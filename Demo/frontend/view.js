import { FEATURES, STAGES, formatScore, groups, humanize, lastEvent, latestResult, safeUrl, signed, stageSummary, statusLabel } from "./model.js";

export const $ = id => document.getElementById(id);
export function el(tag, className = "", text = null) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== null && text !== undefined) node.textContent = String(text);
  return node;
}

function replacePreservingDetails(target, children) {
  const opened = new Set([...target.querySelectorAll("details[open]")].map(node => node.dataset.disclosure));
  target.replaceChildren(...children);
  for (const node of target.querySelectorAll("details")) {
    if (opened.has(node.dataset.disclosure)) node.open = true;
  }
}

function section(title, content) {
  const node = el("section", "detail-section");
  node.append(el("h4", "", title));
  node.append(typeof content === "string" ? el("p", "", content) : content);
  return node;
}

function disclosure(title, text, key) {
  const node = el("details", "query-transform");
  node.dataset.disclosure = key;
  node.append(el("summary", "", title), el("p", "", text));
  return node;
}

function metrics(items) {
  const grid = el("div", "metric-grid");
  for (const [label, value] of items) {
    const card = el("div", "metric");
    card.append(el("strong", "", value ?? "—"), el("span", "", label));
    grid.append(card);
  }
  return grid;
}

function link(text, url) {
  const safe = safeUrl(url);
  if (!safe) return el("span", "", text);
  const anchor = el("a", "", text);
  anchor.href = safe;
  anchor.target = "_blank";
  anchor.rel = "noopener noreferrer";
  return anchor;
}

export function renderFeatures(preset) {
  $("feature-list").replaceChildren(...FEATURES.map(([key, label]) => {
    const item = el("li", preset[key] ? "feature-on" : "");
    const icon = el("span", "feature-symbol", preset[key] ? "✓" : "−");
    icon.setAttribute("aria-hidden", "true");
    item.append(icon, document.createTextNode(`${label} · ${preset[key] ? "on" : "off"}`));
    return item;
  }));
}

export function renderDatabase(database, lastSuccess = {}) {
  const cards = [];
  for (const [role, item] of Object.entries(database || {})) {
    const card = el("div", "database-card");
    const top = el("div", "database-card-top");
    top.append(el("span", "database-name", item.name), el("span", "role-label", item.read_only ? "READ ONLY" : "PERSISTENT"));
    const bottom = el("div", "database-card-bottom");
    bottom.append(el("span", "collection-count", item.points == null ? "— chunks" : `${item.points.toLocaleString()} chunks`),
      el("span", "collection-status", item.reachable && item.compatible ? "✓ Connected" : item.reachable ? "! Incompatible" : "○ Unavailable"));
    card.append(top, bottom);
    if (lastSuccess[role]) card.append(el("p", "database-time", `Last successful refresh ${new Date(lastSuccess[role]).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}`));
    cards.push(card);
  }
  $("database-cards").replaceChildren(...cards);
}

export function renderHealth(health, error = null) {
  const checks = Object.entries(health?.checks || {});
  const unavailable = checks.filter(([, value]) => value.required !== false && !value.ready);
  $("health-summary").textContent = error ? "Services unavailable · refresh to try again" : !health ? "Checking service readiness…"
    : health.ready ? "Services ready for the selected preset" : `${unavailable.length || "Required"} service ${unavailable.length === 1 ? "check needs" : "checks need"} attention`;
  $("health-checks").replaceChildren(...checks.map(([name, value]) => {
    const card = el("div", `health-check ${!value.ready && value.required !== false ? "unavailable" : ""}`);
    const heading = el("h3", "", { rag: "RAG model", generation: "Generation model", base: "Curated knowledge", runtime: "Demo runtime", crop_dictionary: "Crop dictionary", dependencies: "Inference libraries", embedding: "Embedding model", web_search: "Web search", asset_storage: "Image storage" }[name] || humanize(name));
    heading.append(el("span", "check-state", value.ready ? "✓ Ready" : value.required === false ? "Optional" : "Not ready"));
    card.append(heading, el("p", "", value.model || value.message || value.error || (value.missing?.length ? `Missing: ${value.missing.join(", ")}` : value.name || "Status checked")));
    return card;
  }));
}

