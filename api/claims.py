import json
from datetime import date
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import Response
from pydantic import BaseModel,Field,field_validator
from api.auth import current_user
from api.db import uid
from api.policies import now

router=APIRouter(prefix='/api/claims')
DOCUMENTS={'invoice':'Itemized bill or receipt','treatment':'Treatment or discharge summary','policy':'Policy and member information'}
class ClaimInput(BaseModel):
    policy_id:str=Field(min_length=1,max_length=64)
    description:str=Field(min_length=3,max_length=4000)
    incident_date:date
    gathered:list[str]=Field(default_factory=list,max_length=10)
    @field_validator('incident_date')
    @classmethod
    def valid_date(cls,value):
        if value>date.today() or value.year<1900: raise ValueError('Enter a past or current incident date.')
        return value
    @field_validator('gathered')
    @classmethod
    def valid_documents(cls,value):
        if any(key not in DOCUMENTS for key in value): raise ValueError('Unknown document item.')
        return list(dict.fromkeys(value))

def record(row): return {'id':row['id'],'policy_id':row['policy_id'],'description':row['description'],'incident_date':row['incident_date'],'gathered':json.loads(row['gathered']),'updated_at':row['updated_at']}
def owned(db,cid,user):
    with db.connect() as c: row=c.execute('SELECT * FROM web_claims WHERE id=? AND user_id=?',(cid,user['id'])).fetchone()
    if not row: raise HTTPException(404,'Claim draft not found.')
    return row
@router.get('')
def claims(request:Request,user=Depends(current_user)):
    with request.app.state.db.connect() as c: rows=c.execute('SELECT * FROM web_claims WHERE user_id=? ORDER BY updated_at DESC',(user['id'],)).fetchall()
    return [record(r) for r in rows]
def save(data,request,user,cid=None):
    db=request.app.state.db;db.owned(data.policy_id,user['id'])
    if cid: owned(db,cid,user)
    else: db.rate('claim:'+user['id'],50,3600)
    cid=cid or uid();updated=now()
    with db.connect() as c:
        c.execute('INSERT INTO web_claims VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET policy_id=excluded.policy_id,description=excluded.description,incident_date=excluded.incident_date,gathered=excluded.gathered,updated_at=excluded.updated_at',(cid,data.policy_id,user['id'],data.description,str(data.incident_date),json.dumps(data.gathered),updated))
    return {**data.model_dump(mode='json'),'id':cid,'updated_at':updated}
@router.post('')
def create(data:ClaimInput,request:Request,user=Depends(current_user)): return save(data,request,user)
@router.put('/{cid}')
def update(cid:str,data:ClaimInput,request:Request,user=Depends(current_user)): return save(data,request,user,cid)
@router.delete('/{cid}',status_code=204)
def delete(cid:str,request:Request,user=Depends(current_user)):
    owned(request.app.state.db,cid,user)
    with request.app.state.db.connect() as c: c.execute('DELETE FROM web_claims WHERE id=? AND user_id=?',(cid,user['id']))
@router.get('/{cid}/export')
def export(cid:str,request:Request,user=Depends(current_user)):
    row=owned(request.app.state.db,cid,user);claim=record(row);policy=request.app.state.db.owned(row['policy_id'],user['id'])
    lines=['PolicyIQ - Claim preparation summary','Preparation only. Not submitted to an insurer.','',f"Policy: {policy['filename']}",f"Incident date: {claim['incident_date']}",'Description:',claim['description'],'','Suggested documents (not policy-derived requirements):']
    lines += [f"[{'Gathered' if key in claim['gathered'] else 'To gather'}] {label}" for key,label in DOCUMENTS.items()]
    lines += ['','No claim documents have been uploaded. Gathered means the user marked an item as ready.','Required documents and deadlines have not been established. Confirm these with your insurer.','',f"Saved: {claim['updated_at']}"]
    return Response('\n'.join(lines),media_type='text/plain; charset=utf-8',headers={'Content-Disposition':'attachment; filename="claim-preparation.txt"'})
