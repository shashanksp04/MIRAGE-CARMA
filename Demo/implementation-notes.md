# Implementation record: phases 0–3

## Scope and validation agreement

The user originally authorized phases 0–2, then explicitly authorized **Phase 3
only** in a subsequent turn. The cluster's existing `mirage` environment and
`CropDatabase.json` are assumed available. Live inference gates are deferred
to that cluster; local characterization/contract/browser tests are not live
inference validation. Current scope includes the three-column frontend and an
unvalidated starter catalog. Custom feature combinations, validated conference
scenarios, presentation replay controls and a run-history UI remain deferred.
SSE reconnection uses genuine stored events.

## Phase 0: integration map, before shared edits

Read `Guide.md`, `Inference/README.md`, `MSCdocs/Documentation.md`, the demo plan,
agent tools, preset/template parsing, retrieval/confidence, and collection lifecycle.

| Existing path | Demo reuse / boundary |
| --- | --- |
| `Generate.get_prompt` | Same location prefix; explicit task type and optional month supplied by demo request |
| `rag_worker_process` | Audit reference only; do not import batch multiprocessing orchestration |
| `CropQueryEnricher.enrich` | RAG endpoint; dictionary loaded only for enabled presets |
| `VisualAttributeExtractor.extract` | Already implemented; demo always invokes for identification with images (up to three) |
| `MainAgent.main` / `InMemoryRunner` | One dedicated RAG endpoint, fresh request state, real tool calls |
| `MainAgent.finalize_rag_result` | Application-owned evidence/status; agent prose is diagnostic |
| `Client.chat` | Same final-generation client and evidence prompt; dedicated generation endpoint, actual images |
| `QdrantStore` / dual retriever | Existing schema, scoring and base-preferred deduplication |
| `InferenceDatabaseManager` | Do NOT reuse: successful batch cleanup deletes runtime; demo must persist |

`ablation_8_full_domain_filtered` is the full-system default. `db_on` and
`crop_dict_on` must be applied by the demo runner: MainAgent does not apply them.
Eight existing preset IDs have matching templates. Custom overrides are deferred.

Batch trace: input image paths and location → optional crop/visual enrichment →
RAG worker ADK tools → structured RAGResult → evidence text appended to generation
query → Client.chat with actual images → incremental JSONL. Batch intentionally
generates on insufficient evidence; demo must skip generation for that status.

Planned shared edits are limited to optional observation at existing tool/strategy
boundaries. Old signatures/defaults and tool schemas will be retained. Observer
failure must not change retrieval results. No preset, instruction, batch driver,
batch lifecycle, confidence formula, or retrieval selection changes are planned.

The local system Python has none of the inference/web dependencies. Phase 0 uses
standard-library tests of actual source definitions and public signatures plus
existing pure confidence tests. GPU/model/ADK integration, real multiworker startup,
Qdrant persistence, and image inference remain cluster checks.

Baseline command: `python3 -m unittest Demo.tests.test_batch_baseline
rag_agent.test_confidence_evaluator -v` — 14 tests, 12 passed, 2 skipped because
`transformers` is unavailable. Signature, preset/template/tool mapping, endpoint
partition, structured outcome and pure confidence checks passed before feature
implementation. Initial test harness assumptions (list-valued generation endpoints
and constructor defaults) were corrected against the actual source.

## Phase 1

Added isolated settings/preset snapshots, validated request contracts, image
normalization, a demo-only collection manager, process lock, lazy real pipeline
adapter and CLI. No shared code was modified in this phase. The adapter reuses
MainAgent, CropQueryEnricher, VisualAttributeExtractor and Client.chat; its final
prompt matches batch evidence concatenation. Final generation is skipped on
insufficient evidence or malformed RAG state. Runtime is never cleared at exit.