export function renderContext(run) {
  const target = $("query-context");
  target.hidden = !run;
  if (!run) return target.replaceChildren();
  const children = [el("h3", "", "Original question"), el("p", "original-question", run.input.question || "Question unavailable")];
  const meta = el("div", "context-meta");
  for (const text of [run.input.state, run.input.county, run.input.month_year, humanize(run.input.task_type)]) {
    if (text) meta.append(el("span", "context-tag", text));
  }
  children.push(meta);
  const captured = run.metadata.config || run.result?.config;
  if (captured?.name) children.push(disclosure(`Run preset: ${captured.name}`,
    (captured.instruction_preset_id ? `Based on: ${captured.id}\nInstructions: ${captured.instruction_preset_id}\n` : "") +
    FEATURES.map(([key, label]) => `${label}: ${captured[key] ? "enabled" : "disabled"}`).join("\n"), "captured-preset"));
  if (run.images?.length) {
    const images = el("div", "context-images");
    run.images.forEach((url, index) => {
      const image = el("img");
      image.src = url;
      image.alt = `Original input image ${index + 1}`;
      images.append(image);
    });
    children.push(images);
  }
  const enrichment = lastEvent(run, "query_enrichment_completed");
  const enrichmentSkip = lastEvent(run, "query_enrichment_skipped");
  if (enrichment) children.push(disclosure(enrichment.payload.changed ? "Crop-enriched question" : "Crop enrichment · question unchanged", enrichment.payload.query || "", "crop-query"));
  else if (enrichmentSkip) children.push(el("p", "field-help", `Crop enrichment: ${statusLabel("skipped", enrichmentSkip.payload.reason).toLowerCase()}.`));
  const visual = lastEvent(run, "visual_attributes_completed");
  const visualSkip = lastEvent(run, "visual_attributes_skipped");
  if (visual) children.push(disclosure("Visual observations · retrieval only", visual.payload.attributes || "No attributes returned", "visual-attributes"));
  else if (run.input.task_type === "identification" && visualSkip) children.push(el("p", "field-help", `Visual observations were skipped${visualSkip.payload.reason === "no_images" ? ": no image supplied" : "; retrieval continued without attributes"}.`));
  const prepared = lastEvent(run, "query_prepared");
  if (prepared?.payload.retrieval_query) children.push(disclosure("Actual retrieval input", prepared.payload.retrieval_query, "retrieval-query"));
  const search = lastEvent(run, "web_search_query_prepared");
  if (search?.payload.query) children.push(disclosure("Actual web search query", search.payload.query, "web-query"));
  replacePreservingDetails(target, children);
}

