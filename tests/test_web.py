import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from api.app import create_app
from api.settings import Settings
from api.db import digest

@pytest.fixture
def app(tmp_path): return create_app(Settings(data_dir=tmp_path,auth_limit=4))
@pytest.fixture
def client(app):
    with TestClient(app,headers={'X-PolicyIQ':'1','Origin':'http://127.0.0.1:5173'}) as c: yield c

def signup(client,email='alex@example.test'):
    response=client.post('/api/auth/signup',json={'name':'Alex Fiction','email':email,'password':'Fictional-password-123'})
    assert response.status_code==200,response.text
    client.headers['X-CSRF-Token']=response.json()['csrf']
    return response.json()

def test_auth_lifecycle_csrf_and_rotation(client,app):
    assert client.get('/api/auth/session').status_code==401
    signup(client)
    token=client.cookies.get('policyiq_session')
    assert client.get('/api/auth/session').status_code==200
    assert client.post('/api/auth/logout',headers={'X-CSRF-Token':'bad'}).status_code==403
    assert client.patch('/api/auth/profile',json={'name':'Changed'},headers={'Origin':'https://evil.example'}).status_code==403
    assert client.post('/api/auth/logout').status_code==204
    client.cookies.set('policyiq_session',token)
    assert client.get('/api/auth/session').status_code==401
    client.cookies.clear()
    response=client.post('/api/auth/login',json={'email':'alex@example.test','password':'Fictional-password-123'})
    assert response.status_code==200
    assert client.cookies.get('policyiq_session')!=token
    assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=lax' in response.headers['set-cookie']
    with app.state.db.connect() as c: c.execute('UPDATE web_sessions SET expires=?',(time.time()-1,))
    assert client.get('/api/auth/session').status_code==401

def test_invalid_and_rate_limited_auth(client):
    assert client.post('/api/auth/signup',json={'name':'A','email':'bad','password':'short'}).status_code==422
    for _ in range(4): assert client.post('/api/auth/login',json={'email':'none@example.test','password':'incorrect'}).status_code==401
    assert client.post('/api/auth/login',json={'email':'none@example.test','password':'incorrect'}).status_code==429

def test_reset_is_honest_and_single_use(client,app):
    session=signup(client)
    result=client.post('/api/auth/forgot',json={'email':'alex@example.test'})
    assert 'No email was sent' in result.json()['message']
    token='development-reset-token-example'
    with app.state.db.connect() as c: c.execute('INSERT INTO web_resets VALUES(?,?,?)',(digest(token),session['user']['id'],time.time()+90))
    payload={'token':token,'password':'A-new-fictional-password'}
    assert client.post('/api/auth/reset',json=payload).status_code==204
    assert client.get('/api/auth/session').status_code==401
    assert client.post('/api/auth/reset',json=payload).status_code==400

def test_production_guards(tmp_path):
    with pytest.raises(RuntimeError): create_app(Settings(data_dir=tmp_path,production=True))
    app=create_app(Settings(data_dir=tmp_path,production=True,origin='https://policy.example'))
    with TestClient(app,base_url='https://policy.example',headers={'X-PolicyIQ':'1'}) as client:
        result=client.post('/api/auth/forgot',json={'email':'someone@example.test'})
        assert result.status_code==503
        assert 'max-age=' in result.headers['strict-transport-security']

def test_request_header_and_security_headers(client):
    assert client.post('/api/auth/login',headers={'X-PolicyIQ':''},json={}).status_code==403
    response=client.get('/api/health')
    assert response.headers['x-content-type-options']=='nosniff'
    assert "object-src 'none'" in response.headers['content-security-policy']

def pdf_bytes(text='The annual individual in-network deductible is $750. Emergency care is covered. Prior authorization is required for planned inpatient admissions.'):
    import pymupdf
    doc=pymupdf.open();page=doc.new_page();page.insert_text((50,70),text);data=doc.tobytes();doc.close();return data

def upload(client,data=None,name='fictional-policy.pdf'):
    return client.post('/api/policies',content=data if data is not None else pdf_bytes(),headers={'Content-Type':'application/pdf','X-Filename':name})