Command: `/tmp/mirage-demo-venv/bin/python -m unittest Demo.tests.test_runner
Demo.tests.test_batch_baseline rag_agent.test_confidence_evaluator -v` — 20 tests,
18 passed, 2 dependency skips. CLI `--help` passed. The local isolated environment
uses repository-pinned FastAPI/Pydantic/httpx/Qdrant versions, with Pillow 13
because the local Python 3.14 cannot use the repository's Pillow 11 wheel.
Unit fixtures are explicitly synthetic; no live results or recordings are claimed.
Real model/image calls, two-query persistent ingestion and batch multiworker
startup are deferred to the cluster under the user's validation agreement.

## Phase 2

Added typed domain events, durable SQLite run/event storage, SSE catch-up and
disconnect handling, single-query execution, validated multipart image uploads,
readiness/configuration/status APIs, and confirmed runtime point deletion. Recent
run retention, bounded payloads/events, rotating diagnostics, and interrupted-run
recovery are included as backend infrastructure. Presentation replay/scenario/UI
features remain deferred to phases 3–5.

Shared edits:

- `rag_agent/utils/observation.py`: request-local optional observer context and
  signature-preserving tool decorators, with a no-observer fast path.
- `rag_agent/main.py`: tool boundary decorators and reporting of already-measured
  ingestion counts. No new inference parameters or algorithm changes.
- `rag_agent/utils/ContentUtils.py`: emit existing candidate diagnostics and the
  selected per-collection strategy. No score/eligibility/selection changes.
- `rag_agent/tools/web_search.py`: expose actual prepared query and allowed domains.

Collection verification also rejects aliases, preventing a configured demo name
from redirecting reset to the base. Clear deletes demo points without dropping
the collection. Failed source fetches remain diagnostic and cannot produce a
successful ingestion event. All original public signatures in the baseline
remain identical. The batch driver, shell script, preset JSON, instruction
templates and batch collection manager are unchanged.

Local full-suite command: `PYTHONDONTWRITEBYTECODE=1
/tmp/mirage-demo-venv/bin/python -m pytest Demo/tests
rag_agent/test_confidence_evaluator.py -q`. Final result: **36 passed, 2 skipped,
84 signature subtests passed**, plus one upstream deprecation warning (2.03 s).
All demo Python files parsed, `bash -n Inference/bash_generate.sh` passed, and
`git diff --check` passed. Protected batch/configuration files were also compared
byte-for-byte with their original committed versions and are unchanged.

The suite verifies actual local HTTP/SSE transport with explicitly synthetic
inference, Qdrant in-memory point persistence/protected reset/schema rejection,
observer/no-observer equivalence, callback failures, configuration snapshots,
upload decoding/path safety, busy locking, run/event isolation, event retention,
restart recovery, insufficient evidence and readiness reporting. The two skipped
legacy tests require `transformers`; the actual strategy method is additionally
covered by a dependency-light observer-equivalence test.

Environment limitation: the filesystem/network sandbox stalls Starlette
TestClient's event-loop wakeup before app startup. API/TCP tests passed when run
outside that sandbox against loopback only. One upstream Starlette/AnyIO
deprecation warning is unrelated to the demo.

Remaining cluster checks are listed in README: real ADK/tool schemas and model
requests, real image extraction, two-query ingestion/persistence, actual
insufficient-evidence generation suppression, and multiworker batch startup.
No live conference recordings or validated scenarios have been fabricated.

## Phase 3

Implemented a build-free frontend served from the existing FastAPI process at
`/`. New source: `Demo/frontend/index.html`, `styles.css`, `model.js`,
`network.js`, `view.js`, `app.js`, and a local SVG favicon. No frontend runtime
packages or external fonts/CDNs are required. Styles centralize Illini Blue,
Illini Orange and accessible Altgeld text accents, based on the official Illinois
brand/web color references. The desktop layout has three columns and stacks at
smaller widths; keyboard focus, semantic controls and native modal confirmation
are preserved.

Left: editable starter/custom inputs, explicit task type, actual image validation
and previews, geographic/time context, existing real preset selection, read-only
feature indicators, Qdrant status/count refresh and exact runtime confirmation.
`Demo/examples/catalog.json` supplies three explicitly unvalidated starters; the
identification starter requires a user-provided image. No scenario promises an
inference path. Real presets were already supported in Phase 2; no new custom
overrides or instruction-template mappings were introduced.

