# -*- coding: utf-8 -*-
"""冒烟测试：起一个本地服务，请求首页，确认 200 后关掉。

CI 和本地都能跑：
    python tools/smoke_server.py            # 默认端口 8791
    python tools/smoke_server.py 18888      # 指定端口

失败时会把服务端 stdout/stderr 打出来，方便定位。
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def wait_port(port: int, timeout: float) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(('127.0.0.1', port)) == 0:
                return True
        time.sleep(0.3)
    return False


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8791
    env = dict(os.environ)
    env.setdefault('PYTHONUTF8', '1')
    env.setdefault('PYTHONIOENCODING', 'utf-8')

    proc = subprocess.Popen(
        [sys.executable, str(ROOT / 'app' / 'server_v3.py'), str(port)],
        cwd=str(ROOT), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    try:
        if not wait_port(port, 30):
            out = b''
            if proc.poll() is not None:
                out = proc.stdout.read() or b''
                print(f'服务进程已退出，exit={proc.returncode}')
            else:
                proc.terminate()
                try:
                    out = proc.communicate(timeout=5)[0] or b''
                except subprocess.TimeoutExpired:
                    proc.kill()
            print('--- 服务端输出 ---')
            print(out.decode('utf-8', errors='replace')[-4000:])
            return 1

        code = 0
        for _ in range(10):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=5) as r:
                    code = r.status
                break
            except urllib.error.HTTPError as e:
                code = e.code
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        print(f'首页 HTTP {code}')
        return 0 if code == 200 else 1
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == '__main__':
    sys.exit(main())