def test_policy_ownership_originals_duplicate_and_deletion(client,app):
    a=signup(client)
    data=pdf_bytes()
    response=upload(client,data,'..%2F..%2Ffictional.pdf')
    assert response.status_code==200,response.text
    policy=response.json();pid=policy['id']
    assert policy['filename']=='fictional.pdf'
    assert upload(client,data).json()['id']==pid
    assert len(client.get('/api/policies').json())==1
    assert client.get(f'/api/policies/{pid}/original').content==data
    assert client.get(f'/api/policies/{pid}/pages/1/image').headers['content-type']=='image/png'
    assert '$750' in client.get(f'/api/policies/{pid}/pages/1').json()['text']
    assert client.get(f'/api/policies/{pid}/pages/999/image').status_code==404
    assert client.post(f'/api/policies/{pid}/opened').status_code==204
    assert client.get(f'/api/policies/{pid}').json()['last_opened']
    assert client.patch(f'/api/policies/{pid}',json={'archived':True}).status_code==204
    assert client.get('/api/policies').json()[0]['archived']
    with TestClient(app,headers={'X-PolicyIQ':'1'}) as other:
        signup(other,'bea@example.test')
        assert other.get('/api/policies').json()==[]
        for suffix in ['', '/original', '/pages/1', '/pages/1/image']:
            assert other.get(f'/api/policies/{pid}'+suffix).status_code==404
        assert other.delete(f'/api/policies/{pid}').status_code==404
        assert other.patch(f'/api/policies/{pid}',json={'archived':False}).status_code==404
        other_id=upload(other,data).json()['id']
        assert other_id!=pid
    restarted=create_app(Settings(data_dir=app.state.settings.data_dir))
    with TestClient(restarted,headers={'X-PolicyIQ':'1'}) as restart:
        login=restart.post('/api/auth/login',json={'email':a['user']['email'],'password':'Fictional-password-123'})
        assert login.status_code==200
        assert restart.get(f'/api/policies/{pid}/original').content==data
    assert client.delete(f'/api/policies/{pid}').status_code==204
    assert client.get(f'/api/policies/{pid}/original').status_code==404
    with app.state.db.connect() as c:
        assert c.execute('SELECT count(*) FROM chunks WHERE policy_id=?',(pid,)).fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM web_policies WHERE id=?',(pid,)).fetchone()[0]==0
        assert c.execute('SELECT count(*) FROM web_policies WHERE id=?',(other_id,)).fetchone()[0]==1

def test_upload_abuse_and_recovery(client,app):
    import pymupdf
    signup(client)
    assert upload(client,b'not pdf').status_code==415
    assert upload(client,pdf_bytes(),'bad.txt').status_code==415
    assert upload(client,b'%PDF-1.7 corrupted').status_code==422
    doc=pymupdf.open();doc.new_page();blank=doc.tobytes();doc.close()
    response=upload(client,blank)
    assert response.status_code==422 and 'OCR' in response.json()['detail']
    result=client.post('/api/policies',content=b'abc',headers={'Content-Length':str(21*1024*1024)})
    assert result.status_code==413
    assert upload(client).status_code==200
    assert list(app.state.settings.data_dir.glob('*.pdf'))==[]

def test_questions_claim_contract_followups_failures_and_ownership(client,app,monkeypatch):
    from schemas import ClaimBasedAnswer,InsuranceClaim,ClaimCitation
    from verifier import VerificationResult
    import api.questions as questions
    signup(client);pid=upload(client).json()['id'];app.state.settings.questions_enabled=True
    seen=[]
    def draft(result):
        seen.append(result.question);p=result.passages[0]
        return ClaimBasedAnswer(status='SUPPORTED',answer_text='UNVERIFIED prose: all treatments are free.',claims=[InsuranceClaim(claim_id='c1',text='The individual deductible is $750.',claim_type='deductible',citations=[ClaimCitation(passage_id=p.passage_id,page_start=p.page_start,page_end=p.page_end,quote='$750')])])
    def verify(request,*args):
        return VerificationResult(status='supported',issues=[],claim_results=[{'claim_id':'c1','result':'supported','reason':'mock verifier','supporting_passage_ids':[request.retrieved_passages[0].passage_id]}],additional_searches=[],requires_human_review=False)
    monkeypatch.setattr(questions,'answer_policy_question',draft)
    monkeypatch.setattr(questions,'OpenRouterVerifier',lambda:object())
    monkeypatch.setattr(questions,'verify_answer',verify)
    response=client.post(f'/api/policies/{pid}/questions',json={'question':'What is my deductible?'})
    assert response.status_code==200,response.text
    conv=response.json();answer=conv['messages'][0]['answer']
    assert answer['status']=='verified' and 'UNVERIFIED' not in str(answer)
    assert answer['text']==answer['claims'][0]['text']
    assert answer['sources'][0]['quote'] in answer['sources'][0]['text']
    follow=client.post(f'/api/policies/{pid}/questions',json={'question':'And does that change out of network?','conversation_id':conv['id']})
    assert len(follow.json()['messages'])==2
    assert 'What is my deductible?' in seen[-1]
    assert len(client.get(f'/api/policies/{pid}/conversations').json()[0]['messages'])==2
    with TestClient(app,headers={'X-PolicyIQ':'1'}) as other:
        signup(other,'question-b@example.test');other_id=upload(other).json()['id']
        assert other.get(f'/api/policies/{pid}/conversations').status_code==404
        assert other.post(f'/api/policies/{other_id}/questions',json={'question':'test','conversation_id':conv['id']}).status_code==404
    def failed(*args): raise RuntimeError('secret upstream failure')
    monkeypatch.setattr(questions,'verify_answer',failed)
    failure=client.post(f'/api/policies/{pid}/questions',json={'question':'What is the deductible?'})
    assert failure.status_code==503 and 'secret' not in failure.text
    assert len(client.get(f'/api/policies/{pid}/conversations').json())==1
    monkeypatch.setattr(questions,'verify_answer',lambda *args:VerificationResult(status='needs_review',issues=[],claim_results=[],additional_searches=[],requires_human_review=True))
    answer=client.post(f'/api/policies/{pid}/questions',json={'question':'What is the deductible?'}).json()['messages'][0]['answer']
    assert answer['status']=='insufficient_evidence' and not answer['claims']


