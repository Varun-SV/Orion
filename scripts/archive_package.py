"""Archive a validated standalone bundle and write the full checksum manifest."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from orion import __version__
from verify_release import verify_assets


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not (args.bundle/'Orion.exe').is_file():parser.error('Bundle must contain Orion.exe.')
    args.output.mkdir(parents=True,exist_ok=True)
    if any(args.output.iterdir()):parser.error('Release output must be empty to avoid stale assets.')
    name=f'Orion-{__version__}-windows-x64'
    archive=Path(shutil.make_archive(str(args.output/name),'zip',root_dir=args.bundle.parent,base_dir=args.bundle.name))
    with archive.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    (args.output/'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n',encoding='utf-8')
    verify_assets(args.output)
    print(f'{archive}: {archive.stat().st_size} bytes; SHA256 {digest}')
    return 0

if __name__=='__main__':raise SystemExit(main())
