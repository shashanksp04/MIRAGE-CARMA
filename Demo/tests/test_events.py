import asyncio
from dataclasses import replace
import inspect
import json
import os
import statistics
from types import SimpleNamespace

import pytest

from Demo.backend.configurations import Settings
from Demo.backend.event_stream import EventSink, bounded
from Demo.backend.run_store import RunStore
from Demo.tests.source_loader import definitions
from rag_agent.utils.observation import emit, observe, observe_tool
from rag_agent.utils.rag_state import RetrievalResult
from rag_agent.tools.confidence_evaluator import K, MIN_RESULTS, RELEVANT_CHUNK_THRESHOLD


def test_observer_preserves_signature_return_and_exceptions():
    @observe_tool("retrieval")
    def action(*, query: str):
        """Original tool description."""
        if not query:
            raise ValueError("empty")
        return {"status": "success", "query": query}
    original = action(query="corn")
    events = []
    with observe(lambda *args: events.append(args)):
        assert action(query="corn") == original
        with pytest.raises(ValueError):
            action(query="")
    assert action.__doc__ == "Original tool description."
    assert str(inspect.signature(action)) == "(*, query: str)"
    assert [e[0] for e in events] == ["tool_started", "tool_completed", "tool_started", "tool_failed"]
    def broken(*args):
        raise RuntimeError("observer failure")
    with observe(broken):
        assert action(query="corn") == original


def test_request_context_isolation():
    events = {"a": [], "b": []}
    async def work(name):
        with observe(lambda *args: events[name].append(args)):
            await asyncio.sleep(0)
            emit("test", "run", {"name": name})
    async def together():
        await asyncio.gather(work("a"), work("b"))
    asyncio.run(together())
    assert events["a"][0][2] == {"name": "a"}
    assert events["b"][0][2] == {"name": "b"}


def test_recording_bounds_order_isolation_retention_and_recovery(tmp_path):
    store = RunStore(replace(Settings(), data_dir=tmp_path, max_events=20, max_runs=2))
    store.create("a", {"mode": "live"})
    sink = EventSink("a", store)
    for _ in range(30):
        sink.emit("retrieval_started", "retrieval", status="running")
    sink.emit("run_completed", "run")
    events = store.events("a")
    assert len(events) == 20
    assert [e["sequence"] for e in events] == list(range(1, 21))
    assert events[-2]["type"] == "recording_limit_reached"
    assert events[-1]["type"] == "run_completed"
    store.finish("a", {"status": "completed"})
    store.create("b", {})
    assert store.events("b") == []
    store.recover_interrupted()
    assert store.get("b")["status"] == "failed"
    store.create("c", {})
    with pytest.raises(KeyError):
        store.get("a")


def test_failed_fetch_is_diagnostic_and_does_not_claim_ingestion(tmp_path):
    store = RunStore(replace(Settings(), data_dir=tmp_path))
    store.create("a", {})
    sink = EventSink("a", store)
    sink("tool_completed", "ingestion", {"tool": "add_web_content", "result": {"status": "error", "error_message": "fetch failed"}}, "completed")
    events = store.events("a")
    assert events[0]["visibility"] == "diagnostic"
    assert events[1]["status"] == "skipped"
    assert not any(e["type"] == "content_ingested" for e in events)


def test_payload_is_bounded_and_secrets_and_url_credentials_are_omitted():
    value = bounded({"api_key": "secret", "query_embedding": [1],
                     "url": "https://user:pass@example.edu/path?token=private", "items": ["x" * 10000] * 100})
    raw = json.dumps(value)
    assert len(raw.encode()) <= 48000
    assert "private" not in raw and "user:pass" not in raw and "api_key" not in raw
    assert value["url"] == "https://example.edu/path"


def test_confidence_event_exposes_existing_thresholds_without_changing_score(tmp_path):
    store = RunStore(replace(Settings(), data_dir=tmp_path))
    store.create("a", {})
    sink = EventSink("a", store)
    result = {"status": "success", "confidence_score": .668, "confidence_level": "medium"}
    sink("tool_completed", "confidence", {"tool": "evaluate", "result": result}, "completed")
    payload = store.events("a")[0]["payload"]
    assert payload["result"] == result
    assert payload["thresholds"]["high"] == .78
    assert payload["metric"] == "evidence_confidence"


def test_actual_strategy_calculation_is_identical_with_observer():
    cls = definitions("rag_agent/utils/ContentUtils.py", {"ContentUtils"}, {
        "K": K, "MIN_RESULTS": MIN_RESULTS, "RELEVANT_CHUNK_THRESHOLD": RELEVANT_CHUNK_THRESHOLD,
        "RetrievalResult": RetrievalResult, "statistics": statistics, "os": os,
        "extract_hardiness_zone_for_location": lambda _: None,
    })["ContentUtils"]
    content = cls.__new__(cls)
    content.embedding_fn = object()
    content.tokenizer = SimpleNamespace(encode=lambda text, **kwargs: text, decode=lambda text, **kwargs: text)
    store = SimpleNamespace(collection_name="mirage_base", search=lambda **kwargs: [
        {"text": "a", "metadata": {}, "similarity": .83}, {"text": "b", "metadata": {}, "similarity": .79}])
    def retrieve():
        return content.retrieve_with_priority_filters(query="corn", store=store,
            use_progressive_filtering=False, query_embedding=[1.]).to_tool_dict()
    original = retrieve()
    events = []
    with observe(lambda *args: events.append(args)):
        observed = retrieve()
    assert original == observed
    evaluated = next(e[2] for e in events if e[0] == "strategy_evaluated")
    assert evaluated["similarities"] == [.83, .79]
    assert evaluated["normalized_score"] == original["strategy_diagnostics"][0]["normalized_score"]
    assert evaluated["collection"] == "mirage_base"
