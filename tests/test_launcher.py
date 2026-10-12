import os
import socket
import subprocess
import time
from pathlib import Path
import httpx
import pytest
from orion.launcher import InstanceLock,available_port

def test_existing_instance_lock_does_not_start_second_backend(tmp_path):
    first = InstanceLock(tmp_path)
    first.acquire()
    try:
        second = InstanceLock(tmp_path)
        with pytest.raises(RuntimeError): second.acquire()
    finally:
        first.release()
    second.acquire()
    second.release()

def test_occupied_port_is_detected():
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1',0))
        occupied.listen()
        port = occupied.getsockname()[1]
        with pytest.raises(RuntimeError): available_port(port)

def test_cli_serves_isolated_backend_and_stops(tmp_path):
    port = available_port(0)
    process = subprocess.Popen([__import__('sys').executable,'-m','orion','--data-dir',str(tmp_path),'--port',str(port),'--no-browser'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    url = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic()+15
        while time.monotonic()<deadline:
            if process.poll() is not None:
                pytest.fail(process.stdout.read().decode(errors='replace'))
            try:
                if httpx.get(url+'/api/v1/health',timeout=0.5).status_code==200: break
            except httpx.RequestError:
                time.sleep(0.05)
        else:
            pytest.fail('Launcher did not become ready')
        assert (tmp_path/'organizer.db').exists()
        stopped = subprocess.run([__import__('sys').executable,'-m','orion','stop','--data-dir',str(tmp_path)],capture_output=True,timeout=15)
        assert stopped.returncode == 0, stopped.stderr.decode(errors='replace')
        assert process.wait(timeout=15) == 0
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
