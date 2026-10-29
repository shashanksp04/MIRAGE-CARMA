import { acceptEvent, lastEvent, newRun, signed } from "./model.js";
import { api, jsonPost, streamEvents } from "./network.js";
import { $, el, renderContext, renderDatabase, renderDiagnostics, renderFeatures, renderHealth, renderResult, renderStage, renderTimeline } from "./view.js";

const state = {
  configurations: null, examples: [], health: null, healthPending: true, healthVersion: 0,
  database: null, lastDatabaseSuccess: {}, databasePending: false,
  busy: false, activeRunId: null, submitting: false, clearing: false,
  run: null, stream: null, files: [], imagePending: false, mode: "examples", selectedExample: null,
  resolvedConfiguration: null,
  defaultPreset: null, allowAutoAttach: true, activityPending: false,
};

function notify(message) {
  $("notice-message").textContent = message;
  $("notice").hidden = !message;
}

function rememberRun(id) {
  try { if (id) sessionStorage.setItem("mirage-active-run", id); else sessionStorage.removeItem("mirage-active-run"); } catch { /* Browser storage is optional. */ }
}

function rememberedRun() {
  try { return sessionStorage.getItem("mirage-active-run"); } catch { return null; }
}

function selectedPreset() {
  return state.configurations?.presets.find(preset => preset.id === $("preset").value);
}

function configurationOverrides() {
  if (!$("custom-configuration").checked) return {};
  const profile = state.configurations.workflow_profiles.find(item => item.id === $("workflow").value);
  const flags = Object.fromEntries(state.configurations.override_fields.slice(2).map(key => [key, profile[key]]));
  return { ...flags, db_on: $("custom-db").checked, crop_dict_on: $("custom-crop").checked };
}

function resetConfigurationControls() {
  const preset = selectedPreset();
  $("custom-configuration").checked = false;
  $("custom-controls").hidden = true;
  $("custom-db").checked = preset.db_on;
  $("custom-crop").checked = preset.crop_dict_on;
  const profile = state.configurations.workflow_profiles.find(item =>
    state.configurations.override_fields.slice(2).every(key => item[key] === preset[key]));
  $("workflow").value = profile.id;
  renderFeatures(preset);
}

function updateControls() {
  const active = state.busy || state.submitting || state.clearing || state.run?.status === "running";
  $("query-fields").disabled = active;
  $("preset").disabled = active || !state.configurations;
  const questionReady = Boolean($("question").value.trim());
  const needsImage = Boolean(state.mode === "examples" && state.selectedExample?.image_required && $("task-type").value === "identification" && !state.files.length);
  $("images").disabled = active || state.imagePending;
  $("run-button").disabled = active || state.imagePending || !state.configurations || state.healthPending || !state.health?.ready || !questionReady || needsImage;
  $("run-button-label").textContent = state.submitting ? "Submitting question…" : active ? "Demo is busy…" : "Run question";
  $("launch-hint").textContent = state.submitting ? "Preparing your input for the pipeline."
    : active ? "One question at a time. The active query is still running."
      : state.imagePending ? "Checking selected images…"
        : state.healthPending ? "Checking demo readiness…"
        : !state.health?.ready ? "Services need attention. Open service details below."
          : needsImage ? "Add a real plant image to use this starter."
            : !questionReady ? "Choose a starting point or enter your question."
              : "Ready to follow your question through the pipeline.";
  $("clear-runtime").disabled = active || !state.database?.runtime?.reachable || !state.database?.runtime?.compatible;
  $("refresh-database").disabled = state.databasePending;
  $("refresh-database").textContent = state.databasePending ? "Refreshing…" : "Refresh";
  $("refresh-health").disabled = state.healthPending;
  $("confirm-clear").disabled = state.clearing || active || $("clear-confirmation").value !== $("clear-token").textContent;
  $("follow-active-run").hidden = !state.activeRunId || state.activeRunId === state.run?.runId;
}

