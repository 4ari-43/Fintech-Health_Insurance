import re
import secrets
import sqlite3
import time
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from api.db import digest, uid

router = APIRouter(prefix='/api/auth')
hasher = PasswordHasher()
dummy_hash = hasher.hash(secrets.token_urlsafe(32))
COOKIE = 'policyiq_session'
class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1,max_length=128)
    @field_validator('email')
    @classmethod
    def email_valid(cls, value):
        value=value.strip().lower()
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value): raise ValueError('Enter a valid email address.')
        return value
class Signup(Credentials):
    name: str = Field(min_length=1,max_length=80)
    password: str = Field(min_length=12,max_length=128)
class Reset(BaseModel):
    token: str = Field(min_length=20,max_length=200)
    password: str = Field(min_length=12,max_length=128)
class ChangePassword(BaseModel):
    current: str = Field(min_length=1,max_length=128)
    password: str = Field(min_length=12,max_length=128)
class Profile(BaseModel):
    name: str = Field(min_length=1,max_length=80)
class Email(BaseModel):
    email: str = Field(min_length=3,max_length=254)

def check_password(encoded, password):
    try: return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError): return False

def current_user(request: Request):
    token = request.cookies.get(COOKIE,'')
    with request.app.state.db.connect() as c:
        row=c.execute('SELECT u.id,u.name,u.email,s.csrf,s.token FROM web_users u JOIN web_sessions s ON u.id=s.user_id WHERE s.token=? AND s.expires>?',(digest(token),time.time())).fetchone()
    if row is None: raise HTTPException(401,'Your session has ended. Please log in again.')
    if request.method not in ('GET','HEAD','OPTIONS') and not secrets.compare_digest(row['csrf'],request.headers.get('X-CSRF-Token','')):
        raise HTTPException(403,'Security check failed. Refresh the page and try again.')
    return dict(row)

def public_session(user, csrf): return {'user':{key:user[key] for key in ('id','name','email')},'csrf':csrf}

def issue(request, response, user):
    token,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
    with request.app.state.db.connect() as c:
        c.execute('DELETE FROM web_sessions WHERE token=? OR expires<?',(digest(request.cookies.get(COOKIE,'')),time.time()))
        c.execute('INSERT INTO web_sessions VALUES(?,?,?,?)',(digest(token),user['id'],csrf,time.time()+request.app.state.settings.session_seconds))
    response.set_cookie(COOKIE,token,httponly=True,secure=request.app.state.settings.production,samesite='lax',max_age=request.app.state.settings.session_seconds,path='/')
    return public_session(user,csrf)

def auth_rate(request, email):
    db=request.app.state.db
    db.rate('auth-ip:'+request.client.host,request.app.state.settings.auth_limit*3)
    db.rate('auth-account:'+email.strip().lower(),request.app.state.settings.auth_limit)

@router.post('/signup')
def signup(data:Signup,request:Request,response:Response):
    auth_rate(request,data.email)
    name=data.name.strip()
    if not name: raise HTTPException(422,'Enter your name.')
    user={'id':uid(),'name':name,'email':data.email}
    encoded=hasher.hash(data.password)
    try:
        with request.app.state.db.connect() as c: c.execute('INSERT INTO web_users VALUES(?,?,?,?)',(user['id'],name,data.email,encoded))
    except sqlite3.IntegrityError: raise HTTPException(400,'Account could not be created. Try logging in or resetting your password.') from None
    return issue(request,response,user)

@router.post('/login')
def login(data:Credentials,request:Request,response:Response):
    auth_rate(request,data.email)
    with request.app.state.db.connect() as c: user=c.execute('SELECT * FROM web_users WHERE email=?',(data.email,)).fetchone()
    valid=check_password(user['password'] if user else dummy_hash,data.password)
    if not user or not valid: raise HTTPException(401,'Email or password is incorrect.')
    return issue(request,response,user)

@router.get('/session')
def session(user=Depends(current_user)): return public_session(user,user['csrf'])

@router.post('/logout',status_code=204)
def logout(request:Request,response:Response,user=Depends(current_user)):
    with request.app.state.db.connect() as c: c.execute('DELETE FROM web_sessions WHERE token=?',(user['token'],))
    response.delete_cookie(COOKIE,path='/',httponly=True,samesite='lax',secure=request.app.state.settings.production)

@router.post('/forgot')
def forgot(data:Email,request:Request):
    auth_rate(request,data.email)
    if request.app.state.settings.production: raise HTTPException(503,'Password reset delivery is not configured. Contact the workspace operator.')
    return {'message':'Email delivery is not configured. For a local account, ask the server operator to generate a one-time reset link using the documented development command. No email was sent.'}

@router.post('/reset',status_code=204)
def reset(data:Reset,request:Request):
    request.app.state.db.rate('reset:'+request.client.host,10)
    encoded=hasher.hash(data.password)
    with request.app.state.db.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        reset=c.execute('SELECT * FROM web_resets WHERE token=? AND expires>?',(digest(data.token),time.time())).fetchone()
        if not reset: raise HTTPException(400,'This reset link is invalid or expired. Request a new link.')
        c.execute('UPDATE web_users SET password=? WHERE id=?',(encoded,reset['user_id']))
        c.execute('DELETE FROM web_sessions WHERE user_id=?',(reset['user_id'],))
        c.execute('DELETE FROM web_resets WHERE user_id=?',(reset['user_id'],))

@router.post('/password',status_code=204)
def password(data:ChangePassword,request:Request,response:Response,user=Depends(current_user)):
    request.app.state.db.rate('password:'+user['id'],10)
    with request.app.state.db.connect() as c:
        encoded=c.execute('SELECT password FROM web_users WHERE id=?',(user['id'],)).fetchone()[0]
        if not check_password(encoded,data.current): raise HTTPException(400,'Current password is incorrect.')
        c.execute('UPDATE web_users SET password=? WHERE id=?',(hasher.hash(data.password),user['id']))
        c.execute('DELETE FROM web_sessions WHERE user_id=?',(user['id'],))
    response.delete_cookie(COOKIE,path='/')

@router.patch('/profile')
def profile(data:Profile,request:Request,user=Depends(current_user)):
    if not data.name.strip(): raise HTTPException(422,'Enter your name.')
    with request.app.state.db.connect() as c: c.execute('UPDATE web_users SET name=? WHERE id=?',(data.name.strip(),user['id']))
    user['name']=data.name.strip()
    return public_session(user,user['csrf'])
