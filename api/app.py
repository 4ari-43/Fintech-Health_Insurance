import asyncio
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from api.settings import Settings
from api.db import Database
from api.auth import router as auth_router

class BodyLimit:
    def __init__(self, app, maximum): self.app,self.maximum=app,maximum
    async def __call__(self,scope,receive,send):
        if scope['type']!='http': return await self.app(scope,receive,send)
        limit=self.maximum if scope['path']=='/api/policies' else 65536
        length=0
        async def limited():
            nonlocal length
            try: message=await asyncio.wait_for(receive(),timeout=30)
            except TimeoutError: raise HTTPException(408,'Request timed out. Please try again.') from None
            length+=len(message.get('body',b''))
            if length>limit: raise HTTPException(413,'The file or request is too large. PDFs must be 20 MB or smaller.')
            return message
        await self.app(scope,limited,send)

def create_app(settings=None):
    settings=settings or Settings(); settings.validate()
    app=FastAPI(title='PolicyIQ API',docs_url=None if settings.production else '/api/docs',openapi_url=None if settings.production else '/api/openapi.json',redoc_url=None)
    app.state.settings=settings; app.state.db=Database(settings.data_dir)
    app.add_middleware(BodyLimit,maximum=settings.max_upload)
    @app.middleware('http')
    async def security(request:Request,call_next):
        response=None
        if request.method not in ('GET','HEAD','OPTIONS'):
            origin=request.headers.get('origin')
            if request.headers.get('X-PolicyIQ')!='1' or (origin and origin!=settings.origin):
                response=JSONResponse({'detail':'Security check failed. Refresh the page and try again.'},403)
        if response is None:
            try: response=await call_next(request)
            except Exception:
                response=JSONResponse({'detail':'The operation could not be completed. Please try again.'},500)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        response.headers['Cache-Control']='no-store'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; frame-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        if settings.production: response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
        return response
    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc): return JSONResponse({'detail':'Some fields are invalid. Check the form and try again.'},422)
    app.include_router(auth_router)
    @app.get('/api/config')
    def config():
        enabled=settings.questions_enabled
        provider=__import__('os').getenv('AI_PROVIDER','ollama')
        return {'questions_enabled':enabled,'processing':('Questions and relevant policy passages are sent to '+('local Ollama and external OpenRouter verification.' if provider=='ollama' else 'Google Gemini and OpenRouter verification (auto mode may try several Gemini models).')) if enabled else 'PDF extraction and keyword retrieval run on this server. Model questions are disabled. Documents and drafts are stored in the server database.', 'reset_delivery':'Not configured; development operator command only' if not settings.production else 'Unavailable'}
    @app.get('/api/health')
    def health(): return {'status':'ok'}
    from api.policies import router as policies_router
    app.include_router(policies_router)
    from api.questions import router as questions_router
    app.include_router(questions_router)
    from api.claims import router as claims_router
    from api.comparison import router as comparison_router
    app.include_router(claims_router)
    app.include_router(comparison_router)
    dist=Path(__file__).resolve().parent.parent/'frontend'/'dist'
    if (dist/'assets').exists(): app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
    @app.get('/{path:path}')
    def spa(path:str):
        if path.startswith('api/') or '.' in path: raise HTTPException(404,'Not found.')
        if not (dist/'index.html').exists(): raise HTTPException(503,'Frontend is not built. Run npm run build in frontend/.')
        return FileResponse(dist/'index.html')
    return app