function render() {
  $("execution-mode").textContent = state.run?.mode === "replay" ? "REPLAY · recorded events" : state.run?.mode === "history" ? "Saved execution" : "Live inference";
  renderContext(state.run);
  const selected = renderTimeline(state.run, key => {
    state.run.follow = false;
    state.run.selected = key;
    render();
  });
  renderStage(state.run, selected);
  renderResult(state.run);
  renderDiagnostics(state.run);
  const saved = state.run?.result;
  const count = saved?.runtime_after != null ? { before: saved.runtime_before,
    after: saved.runtime_after, delta: saved.runtime_delta }
    : saved?.runtime_count_error ? null : state.run && lastEvent(state.run, "runtime_count_updated")?.payload;
  $("runtime-delta").hidden = !count || count.after == null;
  if (count?.after != null) $("runtime-delta").replaceChildren(
    el("span", "", saved ? "Displayed query:" : "Latest update:"),
    el("span", "", `Before ${count.before?.toLocaleString() ?? "—"}`),
    el("span", "", `After ${count.after.toLocaleString()}`),
    el("strong", "", `${signed(count.delta)} chunks`));
  updateControls();
}

async function refreshDatabase() {
  if (state.databasePending) return;
  state.databasePending = true;
  updateControls();
  try {
    const data = await api("/api/database/status");
    state.database = data;
    for (const [role, item] of Object.entries(data)) {
      if (item.reachable && item.compatible) state.lastDatabaseSuccess[role] = item.checked_at || new Date().toISOString();
    }
    renderDatabase(data, state.lastDatabaseSuccess);
  } catch {
    // Never retain old counts under a current "connected" label after failure.
    state.database = { base: { name: "mirage_base", read_only: true, points: null, reachable: false },
      runtime: { name: state.database?.runtime?.name || "Demo runtime", read_only: false, points: null, reachable: false } };
    renderDatabase(state.database, state.lastDatabaseSuccess);
  } finally { state.databasePending = false; updateControls(); }
}

async function refreshHealth() {
  const presetId = selectedPreset()?.id;
  if (!presetId) return;
  const version = ++state.healthVersion;
  state.healthPending = true;
  state.health = null;
  updateControls();
  $("health-summary").textContent = "Checking service readiness…";
  try {
    const input = { question: "Readiness check", preset_id: presetId, overrides: configurationOverrides() };
    const resolved = await api("/api/configurations/resolve", jsonPost(input));
    if (version !== state.healthVersion) return;
    state.resolvedConfiguration = resolved.config;
    renderFeatures(resolved.config);
    const health = await api("/api/health", jsonPost(input));
    if (version !== state.healthVersion) return;
    state.health = health;
    renderHealth(health);
  } catch (error) {
    if (version !== state.healthVersion) return;
    state.health = null;
    renderHealth(null, error);
  } finally {
    if (version === state.healthVersion) { state.healthPending = false; updateControls(); }
  }
}

async function refreshActivity() {
  if (state.activityPending || state.submitting) return;
  state.activityPending = true;
  try {
    const activity = await api("/api/activity");
    state.busy = activity.busy;
    state.activeRunId = activity.active_run_id;
    if (!state.run && state.allowAutoAttach && activity.active_run_id) await attachRun(activity.active_run_id);
    if (!activity.busy && state.run?.status === "running" && state.run?.mode !== "replay") {
      const record = await api(`/api/runs/${encodeURIComponent(state.run.runId)}`);
      if (record.status !== "running") {
        applyRecord(state.run, record);
        render();
      }
    }
  } catch { /* A failed activity poll cannot turn an active run into idle. */ }
  finally { state.activityPending = false; updateControls(); }
}

function applyRecord(run, record) {
  run.input = record.metadata.input || run.input;
  run.metadata = record.metadata;
  run.result = record.result;
  run.status = record.status;
  run.images = Array.from({ length: record.metadata.image_count || 0 }, (_, index) =>
    `/api/runs/${encodeURIComponent(run.runId)}/images/${index}`);
}

