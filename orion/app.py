"""Serve the local UI and API from a single authenticated loopback origin."""
from __future__ import annotations
import hmac
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI,Request,Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse,FileResponse,HTMLResponse
from orion import __version__
from orion.config import Config
from orion.launcher import workspace_id
from orion.store import Store
from orion.library import Library
from orion.discovery import Discovery
from orion.providers import Providers
from orion.planner import Planner
from orion.executor import Executor
from orion.jobs import JobManager
from orion.services import Services


def create_app(data_dir:Path|None=None,frontend_dir:Path|None=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        cfg = Config(data_dir)
        store = Store(cfg.db_path)
        backup = store.migrate()
        cfg.import_preferences(store)
        library = Library(store)
        planner = Planner(library)
        runtime = Services(cfg,store,library,Discovery(library),Providers(cfg,store=store),planner,Executor(library,planner))
        runtime.jobs = JobManager(store,runtime.handlers())
        from orion.integrations.manager import ServerIntegration
        runtime.server = ServerIntegration(runtime)
        planner.catalogue = runtime.server.catalogue
        from orion.watcher import Watcher
        runtime.watcher = Watcher(library,runtime.discovery,jobs=runtime.jobs)
        runtime.watcher.start()
        app.state.services = runtime
        app.state.backup_path = str(backup) if backup else None
        with store.transaction() as conn:
            unfinished = conn.execute("""SELECT 1 FROM orion_operations WHERE json_extract(data,'$.state') NOT IN ('pending','completed')
                UNION ALL SELECT 1 FROM orion_batches WHERE state='running'
                UNION ALL SELECT 1 FROM orion_jobs j JOIN orion_batches b ON json_extract(j.payload,'$.plan_id')=b.plan_id
                    WHERE j.state='interrupted' AND j.kind IN ('organise','undo','sidecars') LIMIT 1""").fetchone()
        if unfinished:
            runtime.jobs.submit('recovery',{})
        try:
            yield
        finally:
            runtime.watcher.stop()
            runtime.jobs.shutdown()

    app = FastAPI(title='Orion local API',version=__version__,lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.state.stop_callback = None
    cookie = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    frontend = Path(frontend_dir) if frontend_dir else Path(__file__).resolve().parents[1]/'frontend'/'dist'

    @app.middleware('http')
    async def local_session(request:Request,call_next):
        if request.url.hostname not in ('127.0.0.1','localhost','::1'):
            return JSONResponse({'code':'invalid_host','message':'Orion accepts loopback hosts only.'},status_code=400)
        origin = request.headers.get('origin')
        if origin:
            parsed = urlsplit(origin)
            if parsed.scheme != request.url.scheme or parsed.netloc.casefold() != request.url.netloc.casefold():
                return JSONResponse({'code':'invalid_origin','message':'Use the Orion local browser window.'},status_code=403)
        if request.headers.get('sec-fetch-site')=='cross-site':
            return JSONResponse({'code':'invalid_origin','message':'Cross-site requests are excluded.'},status_code=403)
        if request.method not in ('GET','HEAD','OPTIONS'):
            if not hmac.compare_digest(request.cookies.get('orion_session_'+str(request.url.port or 80),''),cookie) or not hmac.compare_digest(request.headers.get('x-orion-csrf',''),csrf):
                return JSONResponse({'code':'session_required','message':'Reload Orion to establish a local session.'},status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        if request.url.path.startswith('/api/'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.exception_handler(KeyError)
    async def missing(request,exc):
        return JSONResponse({'code':'not_found','message':'Requested resource does not exist.'},status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request,exc):
        return JSONResponse({'code':'invalid_request','message':str(exc)},status_code=400)

    @app.exception_handler(RequestValidationError)
    async def validation(request,exc):
        return JSONResponse({'code':'invalid_payload','errors':[{'location':e['loc'],'message':e['msg'],'type':e['type']} for e in exc.errors()]},status_code=422)

    @app.get('/api/v1/session')
    def session(request:Request,response:Response):
        response.set_cookie('orion_session_'+str(request.url.port or 80),cookie,httponly=True,samesite='strict',max_age=86400)
        return {'csrf_token':csrf,'workspace_id':workspace_id(request.app.state.services.config.app_data_dir)}

    @app.get('/api/v1/health')
    def health():
        return {'status':'ok','version':__version__}

    @app.post('/api/v1/stop')
    def stop():
        if app.state.stop_callback:
            app.state.stop_callback()
        return {'stopping':True}

    from orion.routes import library,settings,jobs,plans,productivity,server
    for module in (library,settings,jobs,plans,productivity,server):
        app.include_router(module.router)

    @app.get('/{path:path}')
    def static(path:str):
        if path.startswith('api/'):
            return JSONResponse({'code':'not_found'},status_code=404)
        candidate = (frontend/path).resolve()
        if not candidate.is_relative_to(frontend.resolve()):
            return JSONResponse({'code':'not_found'},status_code=404)
        if candidate.is_file():
            return FileResponse(candidate)
        if path.startswith('assets/') or Path(path).suffix:
            return JSONResponse({'code':'not_found'},status_code=404)
        index = frontend/'index.html'
        if index.is_file():
            return FileResponse(index)
        return HTMLResponse('<!doctype html><html lang="en"><meta charset="utf-8"><title>Orion</title><body><h1>Orion engine is running</h1><p>Build the production interface with npm --prefix frontend run build, then reload.</p></body></html>')
    return app
