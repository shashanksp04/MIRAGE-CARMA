"""Real HTTP/SSE transport with explicitly synthetic inference fixtures."""
from dataclasses import replace
import json
import socket
import threading
import time
from types import SimpleNamespace

import httpx
import uvicorn

from Demo.backend.app import create_app
from Demo.backend.configurations import Settings
from Demo.backend.demo_runner import DemoRunner
from Demo.tests.test_api import ApiDatabase, ApiPipeline


def test_tcp_disconnect_reconnect_while_query_continues(tmp_path):
    settings = replace(Settings(), data_dir=tmp_path)
    db = ApiDatabase()
    ApiPipeline.status = "success"
    ApiPipeline.gate, ApiPipeline.entered = threading.Event(), threading.Event()
    app = create_app(settings, database=db, runner=DemoRunner(settings, db, ApiPipeline),
                     health=SimpleNamespace(check=lambda _: {"ready": True}))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 3
        while not server.started and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=3, trust_env=False) as client:
            run_id = client.post("/api/runs", json={"question": "Transport test"}).json()["run_id"]
            assert ApiPipeline.entered.wait(1)
            with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
                assert stream.headers["content-type"].startswith("text/event-stream")
                for line in stream.iter_lines():
                    if line.startswith("data: "):
                        first = json.loads(line[6:])
                        break
            assert client.get(f"/api/runs/{run_id}").json()["status"] == "running"
            assert client.post("/api/runs", json={"question": "Must be busy"}).status_code == 409
            ApiPipeline.gate.set()
            with client.stream("GET", f"/api/runs/{run_id}/events",
                               headers={"Last-Event-ID": f"{run_id}:{first['sequence']}"}) as stream:
                resumed = [json.loads(line[6:]) for line in stream.iter_lines() if line.startswith("data: ")]
            assert resumed[0]["sequence"] == first["sequence"] + 1
            assert resumed[-1]["type"] == "run_completed"
    finally:
        ApiPipeline.gate.set()
        server.should_exit = True
        thread.join(timeout=5)
        sock.close()
        ApiPipeline.gate = ApiPipeline.entered = None
    assert not thread.is_alive()