def test_claims_export_validation_ownership_and_cascade(client,app):
    signup(client);pid=upload(client).json()['id']
    payload={'policy_id':pid,'description':'<script>alert("x")</script> - a fictional incident','incident_date':'2026-01-10','gathered':['invoice']}
    response=client.post('/api/claims',json=payload)
    assert response.status_code==200,response.text
    cid=response.json()['id']
    assert len(client.get('/api/claims').json())==1
    export=client.get(f'/api/claims/{cid}/export')
    assert export.headers['content-type'].startswith('text/plain')
    assert payload['description'] in export.text and 'not policy-derived' in export.text
    assert 'Not submitted' in export.text
    payload['gathered']=['invoice','treatment']
    assert client.put(f'/api/claims/{cid}',json=payload).json()['gathered']==payload['gathered']
    bad={**payload,'incident_date':'2099-01-01'}
    assert client.post('/api/claims',json=bad).status_code==422
    with TestClient(app,headers={'X-PolicyIQ':'1'}) as other:
        signup(other,'claim-b@example.test')
        assert other.get('/api/claims').json()==[]
        assert other.get(f'/api/claims/{cid}/export').status_code==404
        assert other.put(f'/api/claims/{cid}',json=payload).status_code==404
        assert other.delete(f'/api/claims/{cid}').status_code==404
        assert other.post('/api/claims',json=payload).status_code==404
    client.delete(f'/api/policies/{pid}')
    assert client.get('/api/claims').json()==[]
    assert client.get(f'/api/claims/{cid}/export').status_code==404

def test_comparison_context_suppressed_and_both_owners_checked(client,app):
    signup(client);a=upload(client).json()['id'];b=upload(client,pdf_bytes('The annual individual deductible is $1000. Emergency services require no prior authorization.')).json()['id']
    result=client.post('/api/comparison',json={'a':a,'b':b})
    assert result.status_code==200,result.text
    data=result.json()
    assert len(data['categories'])>=9
    assert 'financial_difference' not in result.text and 'comparable' not in result.text
    assert 'equivalence' in data['limitations'][0]
    assert client.post('/api/comparison',json={'a':a,'b':a}).status_code==422
    with TestClient(app,headers={'X-PolicyIQ':'1'}) as other:
        signup(other,'compare-b@example.test');own=upload(other).json()['id']
        assert other.post('/api/comparison',json={'a':own,'b':a}).status_code==404

def test_streamed_body_limits(tmp_path):
    app=create_app(Settings(data_dir=tmp_path,max_upload=1024))
    with TestClient(app,headers={'X-PolicyIQ':'1'}) as client:
        signup(client)
        response=client.post('/api/policies',content=iter([b'%PDF-1.7\n',b'x'*2048]),headers={'Content-Type':'application/pdf'})
        assert response.status_code==413,response.text
        response=client.post('/api/auth/login',content=iter([b'{"email":"',b'x'*70000,b'"}']),headers={'Content-Type':'application/json'})
        assert response.status_code==413,response.text
