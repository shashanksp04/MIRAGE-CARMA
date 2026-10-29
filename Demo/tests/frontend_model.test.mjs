import assert from "node:assert/strict";
import test from "node:test";
import { acceptEvent, groups, newRun, safeUrl, stageSummary, statusLabel } from "../frontend/model.js";
import { parseFrame } from "../frontend/network.js";

function event(sequence, type, stage, iteration = 1, payload = {}, status = "completed") {
  return { schema_version: 1, run_id: "test-run", sequence, timestamp: new Date().toISOString(),
    type, stage, iteration, payload, status, visibility: "primary" };
}

test("event folding isolates runs, deduplicates reconnects and refuses sequence gaps", () => {
  const run = newRun("test-run");
  assert.equal(acceptEvent(run, event(1, "run_started", "run")), true);
  assert.equal(acceptEvent(run, event(1, "run_started", "run")), false);
  assert.equal(acceptEvent(run, { ...event(2, "query_received", "query"), run_id: "other" }), false);
  assert.throws(() => acceptEvent(run, event(3, "retrieval_started", "retrieval")), /sequence gap/);
  assert.equal(run.lastSequence, 1);
});

test("repeated retrieval attempts stay separate and candidate events do not complete running retrieval", () => {
  const run = newRun("test-run");
  acceptEvent(run, event(1, "retrieval_started", "retrieval", 1, {}, "running"));
  acceptEvent(run, event(2, "strategy_evaluated", "retrieval", 1, { normalized_score: .71 }));
  assert.equal(groups(run)[0].status, "running");
  acceptEvent(run, event(3, "retrieval_completed", "retrieval", 1, { result: { strategy: "semantic_only", relevant_count: 2 } }));
  acceptEvent(run, event(4, "retrieval_started", "retrieval", 2, {}, "running"));
  const rows = groups(run);
  assert.equal(rows.length, 2);
  assert.equal(rows[1].status, "running");
  assert.equal(stageSummary(rows[0]), "Semantic only · 2 relevant chunks");
});

test("routine diagnostics stay out of the timeline and skipped/disabled meanings stay distinct", () => {
  const run = newRun("test-run");
  acceptEvent(run, { ...event(1, "tool_diagnostic", "ingestion"), visibility: "diagnostic" });
  acceptEvent(run, event(2, "augmentation_skipped", "web_search", 0, { reason: "not_invoked" }, "skipped"));
  assert.equal(groups(run).length, 1);
  assert.equal(statusLabel("skipped", "disabled"), "Disabled");
  assert.equal(statusLabel("skipped", "not_invoked"), "Not invoked");
});

test("database updates retain chronological instances and insufficient evidence remains informational", () => {
  const run = newRun("test-run");
  acceptEvent(run, event(1, "runtime_count_updated", "database", 0, { before: 4 }));
  acceptEvent(run, event(2, "runtime_count_updated", "database", 0, { before: 4, after: 6, delta: 2 }));
  acceptEvent(run, event(3, "run_completed", "run", 1, { outcome: "insufficient_evidence" }));
  assert.equal(groups(run).length, 2);
  assert.equal(run.status, "insufficient_evidence");
});

test("SSE parser accepts multiline data and ignores heartbeat comments", () => {
  assert.equal(parseFrame(": keep-alive"), null);
  assert.deepEqual(parseFrame('id: test-run:1\nevent: query_received\ndata: {"sequence":\ndata: 1}'), { sequence: 1 });
});

test("source links reject executable, credentialed, and malformed URLs", () => {
  assert.equal(safeUrl("javascript:alert(1)"), null);
  assert.equal(safeUrl("data:text/html,<script>"), null);
  assert.equal(safeUrl("https://user:password@example.edu"), null);
  assert.equal(safeUrl("https://example.edu/evidence"), "https://example.edu/evidence");
});
