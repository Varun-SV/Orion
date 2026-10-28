"""Smoke-test the real bundle using generated data, no system Node/Python, and loopback HTTP."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
import requests
from build_package import validate,References


def smoke(executable):
    executable=executable.resolve()
    if not executable.is_file():raise ValueError('Packaged executable is absent: '+str(executable))
    bundle=executable.parent
    resources=bundle/'_internal/frontend'
    validate(resources)
    forbidden=[str(p.relative_to(bundle)) for p in bundle.rglob('*') if any(q in p.name.casefold() for q in ('pyqt','pyside','qt6core','qt5core'))]
    if forbidden:raise ValueError('Qt resources found in web bundle: '+', '.join(forbidden))
    import os
    env={**os.environ,'PATH':'','PYTHONPATH':''}
    with tempfile.TemporaryDirectory(prefix='orion-package-smoke-') as temporary:
        scratch=Path(temporary);data=scratch/'isolated data';data.mkdir()
        log=(scratch/'launch.log').open('w+',encoding='utf-8')
        started=time.perf_counter()
        command=[str(executable),'run','--data-dir',str(data),'--port','0','--no-browser']
        process=subprocess.Popen(command,cwd=scratch,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            record=data/'.instance.json';url=None
            with requests.Session() as session:
                session.trust_env=False
                while time.perf_counter()-started<45:
                    if process.poll() is not None:raise ValueError('Package exited before becoming ready.')
                    try:
                        url=json.loads(record.read_text(encoding='utf-8'))['url']
                        health=session.get(url+'/api/v1/health',timeout=1)
                        if health.status_code==200:break
                    except (OSError,ValueError,requests.RequestException):pass
                    time.sleep(.05)
                else:raise ValueError('Package readiness timed out.')
                startup=time.perf_counter()-started
                if health.json().get('status')!='ok':raise ValueError('Unexpected API health response.')
                index=session.get(url+'/',timeout=5)
                if index.status_code!=200 or not index.headers.get('content-type','').startswith('text/html'):raise ValueError('Packaged frontend route failed.')
                if index.content!=(resources/'index.html').read_bytes():raise ValueError('Package served a fallback rather than bundled production UI.')
                for asset in resources.rglob('*'):
                    if asset.is_file() and asset.name!='index.html':
                        response=session.get(url+'/'+asset.relative_to(resources).as_posix(),timeout=5)
                        if response.status_code!=200 or response.content!=asset.read_bytes():raise ValueError('Bundled static asset mismatch: '+asset.name)
                if not (data/'organizer.db').is_file():raise ValueError('Isolated database was not created.')
                again=subprocess.run(command,cwd=scratch,env=env,capture_output=True,text=True,timeout=15)
                if again.returncode!=0 or 'already running' not in again.stdout or url not in again.stdout:raise ValueError('Repeated launch failed to reuse the local instance.')
                with socket.socket() as occupied:
                    occupied.bind(('127.0.0.1',0));occupied.listen(1)
                    other=scratch/'occupied data'
                    failure=subprocess.run([str(executable),'run','--data-dir',str(other),'--port',str(occupied.getsockname()[1]),'--no-browser'],cwd=scratch,env=env,capture_output=True,text=True,timeout=15)
                    if failure.returncode==0 or 'port' not in failure.stderr.lower():raise ValueError('Occupied port did not produce a clear nonzero failure.')
                stopped=subprocess.run([str(executable),'stop','--data-dir',str(data)],cwd=scratch,env=env,capture_output=True,text=True,timeout=15)
                if stopped.returncode!=0:raise ValueError('Packaged stop command failed: '+stopped.stderr)
                if process.wait(timeout=10)!=0:raise ValueError('Packaged server failed graceful shutdown.')
                if record.exists():raise ValueError('Instance record survives graceful shutdown.')
                return {'platform':'Windows','startup_seconds':round(startup,3),'bundle_bytes':sum(p.stat().st_size for p in bundle.rglob('*') if p.is_file()),'health':health.json(),'static_assets_checked':sum(p.is_file() for p in resources.rglob('*')),'isolated_database':True,'occupied_port_rejected':True,'repeat_launch_reuses_instance':True,'graceful_stop':True,'system_path_empty':True,'qt_resources':forbidden}
        except Exception as exc:
            log.flush();log.seek(0)
            raise ValueError(str(exc)+'\nPackage log:\n'+log.read()) from exc
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            log.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--executable',type=Path,required=True);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    try:result=smoke(args.executable)
    except (OSError,ValueError,subprocess.TimeoutExpired) as exc:print('Package smoke failed:',exc);return 1
    text=json.dumps(result,indent=2)
    if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text+'\n',encoding='utf-8')
    print(text);return 0

if __name__=='__main__':raise SystemExit(main())


