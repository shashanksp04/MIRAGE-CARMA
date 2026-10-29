"""Typed, bounded event payloads derived from actual action boundaries."""
from collections import defaultdict
from datetime import datetime, timezone
import json
import logging
import re
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field

LOG = logging.getLogger(__name__)
PRIVATE_KEYS = {"api_key", "authorization", "password", "token", "secret", "query_embedding",
                "embedding_cache", "agent_message", "raw_text_preview", "traceback", "error_message"}


def clean(value, depth=0):
    """Bound nested data, omit operational diagnostics and strip URL credentials."""
    if depth > 8:
        return "[depth limit]"
    if isinstance(value, dict):
        return {str(key): clean(item, depth + 1) for key, item in list(value.items())[:80]
                if str(key).lower() not in PRIVATE_KEYS}
    if isinstance(value, (list, tuple)):
        return [clean(item, depth + 1) for item in value[:80]]
    if isinstance(value, str):
        def safe_url(match):
            try:
                url = urlsplit(match.group())
                host = url.netloc.rsplit("@", 1)[-1]
                query = urlencode([(key, item) for key, item in parse_qsl(url.query, keep_blank_values=True)
                                   if key.lower() not in PRIVATE_KEYS and "token" not in key.lower()
                                   and "signature" not in key.lower() and "credential" not in key.lower()])
                return urlunsplit((url.scheme, host, url.path, query, ""))
            except ValueError:
                return "[invalid URL]"
        text = re.sub(r"https?://[^\s<>\"]+", safe_url, value)
        return text[:8000] + ("…[truncated]" if len(text) > 8000 else "")
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:200]


def bounded(value, limit=48000):
    sanitized = clean(value)
    if len(json.dumps(sanitized, ensure_ascii=False).encode()) <= limit:
        return sanitized
    # Keep useful metadata; never truncate serialized JSON into invalid JSON.
    if isinstance(sanitized, dict):
        result = {"payload_truncated": True}
        for key, item in sanitized.items():
            candidate = {**result, key: item}
            if len(json.dumps(candidate, ensure_ascii=False).encode()) <= limit:
                result[key] = item
        return result
    return {"payload_truncated": True}


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    run_id: str
    sequence: int = Field(ge=1)
    timestamp: str
    type: str
    stage: str
    iteration: int = Field(ge=0)
    status: Literal["running", "completed", "skipped", "failed"]
    visibility: Literal["primary", "diagnostic"] = "primary"
    payload: dict


class EventSink:
    def __init__(self, run_id, store):
        self.run_id, self.store = run_id, store
        self.iterations = defaultdict(int)
        self.invoked = set()

    def emit(self, event_type, stage, payload=None, status="completed", visibility="primary"):
        if status == "running":
            self.iterations[stage] += 1
        self.store.append(self.run_id, {
            "timestamp": datetime.now(timezone.utc).isoformat(), "type": event_type,
            "stage": stage, "iteration": self.iterations[stage], "status": status,
            "visibility": visibility, "payload": bounded(payload or {}),
        })

    def __call__(self, event_type, stage, payload, status):
        """Adapter for shared inference observers; no parsing of stdout."""
        if event_type == "tool_started":
            self.invoked.add(stage)
            self.emit(stage + "_started", stage, payload, "running")
        elif event_type == "tool_completed":
            result = payload.get("result") or {}
            if stage == "confidence":
                from rag_agent.tools.confidence_evaluator import (
                    HIGH_CONFIDENCE_THRESHOLD, MEDIUM_CONFIDENCE_THRESHOLD,
                    HARD_RELEVANCE_FLOOR, RELEVANT_CHUNK_THRESHOLD, MIN_RESULTS,
                )
                payload = {**payload, "metric": "evidence_confidence",
                    "thresholds": {"high": HIGH_CONFIDENCE_THRESHOLD,
                        "medium": MEDIUM_CONFIDENCE_THRESHOLD,
                        "hard_relevance_floor": HARD_RELEVANCE_FLOOR,
                        "relevant_chunk": RELEVANT_CHUNK_THRESHOLD,
                        "minimum_relevant_chunks": MIN_RESULTS}}
            if result.get("status") == "error" and stage in {"ingestion", "web_search", "keyword_extraction"}:
                LOG.warning("Run %s %s diagnostics: %s", self.run_id, stage, result)
                self.emit("tool_diagnostic", stage, {"tool": payload["tool"],
                    "reason": "Source fetch or tool operation did not succeed"}, "failed", "diagnostic")
                self.emit(stage + "_completed", stage, {"tool": payload["tool"],
                    "successful": False, "chunks_added": 0} if stage == "ingestion" else
                    {"tool": payload["tool"], "successful": False, "results": []}, "skipped")
            else:
                name = "content_ingested" if stage == "ingestion" else stage + "_completed"
                self.emit(name, stage, payload)
        elif event_type == "tool_failed":
            self.emit(event_type, stage, payload, status)
        else:
            self.emit(event_type, stage, payload, status)


def sse(event):
    return (f"id: {event['run_id']}:{event['sequence']}\n"
            f"event: {event['type']}\n"
            f"data: {json.dumps(event, ensure_ascii=False)}\n\n")
