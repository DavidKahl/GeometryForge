"""Loopback project catalog and evidence viewer. No modeling execution endpoints."""
from pathlib import Path
import secrets
from urllib.parse import urlparse
from .projects import PACKAGE, registry, register, initialize, load
from .engine import context
from .storage import read, inside

def create_app():
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    app=FastAPI(title='GeometryForge',docs_url=None,redoc_url=None)
    token=secrets.token_urlsafe(32)

    @app.middleware('http')
    async def local_only(request, call_next):
        host=request.headers.get('host','').split(':')[0]
        if host not in ('127.0.0.1','localhost','testserver'):
            return JSONResponse({'error':'Loopback Host required'},status_code=403)
        if request.method not in ('GET','HEAD','OPTIONS'):
            origin=request.headers.get('origin')
            if origin and urlparse(origin).netloc != request.headers.get('host'):
                return JSONResponse({'error':'Cross-origin mutation denied'},status_code=403)
            if request.headers.get('x-geometryforge-token') != token:
                return JSONResponse({'error':'Session token required'},status_code=403)
        try:
            return await call_next(request)
        except (ValueError, FileNotFoundError, KeyError) as exc:
            return JSONResponse({'error':str(exc)},status_code=400)

    def project(key):
        item=registry().get(key)
        if not item:
            raise HTTPException(404,'Unknown project')
        return Path(item['path'])

    @app.get('/api/session')
    def session():
        return {'token':token}

    @app.get('/api/projects')
    def projects():
        return registry()

    @app.post('/api/projects')
    async def add(request: Request):
        body=await request.json()
        if body.get('create'):
            initialize(body['path'],ident=body.get('id'),brief=body.get('brief',''))
        return register(body['path'],body.get('title'))

    @app.patch('/api/projects/{key}')
    async def update(key: str, request: Request):
        body=await request.json();current=registry()[key]
        return register(project(key),body.get('title',current['title']),body.get('archived',current['archived']))

    @app.get('/api/projects/{key}/context')
    def state(key: str):
        return context(project(key))

    @app.get('/api/projects/{key}/runs')
    def runs(key: str):
        root=project(key)
        result=[]
        for file in sorted((root/'.geometryforge/runs').glob('*/run.json'),reverse=True):
            data=read(file)
            if data['status']=='running':
                from .process import is_alive
                if not is_alive(data.get('owner_pid')):
                    data={**data,'status':'interrupted'}
            result.append(data)
        return result

    @app.get('/api/projects/{key}/artifact')
    def download(key: str, path: str, inline: bool = False):
        root=project(key)
        target=inside(root,path)
        # Only retained run artifacts can be served, never arbitrary source files.
        if not target.is_relative_to((root/'.geometryforge/runs').resolve()) or not target.is_file():
            raise HTTPException(404,'Artifact not found')
        if target.suffix not in ('.json','.png','.stl','.3mf','.blend','.hip','.hipnc','.hiplc','.log'):
            raise HTTPException(404,'Unsupported artifact type')
        # inline lets the viewer show images and logs in place; downloads stay the default.
        return FileResponse(target,filename=target.name,content_disposition_type='inline' if inline else 'attachment')

    app.mount('/',StaticFiles(directory=PACKAGE/'web_dist',html=True),name='viewer')
    return app

def serve(port=8743):
    import uvicorn
    print(f'GeometryForge viewer: http://127.0.0.1:{port}',flush=True)
    uvicorn.run(create_app(),host='127.0.0.1',port=port)
