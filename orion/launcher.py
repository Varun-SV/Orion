"""Cross-platform launcher primitives and safe local instance discovery."""
from __future__ import annotations
import json
import os
import socket
from pathlib import Path
from urllib.parse import urlsplit

class InstanceLock:
    def __init__(self,data_dir):
        self.path = Path(data_dir)/'.instance.lock'
        self.handle = None

    def acquire(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        handle = self.path.open('a+b')
        if self.path.stat().st_size==0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            handle.close()
            raise RuntimeError('Orion is already running for this data directory.') from None
        self.handle = handle

    def release(self):
        if self.handle:
            self.handle.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(),fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None

def available_port(port):
    try:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',port))
            return sock.getsockname()[1]
    except OSError:
        raise RuntimeError(f'Port {port} is occupied. Choose another --port or open the existing Orion instance.') from None

def existing_url(data_dir):
    try:
        value = json.loads((Path(data_dir)/'.instance.json').read_text(encoding='utf-8'))['url']
        parsed = urlsplit(value)
        if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or not parsed.port or parsed.path or parsed.query or parsed.fragment:
            raise ValueError()
        return value
    except (OSError,ValueError,KeyError,TypeError):
        raise RuntimeError('No valid local Orion instance record. Start Orion first.') from None
