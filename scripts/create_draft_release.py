"""Create a draft release only after rechecking tag ancestry and all asset hashes."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from orion import __version__
from verify_release import verify_tag,verify_assets


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',required=True);parser.add_argument('--assets',type=Path,required=True)
    args=parser.parse_args()
    try:
        if os.environ.get('draft')!='true':raise ValueError('Draft release policy must be explicitly enabled.')
        verify_tag(args.tag,__version__);verify_assets(args.assets)
        subprocess.run(['gh','release','create',args.tag,'--verify-tag','--draft','--title',f'Orion {__version__}','--notes','Unsigned Windows x64 standalone bundle. See README and docs/github-delivery.md for install, backup and recovery guidance.',*[str(p) for p in sorted(args.assets.iterdir()) if p.is_file()]],check=True)
    except (ValueError,OSError,subprocess.CalledProcessError) as exc:print('Draft release rejected:',exc);return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
