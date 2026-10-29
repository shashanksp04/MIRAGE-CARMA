import asyncio
from dataclasses import replace
from io import BytesIO
import json
import threading
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from Demo.backend.app import create_app
from Demo.backend.configurations import Settings
from Demo.backend.demo_runner import DemoRunner
from Demo.tests.test_runner import FakeDatabase, FakePipeline
from rag_agent.utils.observation import emit


class ApiDatabase(FakeDatabase):
    def status(self):
        return {role: {"name": name, "read_only": role == "base", "reachable": True,
                       "compatible": True, "points": self.points}
                for role, name in (("base", "mirage_base"), ("runtime", "mirage_demo_runtime"))}

    def clear(self, collection, confirmation):
        if collection != "mirage_demo_runtime" or confirmation != "CLEAR mirage_demo_runtime":
            raise ValueError("Confirmation mismatch")
        self.points = 0
        return {"points": 0, "collection": collection}


class ApiPipeline(FakePipeline):
    gate = None
    entered = None

    async def rag(self, query, location, run_id):
        if self.entered:
            self.entered.set()
        # Simulate a synchronous tool without holding the API event loop.
        if self.gate:
            self.gate.wait(timeout=5)
        for _ in range(2):
            emit("tool_started", "retrieval", {"tool": "retrieve", "arguments": {"query": query}}, "running")
            emit("tool_completed", "retrieval", {"tool": "retrieve", "result": {"status": "success", "results": []}})
        return await super().rag(query, location, run_id)


@pytest.fixture
def api(tmp_path):
    settings = replace(Settings(), data_dir=tmp_path)
    database = ApiDatabase()
    health = SimpleNamespace(check=lambda preset: {"ready": True, "checks": {}})
    ApiPipeline.status = "success"
    ApiPipeline.gate = ApiPipeline.entered = None
    app = create_app(settings, database=database,
                     runner=DemoRunner(settings, database, ApiPipeline), health=health)
    with TestClient(app) as client:
        yield client, app
        if ApiPipeline.gate:
            ApiPipeline.gate.set()


def wait_done(client, run_id):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        result = client.get(f"/api/runs/{run_id}").json()
        if result["status"] != "running":
            return result
        time.sleep(.01)
    raise AssertionError("Test run did not finish")


def parse_events(text):
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


def test_api_order_repeated_stages_reconnect_and_run_isolation(api):
    client, app = api
    run_id = client.post("/api/runs", json={"question": "How to manage corn?"}).json()["run_id"]
    outcome = wait_done(client, run_id)
    assert outcome["status"] == "completed"
    first = parse_events(client.get(f"/api/runs/{run_id}/events").text)
    assert [e["sequence"] for e in first] == list(range(1, len(first) + 1))
    assert first[0]["type"] == "run_started"
    assert first[-1]["type"] == "run_completed"
    assert [e["iteration"] for e in first if e["type"] == "retrieval_started"] == [1, 2]
    resumed = parse_events(client.get(f"/api/runs/{run_id}/events",
        headers={"Last-Event-ID": f"{run_id}:3"}).text)
    assert resumed == first[3:]
    assert client.get(f"/api/runs/{run_id}/events", headers={"Last-Event-ID": "another:3"}).status_code == 422
    assert client.get(f"/api/runs/{run_id}/events?after=99999").status_code == 422
    second = client.post("/api/runs", json={"question": "Second query"}).json()["run_id"]
    wait_done(client, second)
    assert all(e["run_id"] == second for e in parse_events(client.get(f"/api/runs/{second}/events").text))
    assert client.get("/api/runs").json()["runs"][0]["run_id"] == second


