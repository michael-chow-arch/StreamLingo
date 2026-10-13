"""One real TCP smoke test: exercise the installed CLI and Uvicorn, not only ASGI mocks."""

import asyncio
import json
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from uuid import uuid4

from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus


def test_cli_over_real_loopback_socket():
    origin = "chrome-extension://" + "a" * 32
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    args = [sys.executable, "-m", "streamlingo.cli", "--mode", "demo", "--port", str(port),
            "--allow-origin", origin]
    process = subprocess.Popen(
        args, cwd=Path(__file__).parents[1], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    try:
        deadline = time.monotonic() + 10
        while True:
            assert process.poll() is None, "Server exited during startup"
            try:
                with urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                    assert json.load(response)["mode"] == "demo"
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)

        async def exchange():
            uri = f"ws://127.0.0.1:{port}/ws/live"
            session_id = str(uuid4())
            async with connect(uri, origin=origin) as ws:
                await ws.send(json.dumps({
                    "type": "start", "protocol_version": 1, "session_id": session_id,
                    "source_language": "en", "target_language": "zh-CN",
                    "audio": {"encoding": "pcm_s16le", "sample_rate": 16000, "channels": 1},
                }))
                assert json.loads(await ws.recv())["type"] == "ready"
                for _ in range(10):
                    await ws.send(bytes(6400))
                subtitle = json.loads(await ws.recv())
                assert subtitle["end_ms"] == 2000 and subtitle["translation"]["status"] == "pending"
                translated = json.loads(await ws.recv())
                assert translated["translation"]["is_mock"] and translated["revision"] == 2
                await ws.send(json.dumps({"type": "stop", "session_id": session_id}))
                assert json.loads(await ws.recv())["type"] == "stopped"
            try:
                async with connect(uri, origin="https://www.youtube.com"):
                    raise AssertionError("Unlisted origin was accepted")
            except InvalidStatus as rejected:
                assert rejected.response.status_code == 403

        async def bounded_exchange():
            await asyncio.wait_for(exchange(), timeout=5)
        asyncio.run(bounded_exchange())
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
