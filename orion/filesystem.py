"""Filesystem primitives: exclusive publication and cancellable verified copies."""
from __future__ import annotations
import hashlib
import os
import shutil
from pathlib import Path
from orion.discovery import signature,linked,Cancelled
from orion.planner import nearest_existing

CHUNK_SIZE = 1024*1024

class Filesystem:
    def same_volume(self,source,destination):
        return Path(source).stat().st_dev == nearest_existing(Path(destination).parent).stat().st_dev

    def hash(self,path,context=None):
        digest = hashlib.sha256()
        with Path(path).open('rb') as file:
            while True:
                if context and context.cancelled():
                    raise Cancelled()
                block = file.read(CHUNK_SIZE)
                if not block:
                    break
                digest.update(block)
        return digest.hexdigest()

    def sync_directory(self,path):
        if os.name != 'nt':
            fd = os.open(path,os.O_RDONLY | getattr(os,'O_DIRECTORY',0))
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def rename_noreplace(self,source,destination):
        source,destination = Path(source),Path(destination)
        if linked(source) or linked(destination):
            raise ValueError('Linked paths are excluded')
        if os.name == 'nt':
            # Windows rename fails if the destination exists; never use replace().
            os.rename(source,destination)
        else:
            # link() publishes exclusively on POSIX; a crash between link/unlink
            # leaves both names and is recognised by the stored inode and hash.
            os.link(source,destination,follow_symlinks=False)
            self.sync_directory(destination.parent)
            source.unlink()
        self.sync_directory(destination.parent)
        self.sync_directory(source.parent)

    def copy(self,source,temp,context,checkpoint):
        copied = 0
        digest = hashlib.sha256()
        with Path(source).open('rb') as original, Path(temp).open('xb') as output:
            checkpoint(0,digest.hexdigest(),signature(Path(temp)))
            while True:
                if context.cancelled(): raise Cancelled()
                block = original.read(CHUNK_SIZE)
                if not block: break
                output.write(block)
                output.flush()
                os.fsync(output.fileno())
                digest.update(block)
                copied += len(block)
                checkpoint(copied,digest.hexdigest(),signature(Path(temp)))
        shutil.copystat(source,temp,follow_symlinks=False)
        self.sync_directory(Path(temp).parent)
        return copied,digest.hexdigest()

    def remove_source(self,source,expected):
        source = Path(source)
        if signature(source) != expected:
            raise ValueError('Source changed; retain it for review')
        source.unlink()
        self.sync_directory(source.parent)
