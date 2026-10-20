"""Explicit local operator command; tokens are never returned by public reset requests."""
import secrets
import sys
import time
from api.db import Database, digest
from api.settings import Settings

def main():
    settings=Settings(); settings.validate()
    if settings.production: raise SystemExit('Development reset links are disabled in production.')
    if len(sys.argv)!=2: raise SystemExit('Usage: python -m api.reset_link account@example.test')
    db=Database(settings.data_dir)
    with db.connect() as c:
        user=c.execute('SELECT id FROM web_users WHERE email=?',(sys.argv[1].strip().lower(),)).fetchone()
        if not user: raise SystemExit('Local account not found.')
        token=secrets.token_urlsafe(32)
        c.execute('DELETE FROM web_resets WHERE user_id=?',(user['id'],))
        c.execute('INSERT INTO web_resets VALUES(?,?,?)',(digest(token),user['id'],time.time()+900))
    print(settings.origin+'/reset-password#token='+token)
if __name__=='__main__': main()