Center: ordered events folded into stage attempts, repeated retrieval/confidence
and ingestion instances, pinned selection or follow-latest, accurate skipped and
disabled states, and fetch failures separated into optional diagnostics. The SSE
client handles partial frames, disconnect/reconnect, monotonic sequence checks,
deduplication and catch-up. Closing/resetting the browser view does not cancel
the active server query. Browser session storage remembers only the run ID;
inputs/images/configuration are restored from the saved backend record.

Right: original query/image/captured preset, crop enrichment, identification
observations, actual retrieval/web queries, per-collection strategy tables and
selection/rejection reasons, raw similarities, confidence components and existing
thresholds, source passages and augmentation counts, and final/insufficient/error
outcomes. Images remain within the existing input/detail columns. Safe DOM/text
rendering and HTTP(S)-only source links prevent retrieved HTML from executing.
Source evidence is explicitly not claimed as a statement-level citation mapping.

Backend changes in this phase are confined to `Demo/backend/app.py`: static UI,
starter catalog, activity status and owned image-preview routes. Image routes
verify the run, index and resolved path (including symlink escape rejection).
Activity uses the existing lock; inference and runtime lifecycle are unchanged.
No additional shared `rag_agent` or `Inference` edits were made in Phase 3.

Validation:

- `node Demo/tests/frontend_model.test.mjs`: **6 passed**. Checks event isolation,
  reconnect deduplication/gaps, repeated stages, intermediate strategy status,
  diagnostics, database chronology, SSE frames and safe links.
- `PLAYWRIGHT_BROWSERS_PATH=/tmp/mirage-demo-browsers PYTHONDONTWRITEBYTECODE=1
  /tmp/mirage-demo-venv/bin/python -m pytest Demo/tests
  rag_agent/test_confidence_evaluator.py -q`: **45 passed, 2 dependency skips,
  84 signature subtests passed**, one upstream deprecation warning (16.15 s).
  Includes seven Chromium tests against a real loopback API/SSE server using
  clearly labeled synthetic inference fixtures. Covers desktop/mobile geometry,
  keyboard interaction, safe answer rendering, direct retrieval, augmentation
  loops/diagnostics, image identification and original images, insufficient/error
  suppression, restore/busy/reset, exact confirmation and stream truncation recovery.
- The actual app was also launched without model/inference fixtures: three UI
  columns rendered, eight missing-service checks were reported, launch remained
  disabled, and a 390px mobile viewport had no horizontal overflow. Screenshots
  were captured locally in `/tmp/mirage-phase3-ui.png` and
  `/tmp/mirage-phase3-ui-mobile.png`; no synthetic responses are shown there.
- JavaScript syntax, all demo Python syntax, protected batch/configuration file
  equality and `git diff --check` passed. An extra label clarifies that retained
  run count deltas describe the displayed query even after a runtime reset.

Deviation/remaining gate: real direct retrieval, actual web augmentation and real
image identification through the UI still require the cluster model/Qdrant
services. The browser fixture tests do not claim those live inference gates.
`Demo/requirements-browser.txt` is optional local QA tooling, not an application
dependency. Work stops here; Phases 4 and 5 are not implemented.

## Phase 4 — Supported custom configurations (2026-10-29)

User authorization: implement Phase 4. Phase 5 remains deferred. The prior live
cluster gates are still pending; this phase adds implementation and local
validation under that known limitation rather than claiming those gates passed.

Configuration resolution in `backend/configurations.py` retains all eight real
presets and supports 20 combinations: five existing instruction-compatible
workflow profiles, each with independent curated DB/crop dictionary settings.
All 128 boolean combinations are enumerated in tests; the remaining 108 fail
validation explicitly. Search and ingestion stay coupled because existing
instructions require that sequence. No generic/fallback instruction is selected
for custom configurations. Frozen custom metadata records source preset,
effective flags, explicit overrides and the exact instruction preset. Preset
changes after submission reject initialization.

