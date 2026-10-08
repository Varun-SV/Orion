from __future__ import annotations
import argparse
import asyncio
import json
import os
import socket
import sys
import webbrowser
from pathlib import Path
import requests
import uvicorn
from orion.app import create_app
from orion.config import Config
from orion.launcher import InstanceLock,existing_url

async def serve(args,cfg):
    sock = socket.socket()
    try:
        sock.bind(('127.0.0.1',args.port))
        sock.listen(128)
        port = sock.getsockname()[1]
        url = f'http://127.0.0.1:{port}'
        frontend = args.frontend_dir
        if frontend is None and hasattr(sys,'_MEIPASS'):
            frontend = Path(sys._MEIPASS)/'frontend'
        app = create_app(cfg.app_data_dir,frontend)
        server = uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='warning',access_log=False))
        app.state.stop_callback = lambda:setattr(server,'should_exit',True)
        record = cfg.app_data_dir/'.instance.json'
        temp = record.with_suffix('.json.tmp')
        temp.write_text(json.dumps({'url':url,'pid':os.getpid()}),encoding='utf-8')
        os.replace(temp,record)
        async def ready():
            while not server.started and not server.should_exit:
                await asyncio.sleep(0.05)
            if server.started:
                print(f'Orion: {url}',flush=True)
                if not args.no_browser:
                    webbrowser.open(url)
        ready_task = asyncio.create_task(ready())
        try:
            await server.serve(sockets=[sock])
        finally:
            ready_task.cancel()
            record.unlink(missing_ok=True)
    except OSError as exc:
        raise RuntimeError(f'Cannot listen on port {args.port}. Choose another --port.') from exc
    finally:
        sock.close()

def main():
    parser = argparse.ArgumentParser(description='Orion local media workspace')
    parser.add_argument('command',nargs='?',choices=('run','stop'),default='run')
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--frontend-dir',type=Path)
    parser.add_argument('--no-browser',action='store_true')
    args = parser.parse_args()
    if not 0<=args.port<=65535:
        parser.error('--port must be between 0 and 65535')
    lock = None
    try:
        cfg = Config(args.data_dir)
        if args.command=='stop':
            url = existing_url(cfg.app_data_dir)
            with requests.Session() as session:
                session.trust_env = False
                response = session.get(url+'/api/v1/session',timeout=5)
                response.raise_for_status()
                token = response.json()['csrf_token']
                stopped = session.post(url+'/api/v1/stop',headers={'X-Orion-CSRF':token},timeout=10)
                stopped.raise_for_status()
            print('Orion is stopping.',flush=True)
            return 0
        lock = InstanceLock(cfg.app_data_dir)
        try:
            lock.acquire()
        except RuntimeError:
            url = existing_url(cfg.app_data_dir)
            print(f'Orion already running: {url}',flush=True)
            if not args.no_browser: webbrowser.open(url)
            return 0
        asyncio.run(serve(args,cfg))
        return 0
    except (RuntimeError,requests.RequestException,ValueError,KeyError) as exc:
        print(f'Orion: {exc}',file=sys.stderr)
        return 1
    finally:
        if lock: lock.release()

if __name__=='__main__':
    raise SystemExit(main())
