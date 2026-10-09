"""Validate release history or verify every asset against its checksum manifest."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import re
import subprocess


def git(*args):
    result=subprocess.run(['git',*args],capture_output=True,text=True)
    if result.returncode:raise ValueError('Missing or invalid Git history: '+result.stderr.strip())
    return result.stdout.strip()


def verify_tag(tag,version):
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:[a-zA-Z0-9.+-]*)?',version) or tag!='v'+version:
        raise ValueError('Tag must match the runtime version v'+version)
    head=git('rev-parse','HEAD')
    tagged=git('rev-parse','--verify',f'refs/tags/{tag}^{{commit}}')
    if head!=tagged:raise ValueError('Tag does not resolve to the checked-out commit.')
    try:
        git('rev-parse','--verify','refs/remotes/origin/main^{commit}')
        git('merge-base','--is-ancestor',head,'refs/remotes/origin/main')
    except ValueError as exc:
        raise ValueError('Tag ancestry cannot be established on origin/main: '+str(exc)) from exc


def verify_assets(directory):
    manifest=directory/'SHA256SUMS.txt'
    if not manifest.is_file():raise ValueError('Checksum manifest is absent.')
    lines=manifest.read_text(encoding='utf-8').splitlines()
    if not lines:raise ValueError('Checksum manifest is empty.')
    seen=set()
    for line in lines:
        match=re.fullmatch(r'([a-f0-9]{64})  ([A-Za-z0-9][A-Za-z0-9_.-]*)',line)
        if not match:raise ValueError('Invalid checksum entry or unsafe asset name.')
        expected,name=match.groups()
        if name in seen or name=='SHA256SUMS.txt':raise ValueError('Duplicate or recursive checksum entry.')
        seen.add(name);asset=directory/name
        if not asset.is_file() or asset.is_symlink():raise ValueError('Release asset absent: '+name)
        if hashlib.file_digest(asset.open('rb'),'sha256').hexdigest()!=expected:raise ValueError('Checksum mismatch: '+name)
    actual={p.name for p in directory.iterdir() if p.is_file() and p.name!='SHA256SUMS.txt'}
    if actual!=seen:raise ValueError('Assets do not match the complete checksum manifest.')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag');parser.add_argument('--version');parser.add_argument('--assets',type=Path)
    args=parser.parse_args()
    try:
        if args.assets:verify_assets(args.assets)
        elif args.tag and args.version:verify_tag(args.tag,args.version)
        else:parser.error('supply --tag and --version, or --assets')
    except (ValueError,OSError) as exc:print('Release rejected:',exc);return 1
    print('Release validation passed.');return 0

if __name__=='__main__':raise SystemExit(main())