`backend/schemas.py` adds immutable strict boolean overrides. `demo_runner.py`
uses the resolved actual instruction ID, explicit base/crop inputs and CLI
`--overrides`. `health.py` accepts effective settings. `app.py` exposes workflow
profiles/override fields, config resolution and POST readiness; run readiness and
recording use resolved settings. Existing GET preset health remains available.

Frontend changes in `app.js`, `index.html`, `view.js` and `styles.css` add custom
workflow and independent DB/crop controls, refresh effective indicators and
readiness, capture the snapshot and display its instruction source. Native
checkboxes use existing theme/focus tokens and proper dimensions. Switching a
preset resets customization without changing previously recorded run settings.
Persistent runtime and enabled/not-invoked/disabled semantics remain in effect.
No shared `rag_agent`/`Inference` files were edited for this phase; no new
MainAgent interface was needed. Existing preset/instruction files were unchanged.

Validation:

- Combined command: `PLAYWRIGHT_BROWSERS_PATH=/tmp/mirage-demo-browsers
  PYTHONDONTWRITEBYTECODE=1 /tmp/mirage-phase4-venv/bin/python -m pytest
  Demo/tests rag_agent/test_confidence_evaluator.py -q`.
- Result: **56 passed, 2 dependency skips, 84 signature subtests passed**;
  one upstream Starlette TestClient deprecation warning. Includes eight Chromium
  tests with explicitly synthetic inference. New checks exercise all supported
  actual agent tool/instruction methods, initialization routing, preset smoke
  fixtures, retention of runtime counts across preset changes, invalid overrides,
  immutable snapshots/drift, API readiness/record agreement and browser controls.
- Final checkbox geometry/mobile browser check repeated: **1 passed**.
  Effective custom health requirements checked after extending health assertions.
- `node Demo/tests/frontend_model.test.mjs`: **6 passed**. Python/JS/shell syntax,
  protected-file equality to HEAD and tracked `git diff --check` passed.
- Test dependencies installed only into `/tmp/mirage-phase4-venv`; browser files
  live under `/tmp/mirage-demo-browsers`. No application dependency additions.

Remaining acceptance: real smoke inference for each preset and representative
custom profiles, full default and no-base/no-crop behavior, tool invocations with
real models, switching after genuine ingestion, and cluster batch startup smoke.
No real inference result, recording or validated conference scenario is claimed.


## Phase 5 — Presentation replay, history and operational preparation

Authorized by the user after Phase 4. Added `backend/replay_manager.py` and
strict replay requests; replay creation and paced SSE consume retained terminal
runs with original event envelopes, timestamps and sequence cursors. Replay
requires no runner/model/web/Qdrant calls. Recording IDs refer to source run IDs
and follow existing retention; missing, running and empty recordings fail clearly.
Replay supports bounded speed, Last-Event-ID reconnect and truncation disclosure.

Frontend history lists 20 recent runs and supports saved inspection and replay.
The existing timeline/detail renderer consumes replay events with a persistent
REPLAY banner and original metadata/images/results. Playback uses explicit 4x
presentation pacing; clear view stops the stream. Model/database periodic polling
pauses during replay. No additional persistent replay copies or unbounded session
registry is introduced.

Added `CONFERENCE-RUNBOOK.md` with readiness, runtime accumulation/reset,
retention/backup, privacy, failure fallback and recovery. Added
`examples/validation.md` with required real scenario provenance. README and status
now describe current functionality. No shared inference code was changed.

Validation: combined Demo/confidence suite **58 passed, 2 skipped, 84 signature
subtests passed**, including nine Chromium tests. JavaScript **6 passed**. Replay
API checks prove identical stored event sequences, cursor recovery and service
independence; browser checks cover offline inference replay/history inspection.
Python/JS syntax and protected-file equality checks pass. One upstream TestClient
warning remains. Local tests use explicitly synthetic inference.

Live acceptance is pending: no cluster allocation/services or genuine inference
traces are available here. Real conference recordings, validated agricultural
scenario bundles, live configuration/accumulation/reset matrix and batch startup
smoke must be recorded on the cluster before claiming conference readiness.