export function renderTimeline(run, onSelect) {
  const rows = run ? groups(run) : [];
  $("timeline-empty").hidden = Boolean(run);
  $("timeline").hidden = !run;
  $("event-count").textContent = !run ? "No active question" : `${run.events.filter(event => event.visibility !== "diagnostic").length} events · ${rows.length} stages`;
  const title = !run ? "Ready" : { running: "Running", completed: "Completed", failed: "Failed", insufficient_evidence: "Insufficient evidence" }[run.status] || humanize(run.status);
  $("run-state").textContent = title;
  $("run-state").className = `badge ${run?.status === "running" ? "active-badge" : run?.status === "failed" ? "error-badge" : "quiet-badge"}`;
  $("follow-latest").disabled = !run;
  $("follow-latest").setAttribute("aria-pressed", String(run?.follow !== false));
  $("follow-latest").textContent = run?.follow === false ? "Follow latest" : "Following latest";
  if (run?.follow && rows.length) run.selected = rows.at(-1).key;
  const focusKey = document.activeElement?.dataset.stageKey;
  const started = run?.events[0]?.timestamp;
  const nodes = rows.map(row => {
    const item = el("li", `timeline-item status-${row.status}`);
    item.append(el("span", "stage-icon", { completed: "✓", running: "◉", skipped: "−", failed: "!" }[row.status] || "○"));
    const button = el("button", `stage-button ${run.selected === row.key ? "selected" : ""}`);
    button.type = "button";
    button.dataset.stageKey = row.key;
    button.setAttribute("aria-expanded", String(run.selected === row.key));
    button.setAttribute("aria-controls", "stage-details");
    const top = el("div", "stage-top");
    const elapsed = started ? Math.max(0, (new Date(row.timestamp) - new Date(started)) / 1000) : 0;
    top.append(el("span", "stage-title", STAGES[row.stage] || humanize(row.stage)), el("span", "stage-time", `+${elapsed.toFixed(1)}s`));
    const meta = el("div", "stage-meta");
    const reason = row.events.at(-1).payload?.reason;
    meta.append(el("span", "stage-status", statusLabel(row.status, reason)));
    if (row.iteration > 0) meta.append(el("span", "", `Attempt ${row.iteration}`));
    button.append(top, el("p", "stage-summary", stageSummary(row)), meta);
    button.addEventListener("click", () => onSelect(row.key));
    item.append(button);
    return item;
  });
  if (run && !rows.length) nodes.push(el("li", "detail-intro", "Waiting for the first pipeline event…"));
  $("timeline").replaceChildren(...nodes);
  if (focusKey) [...$("timeline").querySelectorAll("button")].find(button => button.dataset.stageKey === focusKey)?.focus({ preventScroll: true });
  if (run?.follow) $("timeline").scrollTop = $("timeline").scrollHeight;
  return rows.find(row => row.key === run?.selected);
}

function sourceCards(sources, prefix = "source") {
  const container = el("div");
  sources.forEach((source, index) => {
    const metadata = source.metadata || source;
    const card = el("article", "source-card");
    const heading = el("h4");
    const url = metadata.url || source.url;
    heading.append(link(metadata.title || metadata.source_id || `Evidence passage ${index + 1}`, url));
    card.append(heading);
    if (url && safeUrl(url)) card.append(el("p", "", new URL(url).hostname));
    const text = source.text || source.snippet || "";
    if (text) {
      card.append(el("p", "", text.length > 320 ? `${text.slice(0, 320)}…` : text));
      if (text.length > 320) card.append(disclosure("Read full passage", text, `${prefix}-${index}`));
    }
    const meta = el("div", "source-meta");
    for (const label of [source.retrieval_source ? `Collection: ${source.retrieval_source}` : null,
      typeof source.similarity === "number" ? `Similarity ${formatScore(source.similarity)}` : null,
      metadata.month_year, metadata.source_type]) {
      if (label) meta.append(el("span", "", label));
    }
    card.append(meta);
    container.append(card);
  });
  return container;
}

