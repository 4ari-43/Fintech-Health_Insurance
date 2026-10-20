import hashlib
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import BoundedSemaphore
from urllib.parse import unquote
import pymupdf
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
from api.auth import current_user
from api.db import uid
from insurewise.ingest import process_pdf, IngestionError
from insurewise.chunking import chunk_policy

router=APIRouter(prefix='/api/policies')
processing=BoundedSemaphore(2)
def now(): return datetime.now(timezone.utc).isoformat()
def metadata(row):
    return {'id':row['policy_id'],'filename':row['filename'],'page_count':row['page_count'],'created_at':row['created_at'],'last_opened':row['last_opened'],'archived':bool(row['archived']),'warnings':json.loads(row['warnings_json']),'original_available':True}

def ingest_bytes(request,user,body,filename):
    db=request.app.state.db
    file_hash=hashlib.sha256(body).hexdigest()
    with db.connect() as c:
        existing=c.execute('SELECT id FROM web_policies WHERE user_id=? AND hash=?',(user['id'],file_hash)).fetchone()
        if existing: return metadata(db.owned(existing['id'],user['id']))
        count=c.execute('SELECT count(*) FROM web_policies WHERE user_id=?',(user['id'],)).fetchone()[0]
    if count>=50: raise HTTPException(409,'This workspace has reached its 50-policy limit. Remove an unused policy first.')
    if not body.startswith(b'%PDF-'): raise HTTPException(415,'This file is not a PDF. Choose a PDF document and try again.')
    if not processing.acquire(blocking=False): raise HTTPException(429,'Document processing is busy. Please try again shortly.')
    temp_path=None
    try:
        with tempfile.NamedTemporaryFile(suffix='.pdf',dir=request.app.state.settings.data_dir,delete=False) as temp:
            temp.write(body);temp_path=Path(temp.name)
        doc=process_pdf(temp_path,max_file_mb=20,max_pages=300)
        policy_id=uid()
        chunks=chunk_policy(doc)
        for index,chunk in enumerate(chunks):
            chunk.policy_id=policy_id;chunk.chunk_id=f'{policy_id}_c{index+1}'
        db.store.save_policy(policy_id,filename,doc.page_count,doc.status,doc.warnings,chunks)
        try:
            with db.connect() as c: c.execute('INSERT INTO web_policies(id,user_id,hash,original) VALUES(?,?,?,?)',(policy_id,user['id'],file_hash,body))
        except Exception:
            db.store.delete_policy(policy_id)
            with db.connect() as c: existing=c.execute('SELECT id FROM web_policies WHERE user_id=? AND hash=?',(user['id'],file_hash)).fetchone()
            if existing: return metadata(db.owned(existing['id'],user['id']))
            raise
        return metadata(db.owned(policy_id,user['id']))
    except IngestionError as exc:
        messages={'NO_EXTRACTABLE_TEXT':'No readable text was found. Choose a searchable PDF; scanned documents need OCR first.','PDF_ENCRYPTED':'This PDF is password protected. Upload an unlocked copy.','PAGE_LIMIT_EXCEEDED':'This PDF exceeds the 300-page limit.','PDF_PARSE_FAILED':'This PDF could not be read. Try exporting a fresh copy.'}
        raise HTTPException(422,messages.get(exc.code.value,'This PDF could not be processed. Check the document and try again.')) from None
    finally:
        try:
            if temp_path: temp_path.unlink(missing_ok=True)
        finally: processing.release()

@router.get('')
def policies(request:Request,user=Depends(current_user)):
    with request.app.state.db.connect() as c:
        rows=c.execute('SELECT p.*,w.archived,w.last_opened FROM policies p JOIN web_policies w ON p.policy_id=w.id WHERE w.user_id=? ORDER BY p.created_at DESC',(user['id'],)).fetchall()
    return [metadata(row) for row in rows]

@router.post('')
async def upload(request:Request,user=Depends(current_user)):
    from starlette.concurrency import run_in_threadpool
    request.app.state.db.rate('upload:'+user['id'],15,3600)
    length=request.headers.get('content-length')
    if length and (not length.isdigit() or int(length)>request.app.state.settings.max_upload): raise HTTPException(413,'PDFs must be 20 MB or smaller.')
    body=await request.body()
    if len(body)>request.app.state.settings.max_upload: raise HTTPException(413,'PDFs must be 20 MB or smaller.')
    filename=unquote(request.headers.get('X-Filename','policy.pdf'))
    filename=re.sub(r'[\x00-\x1f\x7f]','',filename.replace('\\','/').split('/')[-1])[:180] or 'policy.pdf'
    if not filename.lower().endswith('.pdf'): raise HTTPException(415,'Choose a PDF file.')
    return await run_in_threadpool(ingest_bytes,request,user,body,filename)

@router.get('/{policy_id}')
def policy(policy_id:str,request:Request,user=Depends(current_user)): return metadata(request.app.state.db.owned(policy_id,user['id']))

@router.post('/{policy_id}/opened',status_code=204)
def opened(policy_id:str,request:Request,user=Depends(current_user)):
    request.app.state.db.owned(policy_id,user['id'])
    with request.app.state.db.connect() as c: c.execute('UPDATE web_policies SET last_opened=? WHERE id=? AND user_id=?',(now(),policy_id,user['id']))

class Archive(BaseModel): archived:bool
@router.patch('/{policy_id}',status_code=204)
def archive(policy_id:str,data:Archive,request:Request,user=Depends(current_user)):
    request.app.state.db.owned(policy_id,user['id'])
    with request.app.state.db.connect() as c: c.execute('UPDATE web_policies SET archived=? WHERE id=? AND user_id=?',(int(data.archived),policy_id,user['id']))

@router.delete('/{policy_id}',status_code=204)
def delete(policy_id:str,request:Request,user=Depends(current_user)):
    request.app.state.db.owned(policy_id,user['id'])
    request.app.state.db.store.delete_policy(policy_id)

def original_bytes(request,policy_id,user):
    request.app.state.db.owned(policy_id,user['id'])
    with request.app.state.db.connect() as c: return c.execute('SELECT original FROM web_policies WHERE id=? AND user_id=?',(policy_id,user['id'])).fetchone()[0]

@router.get('/{policy_id}/original')
def original(policy_id:str,request:Request,user=Depends(current_user)):
    body=original_bytes(request,policy_id,user)
    return Response(body,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="policy.pdf"'})

@router.get('/{policy_id}/pages/{page}')
def page_text(policy_id:str,page:int,request:Request,user=Depends(current_user)):
    with pymupdf.open(stream=original_bytes(request,policy_id,user),filetype='pdf') as doc:
        if not 1<=page<=len(doc): raise HTTPException(404,'Page not found.')
        return {'text':doc[page-1].get_text(),'page_count':len(doc)}

@router.get('/{policy_id}/pages/{page}/image')
def page_image(policy_id:str,page:int,request:Request,user=Depends(current_user)):
    request.app.state.db.rate('render:'+user['id'],180,60)
    if not processing.acquire(blocking=False): raise HTTPException(429,'Document rendering is busy. Try again shortly.')
    try:
        with pymupdf.open(stream=original_bytes(request,policy_id,user),filetype='pdf') as doc:
            if not 1<=page<=len(doc): raise HTTPException(404,'Page not found.')
            p=doc[page-1];scale=min(1.5,1800/max(p.rect.width,1),1800/max(p.rect.height,1))
            return Response(p.get_pixmap(matrix=pymupdf.Matrix(scale,scale),alpha=False).tobytes('png'),media_type='image/png')
    finally: processing.release()

