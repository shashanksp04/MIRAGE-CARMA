"""Local browser QA. Inference fixtures here are synthetic and test-only."""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import socket
import threading
import time
from types import SimpleNamespace

import pytest
import uvicorn

from Demo.backend.app import create_app
from Demo.backend.configurations import Settings
from Demo.backend.demo_runner import DemoRunner
from Demo.tests.test_api import ApiDatabase
from Demo.tests.test_runner import FakePipeline
from rag_agent.utils.observation import emit


@pytest.fixture
def browser_server(tmp_path):
    control = SimpleNamespace(gate=threading.Event(), ready=True, generated=[], clear_count=0)

    class Database(ApiDatabase):
        def status(self):
            statuses = super().status()
            for item in statuses.values():
                item["checked_at"] = datetime.now(timezone.utc).isoformat()
            return statuses

        def clear(self, collection, confirmation):
            result = super().clear(collection, confirmation)
            control.clear_count += 1
            return result

    database = Database()

    def readiness(preset):
        return {"ready": control.ready, "preset_id": getattr(preset, "id", preset), "checks": {
            "rag": {"ready": control.ready, "model": "TEST RAG MODEL"},
            "generation": {"ready": control.ready, "model": "TEST GENERATION MODEL"},
            "base": {"ready": True}, "runtime": {"ready": True},
        }}

    evidence = [{"text": "TEST FIXTURE: Agricultural passage supplied to the generation endpoint. " * 9,
                 "similarity": .83, "retrieval_source": "base",
                 "metadata": {"title": "TEST FIXTURE extension guidance", "url": "https://example.edu/evidence", "source_type": "web"}},
                {"text": "TEST FIXTURE: A second independent evidence passage.", "similarity": .79,
                 "retrieval_source": "base", "metadata": {"title": "TEST FIXTURE second source", "url": "javascript:alert(1)"}}]

    class Pipeline(FakePipeline):
        def extract(self, images, query):
            return {"status": "success", "attributes": "TEST OBSERVATIONS: yellow spots on a green leaf."}

        async def rag(self, query, location, run_id):
            self.query = query
            if "hold" in query.lower():
                await asyncio.to_thread(control.gate.wait, 15)
            await asyncio.sleep(.08)
            augment = "augment" in query.lower()
            insufficient = "insufficient" in query.lower()
            for attempt in range(2 if augment else 1):
                emit("tool_started", "retrieval", {"tool": "retrieve", "arguments": {"query": query}}, "running")
                await asyncio.sleep(.06)
                for name, score, relevant, eligible in (("hardiness_zone", .61, 1, False), ("semantic_only", .725, 2, True)):
                    emit("strategy_evaluated", "retrieval", {"collection": "mirage_base", "strategy_name": name,
                        "normalized_score": score, "relevant_count": relevant, "similarities": [.83, .79],
                        "eligible": eligible, "reason": "valid_retrieval" if eligible else "insufficient_relevant_results"})
                emit("strategy_selected", "retrieval", {"collection": "mirage_base", "strategy": "semantic_only", "normalized_score": .725})
                emit("tool_completed", "retrieval", {"tool": "retrieve", "result": {"status": "success",
                    "strategy": "semantic_only", "relevant_count": 2, "results": evidence}})
                emit("tool_started", "confidence", {"tool": "evaluate"}, "running")
                low = augment and attempt == 0
                emit("tool_completed", "confidence", {"tool": "evaluate", "result": {
                    "status": "success", "confidence_score": .42 if low else .81,
                    "confidence_level": "low" if low else "high", "diagnostics": {"similarity_score": .81,
                        "coverage_score": .4, "consistency_score": .79, "scope_score": .4,
                        "reason": "valid_retrieval", "relevant_count": 2, "returned_count": 2}}})
                if low:
                    emit("tool_started", "keyword_extraction", {"tool": "keywords"}, "running")
                    emit("tool_completed", "keyword_extraction", {"tool": "keywords", "result": {"status": "success", "keywords": ["corn", "guidance"]}})
                    emit("tool_started", "web_search", {"tool": "search", "arguments": {"query": "corn guidance"}}, "running")
                    emit("web_search_query_prepared", "web_search", {"query": "corn guidance site:example.edu",
                        "allowed_domains": ["example.edu"], "domain_filter_enabled": True})
                    emit("tool_completed", "web_search", {"tool": "search", "result": {"status": "success", "results": [
                        {"title": "TEST FIXTURE web source", "url": "https://example.edu/new"}]}})
                    emit("tool_started", "ingestion", {"tool": "add", "arguments": {"url": "https://example.edu/failed"}}, "running")
                    emit("tool_completed", "ingestion", {"tool": "add", "result": {"status": "error", "error_message": "TEST fetch failure"}})
                    emit("tool_started", "ingestion", {"tool": "add", "arguments": {"url": "https://example.edu/new"}}, "running")
                    before = database.points
                    database.points += 2
                    emit("runtime_count_updated", "database", {"collection": "mirage_demo_runtime", "before": before, "after": database.points, "delta": 2})
                    emit("tool_completed", "ingestion", {"tool": "add", "result": {"status": "success", "url": "https://example.edu/new", "chunks_added": 2}})
            return {"status": "insufficient_evidence" if insufficient else "success", "evidence": [] if insufficient else evidence}

        def generate(self, query, images):
            if "failure" in query.lower():
                raise RuntimeError("TEST FIXTURE generation failure")
            control.generated.append({"query": query, "images": list(images)})
            return "## TEST FIXTURE RESPONSE\n\n**Evidence-informed guidance** from synthetic test inputs.\n\n- Inspect the supplied evidence.\n- [Read the source](https://example.edu/evidence).\n\n<script>window.injected = true</script>"

    settings = replace(Settings(), data_dir=tmp_path)
    app = create_app(settings, database=database, runner=DemoRunner(settings, database, Pipeline),
                     health=SimpleNamespace(check=readiness))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and time.monotonic() < deadline:
        time.sleep(.01)
    assert server.started
    try:
        yield SimpleNamespace(url=f"http://127.0.0.1:{port}", control=control, database=database)
    finally:
        control.gate.set()
        server.should_exit = True
        thread.join(5)
        sock.close()


@pytest.fixture
def page(browser_server):
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as manager:
        try:
            browser = manager.chromium.launch(headless=True)
        except Exception as exc:
            pytest.skip(f"Browser not installed: {exc}")
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, reduced_motion="reduce")
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(browser_server.url)
        page.wait_for_function("document.querySelector('#health-summary').textContent.includes('Services ready')")
        yield page
        assert not errors, errors
        context.close()
        browser.close()
