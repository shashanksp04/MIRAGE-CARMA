// Pure event folding shared by the browser and dependency-free Node tests.
export const STAGES = {
  query: "Question preparation", query_enrichment: "Crop query enrichment",
  visual_attributes: "Visual observations", retrieval: "Evidence retrieval",
  confidence: "Evidence confidence", keyword_extraction: "Search keywords",
  web_search: "Web search", ingestion: "Knowledge augmentation",
  generation: "Final response", database: "Runtime knowledge", rag: "Evidence assessment",
  run: "Run status",
};

export const FEATURES = [
  ["db_on", "Curated knowledge"], ["crop_dict_on", "Crop dictionary"],
  ["progressive_filtering_on", "Progressive retrieval"], ["confidence_on", "Confidence evaluation"],
  ["web_search_on", "Web search"], ["domain_filter_on", "Domain filtering"],
  ["ingestion_loop_on", "Runtime ingestion"],
];

export function newRun(runId, input = {}, metadata = {}) {
  return { runId, input, metadata, events: [], lastSequence: 0, selected: null,
    follow: true, status: "running", result: null, images: [] };
}

export function acceptEvent(run, event) {
  if (event.run_id !== run.runId || !Number.isInteger(event.sequence)) return false;
  if (event.sequence <= run.lastSequence) return false;
  if (event.sequence !== run.lastSequence + 1) throw new Error("Event sequence gap; reconnecting to recover missed events.");
  run.events.push(event);
  run.lastSequence = event.sequence;
  if (event.type === "run_failed") run.status = "failed";
  if (event.type === "run_completed") run.status = event.payload.outcome || "completed";
  return true;
}

export function groups(run) {
  const rows = [];
  const stages = new Map();
  for (const event of run.events) {
    if (event.visibility === "diagnostic") continue;
    if (event.stage === "run" && !["stage_failed", "recording_limit_reached"].includes(event.type)) continue;
    const standalone = event.stage === "database" || event.type === "recording_limit_reached";
    const key = standalone ? `event:${event.sequence}` : `${event.stage}:${event.iteration}`;
    let row = stages.get(key);
    if (!row) {
      row = { key, stage: event.stage, iteration: event.iteration, events: [], status: event.status,
        firstSequence: event.sequence, timestamp: event.timestamp };
      stages.set(key, row);
      rows.push(row);
    }
    row.events.push(event);
    // Candidate evaluations must not mark their enclosing retrieval complete.
    const intermediate = ["strategy_evaluated", "strategy_selected", "web_search_query_prepared"].includes(event.type);
    if (!intermediate) row.status = event.status;
  }
  if (["failed", "completed", "insufficient_evidence"].includes(run.status)) {
    for (const row of rows) {
      if (row.status === "running") row.status = run.status === "failed" ? "failed" : "skipped";
    }
  }
  return rows;
}

export function lastEvent(run, type) {
  return run.events.findLast(event => event.type === type);
}

export function statusLabel(status, reason) {
  if (status === "skipped") {
    if (reason === "disabled") return "Disabled";
    if (reason === "not_invoked") return "Not invoked";
    return "Skipped";
  }
  return { running: "Running", completed: "Completed", failed: "Failed",
    insufficient_evidence: "Insufficient evidence", pending: "Waiting" }[status] || status;
}

export function latestResult(row) {
  return [...row.events].reverse().find(event => event.payload?.result)?.payload.result || {};
}

export function stageSummary(row) {
  const event = row.events.at(-1);
  const payload = event.payload || {};
  const result = latestResult(row);
  if (event.type === "recording_limit_reached") return "The event recording limit was reached. See the final result for the outcome.";
  if (row.status === "running") return "The pipeline is working on this stage.";
  if (row.status === "failed") return payload.message || "This stage could not complete. Check service readiness.";
  if (row.status === "skipped") {
    return { disabled: "Disabled by this preset.", not_invoked: "Enabled, but not invoked for this question.",
      no_images: "No image was supplied.", not_applicable: "Not applicable to this question.",
      insufficient_evidence: "Final generation was skipped because reliable evidence was insufficient.",
    }[payload.reason] || (payload.successful === false ? "No successful content was returned; see diagnostics." : "This stage was not applied.");
  }
  switch (row.stage) {
    case "query": return "Original question and retrieval input are available.";
    case "query_enrichment": return payload.changed ? "Crop context was added to the question." : "Question retained without a crop insertion.";
    case "visual_attributes": return "Visible attributes prepared for evidence retrieval.";
    case "retrieval": return result.strategy ? `${humanize(result.strategy)} · ${result.relevant_count ?? result.results?.length ?? 0} relevant chunks` : "Inspect the evaluated strategies and retrieved evidence.";
    case "confidence": return result.confidence_level ? `${humanize(result.confidence_level)} confidence · ${formatScore(result.confidence_score)}` : "Evidence confidence was evaluated.";
    case "keyword_extraction": return `${result.keywords?.length ?? 0} search keywords extracted.`;
    case "web_search": return `${result.results?.length ?? 0} source results returned.`;
    case "ingestion": return `${result.chunks_added ?? 0} chunks added to runtime knowledge.`;
    case "database": return payload.after != null ? `${payload.after.toLocaleString()} chunks · ${signed(payload.delta)} this update` : `${payload.before?.toLocaleString() ?? "—"} chunks before the query`;
    case "generation": return "Response generated using the accepted evidence.";
    case "rag": return payload.message || "Evidence assessment completed.";
    default: return humanize(event.type);
  }
}

export function humanize(value) {
  if (!value) return "Not available";
  if (value === "semantic_only") return "Semantic only";
  return String(value).replaceAll("_", " ").replaceAll("+", " + ").replace(/^./, char => char.toUpperCase());
}

export function formatScore(value) {
  return typeof value === "number" && Number.isFinite(value) ? value.toFixed(3) : "—";
}

export function signed(value) {
  return typeof value === "number" ? `${value >= 0 ? "+" : ""}${value.toLocaleString()}` : "—";
}

export function safeUrl(value) {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}