async function completeRun(run) {
  for (let attempt = 0; attempt < 20; attempt++) {
    if (state.run !== run) return;
    try {
      const record = await api(`/api/runs/${encodeURIComponent(run.runId)}`);
      if (state.run !== run) return;
      if (record.status !== "running") {
        applyRecord(run, record);
        $("stream-status").textContent = record.events_truncated ? "Run ended · some events exceeded the recording limit." : "Run ended · all available events received.";
        render();
        await Promise.allSettled(run.mode === "replay" ? [refreshHistory()] : [refreshDatabase(), refreshActivity(), refreshHistory()]);
        return;
      }
    } catch { /* Preserve the known event outcome while the saved result catches up. */ }
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  if (state.run === run) $("stream-status").textContent = "Events ended. Waiting for the saved result; service polling will retry.";
}

function startStream(run) {
  state.stream?.abort();
  const controller = new AbortController();
  state.stream = controller;
  let scheduled = false;
  streamEvents(run, {
    signal: controller.signal,
    onConnection(status) {
      if (state.run !== run) return;
      if (run.mode === "replay") { $("stream-status").textContent = "REPLAY · recorded events · 4× presentation pace"; return; }
      $("stream-status").textContent = { connecting: "Connecting to the event stream…", connected: "Live · receiving pipeline events", reconnecting: "Connection interrupted · reconnecting from the last received event…" }[status];
    },
    onEvent(event) {
      if (state.run !== run) return;
      if (!acceptEvent(run, event)) return;
      if (!scheduled) {
        scheduled = true;
        requestAnimationFrame(() => { scheduled = false; if (state.run === run) render(); });
      }
    },
    onTerminal: () => completeRun(run),
    onError(error) {
      if (state.run !== run) return;
      $("stream-status").textContent = error.message;
      notify(error.message);
      refreshActivity();
    },
  }).catch(error => { if (!controller.signal.aborted) notify(error.message || "Unable to read pipeline events."); });
}

async function attachRun(runId) {
  try {
    const record = await api(`/api/runs/${encodeURIComponent(runId)}`);
    const run = newRun(runId, record.metadata.input, record.metadata);
    applyRecord(run, record);
    state.run = run;
    state.allowAutoAttach = false;
    rememberRun(runId);
    render();
    startStream(run);
  } catch (error) {
    rememberRun(null);
    if (error.status !== 404) notify("The active run could not be restored. Refresh to try again.");
  }
}

function setMode(mode) {
  state.mode = mode;
  $("mode-examples").classList.toggle("active", mode === "examples");
  $("mode-custom").classList.toggle("active", mode === "custom");
  $("mode-examples").setAttribute("aria-pressed", String(mode === "examples"));
  $("mode-custom").setAttribute("aria-pressed", String(mode === "custom"));
  $("example-controls").hidden = mode !== "examples";
  updateControls();
}

function renderImages() {
  $("image-count").textContent = `${state.files.length} / 3`;
  $("image-previews").replaceChildren(...state.files.map((file, index) => {
    const figure = el("figure", "image-preview");
    const image = el("img"); image.src = file.url; image.alt = `Selected input: ${file.file.name}`;
    const remove = el("button", "image-remove", "×");
    remove.type = "button"; remove.setAttribute("aria-label", `Remove ${file.file.name}`);
    remove.addEventListener("click", () => {
      URL.revokeObjectURL(file.url);
      state.files.splice(index, 1);
      renderImages(); updateControls();
    });
    figure.append(image, el("figcaption", "", file.file.name), remove);
    return figure;
  }));
}

async function addImages(files) {
  const incoming = [...files];
  if (incoming.length + state.files.length > 3) { notify("Choose at most three images in total."); return; }
  const staged = [];
  state.imagePending = true;
  updateControls();
  try {
    for (const file of incoming) {
      if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || !/\.(jpe?g|png|webp)$/i.test(file.name)) throw new Error("Use JPEG, PNG, or WebP images.");
      if (!file.size || file.size > 10 * 1024 * 1024) throw new Error("Each image must be nonempty and no larger than 10 MiB.");
      const bitmap = await createImageBitmap(file);
      const pixels = bitmap.width * bitmap.height;
      bitmap.close();
      if (pixels > 20_000_000) throw new Error("Each image must be at most 20 megapixels.");
      staged.push({ file, url: URL.createObjectURL(file) });
    }
    state.files.push(...staged);
    renderImages();
  } catch (error) {
    staged.forEach(file => URL.revokeObjectURL(file.url));
    notify(error.message || "An image could not be read. Please choose a valid image.");
  }
  state.imagePending = false;
  updateControls();
}

function queryInput() {
  const input = { question: $("question").value.trim(), task_type: $("task-type").value,
    state: $("state").value.trim(), county: $("county").value.trim(),
    month_year: $("month-year").value || null, preset_id: $("preset").value, overrides: configurationOverrides() };
  if (input.county && !input.state) throw new Error("Please provide a state with the county.");
  if (input.month_year && !/^\d{4}-(0[1-9]|1[0-2])$/.test(input.month_year)) throw new Error("Please provide a valid month and four-digit year.");
  return input;
}

