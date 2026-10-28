"""Build a Qt-free desktop bundle from a verified snapshot of frontend resources."""
from __future__ import annotations
import argparse
from html.parser import HTMLParser
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit,unquote

ROOT=Path(__file__).resolve().parents[1]

class References(HTMLParser):
    def __init__(self):super().__init__();self.paths=[]
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ('src','href') and value:
                parsed=urlsplit(value)
                if not parsed.scheme and not parsed.netloc and parsed.path and parsed.path!='/':self.paths.append(unquote(parsed.path).lstrip('/'))

def validate(frontend):
    if not (frontend/'index.html').is_file():raise ValueError('Production frontend index.html missing. Run npm --prefix frontend run build.')
    if not (frontend/'assets').is_dir() or not any((frontend/'assets').iterdir()):raise ValueError('Production frontend assets are missing.')
    refs=References();refs.feed((frontend/'index.html').read_text(encoding='utf-8'))
    for name in refs.paths:
        asset=(frontend/name).resolve()
        if not asset.is_relative_to(frontend.resolve()) or not asset.is_file():raise ValueError('Production frontend asset missing: '+name)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--frontend',type=Path,default=ROOT/'frontend/dist');parser.add_argument('--validate-only',action='store_true')
    args=parser.parse_args();frontend=args.frontend.resolve()
    try:
        validate(frontend)
        if args.validate_only:print('Production package resources validated.');return 0
        if sys.platform!='win32':print('Windows package builds require Windows.');return 1
        # Vite replaces dist during builds: package a stable copy and validate again after copying.
        with tempfile.TemporaryDirectory(prefix='orion-build-') as temporary:
            snapshot=Path(temporary)/'frontend';shutil.copytree(frontend,snapshot);validate(snapshot)
            env={**os.environ,'ORION_FRONTEND_DIST':str(snapshot)}
            return subprocess.call([sys.executable,'-m','PyInstaller','--noconfirm','--clean',str(ROOT/'build.spec')],cwd=ROOT,env=env)
    except (OSError,ValueError) as exc:print(exc);return 1

if __name__=='__main__':raise SystemExit(main())