function retrievalDetails(row) {
  const content = [];
  const result = latestResult(row);
  const query = row.events.find(event => event.type === "retrieval_started")?.payload.arguments?.query;
  if (query) content.push(disclosure("Query used by this retrieval", query, `retrieval-${row.key}`));
  const evaluated = row.events.filter(event => event.type === "strategy_evaluated").map(event => event.payload);
  const selections = row.events.filter(event => event.type === "strategy_selected").map(event => event.payload);
  if (result.strategy) content.push(metrics([["Selected strategy (merged evidence)", humanize(result.strategy)], ["Relevant chunks", result.relevant_count ?? result.results?.length]]));
  const collections = new Map();
  for (const diagnostic of evaluated.length ? evaluated : result.strategy_diagnostics || []) {
    const name = diagnostic.collection || "Retrieval diagnostics";
    if (!collections.has(name)) collections.set(name, []);
    collections.get(name).push(diagnostic);
  }
  for (const [collection, strategies] of collections) {
    const wrap = el("div", "strategy-table-wrap");
    const table = el("table", "strategy-table");
    table.append(el("caption", "", collection));
    const head = el("thead");
    const tr = el("tr");
    for (const name of ["Strategy", "Score", "Relevant", "Decision"]) {
      const th = el("th", "", name); th.scope = "col"; tr.append(th);
    }
    head.append(tr); table.append(head);
    const body = el("tbody");
    for (const diagnostic of strategies) {
      const strategy = diagnostic.strategy_name || diagnostic.strategy;
      const chosen = selections.some(selection => selection.collection === collection && selection.strategy === strategy);
      const line = el("tr", chosen ? "selected-strategy" : "");
      const name = el("td", "", humanize(strategy));
      if (diagnostic.reason && diagnostic.reason !== "valid_retrieval") name.append(el("span", "table-detail", humanize(diagnostic.reason)));
      line.append(name, el("td", "", formatScore(diagnostic.normalized_score)), el("td", "", diagnostic.relevant_count ?? "—"),
        el("td", "", chosen ? "Selected" : diagnostic.eligible === true ? "Eligible" : diagnostic.eligible === false ? "Rejected" : "Evaluated"));
      body.append(line);
    }
    table.append(body); wrap.append(table); content.push(wrap);
    content.push(disclosure("Inspect raw cosine similarities", strategies.map(diagnostic => `${humanize(diagnostic.strategy_name)}: ${(diagnostic.similarities || []).map(formatScore).join(", ") || "No hits"}`).join("\n"), `similarities-${collection}`));
  }
  if (result.results?.length) content.push(section("Retrieved evidence", sourceCards(result.results, row.key)));
  else if (!collections.size) content.push(el("p", "detail-intro", row.status === "running" ? "Strategy scores will appear as each candidate is evaluated." : "No retrieval diagnostics were recorded for this stage."));
  if (result.strategy === "no_results") content.push(el("p", "threshold-note", "No strategy returned enough relevant evidence."));
  return content;
}

function confidenceDetails(row, run) {
  const event = [...row.events].reverse().find(item => item.type === "confidence_completed");
  const result = event?.payload.result;
  if (!result) return [el("p", "detail-intro", "Waiting for the evidence-confidence evaluation.")];
  const diagnostic = result.diagnostics || {};
  const content = [metrics([["Evidence-confidence metric", formatScore(result.confidence_score)], ["Classification", humanize(result.confidence_level)]]),
    el("p", "field-help", "This is the project’s evidence-confidence metric, not a calibrated probability.")];
  const components = el("div", "component-list");
  for (const [key, label] of [["similarity_score", "Similarity"], ["coverage_score", "Coverage"], ["consistency_score", "Consistency"], ["scope_score", "Scope"]]) {
    if (typeof diagnostic[key] !== "number") continue;
    const line = el("div", "component-row");
    const meter = el("meter"); meter.min = 0; meter.max = 1; meter.value = diagnostic[key]; meter.setAttribute("aria-label", `${label} component`);
    line.append(el("span", "", label), meter, el("strong", "", formatScore(diagnostic[key])));
    components.append(line);
  }
  if (components.children.length) content.push(section("Confidence components", components));
  const thresholds = event.payload.thresholds;
  if (thresholds) content.push(el("p", "threshold-note", `High ≥ ${formatScore(thresholds.high)} · Medium ≥ ${formatScore(thresholds.medium)}\nRelevant chunk similarity ≥ ${formatScore(thresholds.relevant_chunk)} · Minimum ${thresholds.minimum_relevant_chunks} relevant chunks`));
  if (diagnostic.reason) content.push(section("Assessment", humanize(diagnostic.reason)));
  if (diagnostic.relevant_count != null) content.push(section("Evidence evaluated", `${diagnostic.relevant_count} relevant chunks out of ${diagnostic.returned_count ?? diagnostic.num_chunks ?? "—"} returned.`));
  const nextConfidence = run.events.find(item => item.type === "confidence_started" && item.sequence > event.sequence)?.sequence ?? Infinity;
  const searched = run.events.some(item => item.type === "web_search_started" && item.sequence > event.sequence && item.sequence < nextConfidence);
  content.push(section("Search decision", searched ? "Web search was subsequently invoked by the agent." : run.status === "running" && nextConfidence === Infinity ? "Waiting for the agent’s next action." : "No subsequent web-search invocation was recorded for this assessment."));
  return content;
}