def test_live_stream_disconnect_does_not_cancel_worker_and_reconnects(api):
    client, app = api
    ApiPipeline.gate, ApiPipeline.entered = threading.Event(), threading.Event()
    run_id = client.post("/api/runs", json={"question": "Question"}).json()["run_id"]
    assert ApiPipeline.entered.wait(1)
    endpoint = next(route.endpoint for route in app.routes if route.path == "/api/runs/{run_id}/events")
    disconnected = False
    async def is_disconnected():
        return disconnected
    async def read_then_disconnect():
        nonlocal disconnected
        response = await endpoint(run_id, SimpleNamespace(headers={}, is_disconnected=is_disconnected), after=0)
        iterator = response.body_iterator
        frame = await anext(iterator)
        disconnected = True
        await iterator.aclose()
        return parse_events(frame)[0]
    last = asyncio.run(read_then_disconnect())
    assert last["type"] == "run_started"
    assert client.get(f"/api/runs/{run_id}").json()["status"] == "running"
    ApiPipeline.gate.set()
    wait_done(client, run_id)
    resumed = parse_events(client.get(f"/api/runs/{run_id}/events",
        headers={"Last-Event-ID": f"{run_id}:{last['sequence']}"}).text)
    assert resumed[0]["sequence"] == last["sequence"] + 1
    assert resumed[-1]["type"] == "run_completed"


def test_busy_submission_and_reset_are_rejected_then_lock_releases(api):
    client, app = api
    ApiPipeline.gate, ApiPipeline.entered = threading.Event(), threading.Event()
    run_id = client.post("/api/runs", json={"question": "Question"}).json()["run_id"]
    assert ApiPipeline.entered.wait(1)
    assert client.post("/api/runs", json={"question": "Other"}).status_code == 409
    clear = {"collection": "mirage_demo_runtime", "confirmation": "CLEAR mirage_demo_runtime"}
    assert client.post("/api/database/runtime/clear", json=clear).status_code == 409
    assert client.get("/api/database/status").status_code == 200
    ApiPipeline.gate.set()
    wait_done(client, run_id)
    assert client.post("/api/database/runtime/clear", json=clear).status_code == 200
    assert client.get(f"/api/runs/{run_id}").status_code == 200
    assert client.post("/api/database/runtime/clear", json={"collection": "mirage_base", "confirmation": "CLEAR mirage_base"}).status_code == 422


def test_invalid_inputs_missing_readiness_and_insufficient_evidence(api):
    client, app = api
    for payload in ({"question": ""}, {"question": "q", "preset_id": "made_up"},
                    {"question": "q", "db_on": False}, {"question": "q", "images": ["/etc/passwd"]},
                    {"question": "q", "month_year": "2026-99"}, {"question": "q", "county": "Champaign"}):
        assert client.post("/api/runs", json=payload).status_code == 422
    original = app.state.health.check
    app.state.health.check = lambda _: {"ready": False, "checks": {}}
    assert client.post("/api/runs", json={"question": "Question"}).status_code == 503
    app.state.health.check = original
    ApiPipeline.status = "insufficient_evidence"
    run_id = client.post("/api/runs", json={"question": "Question"}).json()["run_id"]
    result = wait_done(client, run_id)
    assert result["status"] == "insufficient_evidence"
    assert result["result"]["answer"] is None
    types = [e["type"] for e in parse_events(client.get(f"/api/runs/{run_id}/events").text)]
    assert "generation_skipped" in types and "generation_started" not in types


def test_uploads_are_decoded_normalized_and_client_paths_ignored(api):
    client, app = api
    data = BytesIO()
    Image.new("RGB", (8, 8), "green").save(data, format="PNG")
    request = {"question": "Identify", "task_type": "identification"}
    response = client.post("/api/runs", data={"request": json.dumps(request)},
        files=[("images", ("../../outside.png", data.getvalue(), "image/png"))])
    assert response.status_code == 202, response.text
    result = wait_done(client, response.json()["run_id"])
    path = app.state.manager.settings.data_dir / "runs" / result["run_id"] / "image-0.jpg"
    assert Image.open(path).format == "JPEG"
    assert result["result"]["visual_attributes"]["status"] == "success"
    assert client.post("/api/runs", data={"request": json.dumps(request)},
        files=[("images", ("fake.jpg", b"not an image", "image/jpeg"))]).status_code == 422
    assert client.post("/api/runs", data={"request": json.dumps(request)},
        files=[("images", ("file.svg", b"<svg/>", "image/svg+xml"))]).status_code == 422