$("query-form").addEventListener("submit", async event => {
  event.preventDefault();
  if ($("run-button").disabled) return;
  let input;
  try { input = queryInput(); } catch (error) { notify(error.message); return; }
  state.submitting = true;
  notify("");
  updateControls();
  try {
    let options;
    if (state.files.length) {
      const form = new FormData();
      form.append("request", JSON.stringify(input));
      state.files.forEach(file => form.append("images", file.file));
      options = { method: "POST", body: form };
    } else options = jsonPost(input);
    const accepted = await api("/api/runs", options);
    const run = newRun(accepted.run_id, input, { config: structuredClone(state.resolvedConfiguration), image_count: state.files.length });
    run.images = state.files.map((_, index) => `/api/runs/${encodeURIComponent(run.runId)}/images/${index}`);
    state.run = run;
    state.busy = true;
    state.activeRunId = run.runId;
    state.allowAutoAttach = false;
    rememberRun(run.runId);
    render();
    startStream(run);
  } catch (error) {
    if (error.status === 409) {
      state.busy = true;
      notify("The demo is already processing a question. You can follow the active run while it finishes.");
    } else if (error.status === 503) {
      const health = error.detail?.readiness;
      state.health = health || null;
      renderHealth(health);
      $("health-panel").open = true;
      notify("The services are not ready for this question. Check service details below.");
    } else notify(error.message || "The question could not be submitted. Please try again.");
  } finally {
    state.submitting = false;
    updateControls();
    refreshActivity();
  }
});

$("mode-examples").addEventListener("click", () => setMode("examples"));
$("mode-custom").addEventListener("click", () => setMode("custom"));
$("example").addEventListener("change", () => {
  const example = state.examples.find(item => item.id === $("example").value);
  state.selectedExample = example || null;
  $("example-description").textContent = example ? `${example.description} ${example.validated ? "" : "Starter question · not yet validated."}` : "Editable examples; conference validation is pending.";
  if (example) {
    for (const [name, value] of Object.entries(example.input)) {
      const field = { task_type: "task-type", month_year: "month-year" }[name] || name;
      if ($(field)) $(field).value = value || "";
    }
  }
  updateControls();
});
$("query-form").addEventListener("input", updateControls);
$("images").addEventListener("change", async event => { await addImages(event.target.files); event.target.value = ""; });
$("preset").addEventListener("change", () => { resetConfigurationControls(); refreshHealth(); });
$("custom-configuration").addEventListener("change", () => {
  $("custom-controls").hidden = !$("custom-configuration").checked;
  refreshHealth();
});
for (const id of ["workflow", "custom-db", "custom-crop"]) $(id).addEventListener("change", refreshHealth);
$("refresh-database").addEventListener("click", refreshDatabase);
$("refresh-health").addEventListener("click", refreshHealth);
$("dismiss-notice").addEventListener("click", () => notify(""));
$("follow-latest").addEventListener("click", () => { if (state.run) { state.run.follow = true; render(); } });
$("follow-active-run").addEventListener("click", () => { if (state.activeRunId) attachRun(state.activeRunId); });
$("reset-view").addEventListener("click", () => {
  const wasRunning = state.busy || state.run?.status === "running";
  state.stream?.abort();
  state.run = null;
  state.allowAutoAttach = false;
  rememberRun(null);
  state.files.forEach(file => URL.revokeObjectURL(file.url));
  state.files = [];
  state.selectedExample = null;
  $("query-form").reset();
  if (state.defaultPreset) $("preset").value = state.defaultPreset;
  if (selectedPreset()) resetConfigurationControls();
  setMode("examples"); renderImages();
  $("example-description").textContent = "Editable examples; conference validation is pending.";
  $("stream-status").textContent = "";
  notify(wasRunning ? "View cleared. The active query continues on the server." : "");
  render(); refreshHealth(); refreshActivity();
});

$("clear-runtime").addEventListener("click", () => {
  const runtime = state.database?.runtime;
  if (!runtime || $("clear-runtime").disabled) return;
  $("clear-dialog-description").textContent = `This removes all ${runtime.points?.toLocaleString() ?? "stored"} chunks from ${runtime.name}. New questions will start with an empty demo runtime.`;
  $("clear-token").textContent = `CLEAR ${runtime.name}`;
  $("clear-confirmation").value = "";
  $("clear-error").hidden = true;
  $("clear-dialog").showModal();
  updateControls();
});
$("cancel-clear").addEventListener("click", () => $("clear-dialog").close());
$("clear-confirmation").addEventListener("input", updateControls);
$("clear-form").addEventListener("submit", async event => {
  event.preventDefault();
  if ($("confirm-clear").disabled) return;
  state.clearing = true;
  $("clear-error").hidden = true;
  $("cancel-clear").disabled = true;
  updateControls();
  try {
    await api("/api/database/runtime/clear", jsonPost({ collection: state.database.runtime.name,
      confirmation: $("clear-confirmation").value }));
    $("clear-dialog").close();
    notify("Demo runtime cleared. Curated knowledge and saved run records are preserved.");
    await refreshDatabase();
  } catch (error) {
    $("clear-error").textContent = error.status === 409 ? "A query started before the reset. Wait for it to finish and confirm again." : error.message;
    $("clear-error").hidden = false;
    if (error.status === 409) state.busy = true;
  } finally {
    state.clearing = false;
    $("cancel-clear").disabled = false;
    updateControls(); refreshActivity();
  }
});