export function renderStage(run, row) {
  $("details-empty").hidden = Boolean(run);
  $("stage-details").hidden = !row;
  if (!row) return $("stage-details").replaceChildren();
  const header = el("div", "detail-heading");
  header.append(el("h3", "", STAGES[row.stage] || humanize(row.stage)), el("span", "badge quiet-badge", statusLabel(row.status, row.events.at(-1).payload?.reason)));
  const content = [el("p", "detail-eyebrow", `SELECTED STAGE${row.iteration ? ` / ATTEMPT ${row.iteration}` : ""}`), header, el("p", "detail-intro", stageSummary(row))];
  const result = latestResult(row);
  const latest = row.events.at(-1).payload || {};
  if (row.stage === "retrieval") content.push(...retrievalDetails(row));
  else if (row.stage === "confidence") content.push(...confidenceDetails(row, run));
  else if (row.stage === "web_search") {
    const search = row.events.find(event => event.type === "web_search_query_prepared")?.payload;
    const requested = row.events.find(event => event.type === "web_search_started")?.payload.arguments;
    if (search?.query || requested?.query) content.push(section(search ? "Actual search query" : "Requested search query", search?.query || requested.query));
    if (search) content.push(section("Domain filtering", search.allowed_domains?.length ? search.allowed_domains.join(", ") : search.domain_filter_enabled ? "Enabled; no location-specific domains were available." : "Disabled by the preset."));
    if (result.results?.length) content.push(section("Returned web sources", sourceCards(result.results, row.key)));
  } else if (row.stage === "ingestion") {
    if (result.status === "success") {
      content.push(metrics([["Chunks added", result.chunks_added ?? "—"], ["Outcome", "Success"]]));
      if (result.url) content.push(section("Ingested source", link(result.title || result.url, result.url)));
    }
    if (run.result?.runtime_after != null) content.push(section("Runtime after this query", `${run.result.runtime_after.toLocaleString()} stored chunks · ${signed(run.result.runtime_delta)} during the query`));
  } else if (row.stage === "visual_attributes" && latest.attributes) content.push(section("Visible observations", latest.attributes), el("p", "field-help", "Observations enrich retrieval and are not a verified identification. The generation model also receives the actual input image."));
  else if (row.stage === "query_enrichment" && latest.query) content.push(section(latest.changed ? "Crop-enriched question" : "Unchanged question", latest.query));
  else if (row.stage === "keyword_extraction" && result.keywords) content.push(section("Extracted search keywords", Array.isArray(result.keywords) ? result.keywords.join(", ") : String(result.keywords)));
  else if (row.stage === "database") content.push(metrics([["Before", latest.before ?? "—"], ["After", latest.after ?? "—"], ["Point delta", signed(latest.delta)]]));
  else if (row.stage === "query") content.push(el("p", "field-help", "The original question and any observed transformations are shown above."));
  else if (row.stage === "generation") content.push(el("p", "field-help", row.status === "completed" ? "The generated answer and its retrieved evidence are shown below." : row.status === "running" ? "The generation endpoint is using the actual question, images, and accepted evidence." : "No final answer is produced for a skipped generation stage."));
  replacePreservingDetails($("stage-details"), content);
}

