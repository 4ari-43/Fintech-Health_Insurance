from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,Field
from api.auth import current_user
from api.policies import processing
from insurewise.persistent_service import PersistentPolicyService
from insurewise.comparison import compare_policies
router=APIRouter(prefix='/api')
class Selection(BaseModel):
    a:str=Field(min_length=1,max_length=64)
    b:str=Field(min_length=1,max_length=64)
@router.post('/comparison')
def compare(data:Selection,request:Request,user=Depends(current_user)):
    db=request.app.state.db
    db.owned(data.a,user['id']);db.owned(data.b,user['id'])
    if data.a==data.b: raise HTTPException(422,'Choose two different policies.')
    db.rate('compare:'+user['id'],30,3600)
    if not processing.acquire(blocking=False): raise HTTPException(429,'Comparison is busy. Please try again shortly.')
    try:
        result=compare_policies(PersistentPolicyService(db_path=db.path,use_semantic=False),data.a,data.b).model_dump()
        # The backend has not proven benefit/currency/network/tier equivalence.
        for category in result['categories']:
            category.pop('financial_difference',None);category.pop('comparable',None)
        result['limitations'].insert(0,'Benefit, currency, network and coverage-tier equivalence are not established. No reliable financial difference or policy ranking is provided.')
        return result
    finally: processing.release()