async function refreshHistory() {
  try {
    const data = await api("/api/runs?limit=20");
    const selected = $("history-run").value;
    $("history-run").replaceChildren(...data.runs.map(record => {
      const option = el("option", "", `${record.created_at} · ${record.status} · ${(record.metadata.input?.question || "Untitled").slice(0, 100)}`);
      option.value = record.run_id; return option;
    }));
    if ([...$("history-run").options].some(option => option.value === selected)) $("history-run").value = selected;
    $("history-status").textContent = `${data.runs.length} recent executions. Shared runtime makes comparisons illustrative.`;
  } catch { $("history-status").textContent = "History unavailable. Refresh to retry."; }
}

$("refresh-history").addEventListener("click", refreshHistory);
$("inspect-history").addEventListener("click", async () => {
  const id = $("history-run").value;
  if (!id) return;
  await attachRun(id);
  if (state.run && state.run.status !== "running") state.run.mode = "history";
  render();
});
$("replay-history").addEventListener("click", async () => {
  const id = $("history-run").value;
  if (!id) return;
  try {
    const replay = await api("/api/replays", jsonPost({ run_id: id }));
    const record = await api(`/api/runs/${encodeURIComponent(id)}`);
    state.stream?.abort();
    const run = newRun(id, record.metadata.input, record.metadata);
    run.mode = "replay";
    run.eventsUrl = replay.events_url;
    run.images = Array.from({ length: record.metadata.image_count || 0 }, (_, index) => `/api/runs/${encodeURIComponent(id)}/images/${index}`);
    state.run = run;
    state.allowAutoAttach = false;
    rememberRun(null);
    notify(replay.events_truncated ? "This recording is truncated; some original events are unavailable." : "Replaying a saved trace. Original timestamps and provenance are preserved.");
    render(); startStream(run);
  } catch (error) { notify(error.message); }
});

async function initialize() {
  render();
  const results = await Promise.allSettled([
    api("/api/configurations").then(data => {
      state.configurations = data;
      state.defaultPreset = data.default;
      $("preset").replaceChildren(...data.presets.map(preset => {
        const option = el("option", "", preset.name); option.value = preset.id; return option;
      }));
      $("preset").value = data.default;
      $("workflow").replaceChildren(...data.workflow_profiles.map(profile => {
        const option = el("option", "", profile.name); option.value = profile.id; return option;
      }));
      resetConfigurationControls();
      return refreshHealth();
    }),
    api("/api/examples").then(catalog => {
      state.examples = catalog.examples;
      for (const example of catalog.examples) {
        const option = el("option", "", `${example.title}${example.image_required ? " · add image" : ""}`);
        option.value = example.id; $("example").append(option);
      }
    }),
    refreshDatabase(),
  ]);
  if (results[0].status === "rejected") {
    state.healthPending = false;
    notify("Pipeline configurations could not be loaded. Refresh this page when the API is available.");
    $("preset").replaceChildren(el("option", "", "Configurations unavailable"));
    renderHealth(null, true);
  }
  if (results[1].status === "rejected") {
    setMode("custom");
    $("example-description").textContent = "Starter catalog unavailable. You can still enter a custom question.";
  }
  const remembered = rememberedRun();
  if (remembered) await attachRun(remembered);
  await refreshActivity();
  await refreshHistory();
  render();
  setInterval(refreshActivity, 2500);
  setInterval(() => { if (!document.hidden && state.run?.mode !== "replay") refreshDatabase(); }, 15000);
  setInterval(() => { if (!document.hidden && state.run?.mode !== "replay" && !state.healthPending && !state.busy) refreshHealth(); }, 45000);
}

window.addEventListener("pagehide", () => { state.stream?.abort(); });
window.addEventListener("pageshow", event => {
  if (event.persisted) {
    if (state.run) startStream(state.run);
    refreshActivity();
  }
});
initialize().catch(() => notify("The interface could not connect to the backend. Refresh the page to try again."));