function inlineText(node, text) {
  // A deliberately small text-only Markdown renderer. No HTML is interpreted.
  const tokens = String(text).split(/(\*\*[^*\n]+\*\*|`[^`\n]+`|\[[^\]\n]+\]\(https?:\/\/[^\s)]+\))/g);
  for (const token of tokens) {
    if (token.startsWith("**") && token.endsWith("**")) node.append(el("strong", "", token.slice(2, -2)));
    else if (token.startsWith("`") && token.endsWith("`")) node.append(el("code", "", token.slice(1, -1)));
    else {
      const match = token.match(/^\[([^\]]+)\]\((.+)\)$/);
      node.append(match ? link(match[1], match[2]) : document.createTextNode(token));
    }
  }
}

export function renderAnswer(text) {
  const container = el("div", "answer-text");
  let paragraph = null, list = null;
  for (const line of String(text).split("\n")) {
    if (!line.trim()) { paragraph = null; list = null; continue; }
    const heading = line.match(/^#{1,6}\s+(.+)$/);
    const item = line.match(/^\s*(?:[-*]|\d+\.)\s+(.+)$/);
    if (heading) { const node = el("h4"); inlineText(node, heading[1]); container.append(node); paragraph = list = null; }
    else if (item) {
      if (!list) { list = el(/^\s*\d/.test(line) ? "ol" : "ul"); container.append(list); }
      const node = el("li"); inlineText(node, item[1]); list.append(node); paragraph = null;
    } else {
      if (!paragraph) { paragraph = el("p"); container.append(paragraph); } else paragraph.append(document.createElement("br"));
      inlineText(paragraph, line); list = null;
    }
  }
  return container;
}

export function renderResult(run) {
  const target = $("result");
  const generation = run && lastEvent(run, "generation_completed");
  const insufficient = run && (run.status === "insufficient_evidence" || lastEvent(run, "insufficient_evidence"));
  const failed = run?.status === "failed";
  const answer = run?.result?.answer || generation?.payload.answer;
  target.hidden = !(insufficient || failed || answer);
  if (target.hidden) return target.replaceChildren();
  const children = [];
  if (insufficient || failed) {
    const message = el("div", `outcome-message ${failed ? "failed" : ""}`);
    const error = run.result?.error || lastEvent(run, "stage_failed")?.payload || lastEvent(run, "run_failed")?.payload.error;
    message.append(el("h3", "", insufficient ? "More reliable evidence is needed" : "The question could not be completed"),
      el("p", "", insufficient ? run.result?.message || lastEvent(run, "insufficient_evidence")?.payload.message || "Try adding a clearer image, more symptoms, or more precise location."
        : error?.message || "Check service readiness and try the question again."));
    children.push(message);
  } else {
    children.push(el("p", "detail-eyebrow", "EVIDENCE-INFORMED RESPONSE"), el("h3", "", "The answer"), renderAnswer(answer));
    const sources = run.result?.sources || generation?.payload.sources || [];
    if (sources.length) children.push(section("Evidence supplied to generation", sourceCards(sources, "answer-source")),
      el("p", "field-help", "These passages were supplied as context. Individual answer statements are not mapped to source citations."));
  }
  const activity = run.result?.tool_activity || lastEvent(run, "run_completed")?.payload.tool_activity;
  if (activity && Object.keys(activity).length) {
    const list = el("div", "tool-activity");
    for (const [stage, value] of Object.entries(activity)) {
      const row = el("div");
      row.append(el("span", "", STAGES[stage] || humanize(stage)), el("strong", "", value.invoked ? "Invoked" : value.enabled ? "Enabled · not invoked" : "Disabled"));
      list.append(row);
    }
    children.push(section("Pipeline activity", list));
  }
  if (run.events.some(event => event.type === "recording_limit_reached")) children.push(el("p", "threshold-note", "The event recording limit was reached. Some intermediate events were not retained."));
  replacePreservingDetails(target, children);
}

export function renderDiagnostics(run) {
  const diagnostics = run?.events.filter(event => event.visibility === "diagnostic") || [];
  $("diagnostics").hidden = !diagnostics.length;
  $("diagnostic-count").textContent = `(${diagnostics.length})`;
  $("diagnostic-content").replaceChildren(...diagnostics.map(event => el("p", "", `#${event.sequence} · ${STAGES[event.stage] || event.stage}: ${event.payload.reason || humanize(event.type)}`)));
}
