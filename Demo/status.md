# MIRAGE-CARMA demo: status and handoff context

Last updated: 2026-10-29.

This file is the starting context for future chats. Read it before changing the
demo, then consult [README.md](README.md) for operation and
[implementation-notes.md](implementation-notes.md) for the detailed phase record.
The authoritative specification is
[MSCdocs/plan-demo-paper-implementation.md](../MSCdocs/plan-demo-paper-implementation.md).

## Current stopping point

**Phase 5 history/replay and operational implementation is present. Live cluster
acceptance gates remain pending, including genuine recordings and validated
conference scenarios. The demo is not yet validated for conference presentation.**

| Phase | Implementation status | Validation status |
| --- | --- | --- |
| 0 — Audit and compatibility baseline | Repository audit, integration map, signature/preset/outcome characterization complete | Local checks passed; real batch startup/smoke remains a cluster check |
| 1 — Standalone query runner | Real-pipeline adapter, CLI, image handling, persistent demo runtime and explicit outcomes implemented | Unit checks passed; real end-to-end inference, image extraction and two-query ingestion/persistence remain unverified on cluster |
| 2 — Events and backend API | Optional instrumentation, durable ordered events, SSE, run management, readiness/status/reset APIs implemented | Local API, transport, collection-safety and regression checks passed; model-driven integration remains a cluster check |
| 3 — Three-column frontend | UIUC-themed UI connected to the actual API/SSE implemented | Browser interaction tests and actual offline UI checks passed; real direct retrieval, augmentation and identification UI flows remain cluster checks |
| 4 — Custom configurations and broader preset validation | Supported custom workflows, strict overrides, effective readiness and frozen configuration snapshots implemented | Local configuration/tool/API/browser checks performed; real preset smoke and batch startup remain cluster checks |
| 5 — Presentation replay, history UI, validated scenarios and conference hardening | Retained-trace replay, recent history UI, provenance and operational runbook implemented; genuine recordings/scenarios pending | Local API/browser validation; live conference matrix pending |

"Implemented" does not mean the real inference acceptance gates have passed.
Local inference fixtures are explicitly synthetic. No successful live cluster
inference, real conference recording or validated conference scenario is claimed.

## User instructions and decisions from this conversation

- Initially implement only Phases 0–2, after reading the plan and receiving
  approval. The user provided that approval, and those phases were implemented.
- The user subsequently authorized Phase 3 and instructed us to stop.
- On 2026-10-29, the user authorized **Phase 4**. The user subsequently authorized Phase 5.
- Live inference validation belongs on the user's cluster. The user has an
  existing Python environment called `mirage` with the current inference
  dependencies; assume that environment works. New demo libraries can be
  installed into it using the demo-specific manifests.
- Assume `CropDatabase.json` will be available on the cluster. It was not present
  in this checkout during implementation.
- The user currently has no cluster compute allocation. The UI can be viewed
  locally with unavailable-service status and inference disabled.
- The user viewed the local UI and said it looked great. Preserve the established
  design unless they request changes.
- At the Phase 3 handoff, the request was to **close the local preview and create this context
  file**. The preview process on `127.0.0.1:8000` was stopped cleanly, including
  application shutdown. No preview server is intentionally being left running.
- No commits, pushes, PRs, hosted Sites, or deployments were created during this
  conversation. At handoff, `Demo/` and `rag_agent/utils/observation.py` are
  untracked, and three existing shared Python files are modified. Do not discard
  these changes as unrelated work.

## Architecture and integration

```text
Browser (build-free HTML/CSS/JavaScript)
  → FastAPI HTTP + SSE, serving the UI from the same origin
  → single-query execution thread / exclusive process lock
  → one dedicated RAG-model endpoint
      crop enrichment + identification image observations + MainAgent tools
      curated base search + persistent demo runtime search/ingestion
  → one separate final-generation endpoint
      original actual images + crop-enriched question + accepted evidence
  → saved result, durable event stream and collection count updates
```

The demo imports existing algorithms and clients rather than duplicating the
batch orchestration. It does not import `Inference/generate.py` to launch workers.

Existing components reused:

- `rag_agent.main.MainAgent` and its Google ADK `InMemoryRunner`.
- `MainAgent.begin_request` and `finalize_rag_result` for application-owned state.
- `CropQueryEnricher` on the RAG endpoint.
- Existing `Inference/visual_attribute_extractor.py`, also on the RAG endpoint.
- Existing Qdrant store schema, dual-collection retrieval and base-preferred
  deduplication.
- `chat_models.Client.Client.chat` for final generation with actual images.

The existing batch database manager is deliberately **not** reused for demo
lifecycle: batch success deletes its runtime collection, whereas demo knowledge
must persist between queries.

## Configuration and inference behavior

- Default preset: **`ablation_8_full_domain_filtered`**, the existing full system
  with curated database and crop dictionary enabled.
- Eight real preset IDs are loaded from `rag_agent/ablation_configs.json` and
  checked against matching sections in `rag_agent/model_instructions.md`.
- `db_on` and `crop_dict_on` must be applied explicitly by the demo runner.
  MainAgent applies the remaining feature flags but does not apply those two.
- Per-run preset metadata is captured, and the runner rejects a preset that
  changes between submission and agent initialization.
- Supported custom feature overrides are accepted per run. Five instruction-compatible
  workflow profiles plus independent DB/crop controls support 20 feature combinations.
  Unsupported combinations and non-boolean overrides are rejected. The UI displays
  effective flags and the saved run records its source preset and instruction preset.
- Question type is explicit: `management` or `identification`, default management.
  It is not guessed from the question's wording.
- For identification with images, visual extraction is always attempted and has
  no toggle. Management questions do not gratuitously invoke it.
- Visual observations enrich retrieval only. Final generation still receives the
  actual normalized image files. Extraction failures preserve the existing
  text-only retrieval fallback and are recorded as such.
- Final generation receives the same style of evidence concatenation as batch:
  enriched query followed by the accepted retrieved evidence text.
- Demo outcomes: `completed`, `insufficient_evidence`, `failed`.
- On explicit insufficient evidence, skip final generation and display the
  informational no-evidence message. Invalid structured RAG output also does not
  produce an unsupported answer. Backend failures are distinct from insufficient
  evidence. Agent final prose is diagnostic, not the source of RAG success.
- This differs intentionally from batch's existing insufficient-evidence fallback,
  which remains unchanged.

## Collection and concurrency boundaries

- Curated collection is fixed as **`mirage_base`**, read-only from the demo.
- Default persistent demo collection is **`mirage_demo_runtime`**. A configured
  `mirage_demo_runtime_<suffix>` is allowed; base and batch collection names are
  not allowed as demo runtime names.
- Collection roles must refer to physical collections. Aliases are rejected so
  a demo alias cannot redirect clearing to the curated base.
- Required vectors: unnamed 768-dimensional cosine, matching
  `BAAI/bge-base-en-v1.5`. Incompatible existing schema fails verification without
  silently recreating data.
- Runtime is created/resumed and never automatically reset between queries,
  when switching presets, or on successful exit.
- Ingestion targets only the demo runtime. Previously accumulated runtime
  evidence can still be retrieved when ingestion is disabled.
- Clear requires an exact configured collection name plus `CLEAR <name>`, and
  the exclusive idle lock. It deletes runtime points while retaining the
  collection/indexes, base, batch data and run history.
- Counts are Qdrant **points/chunks**, not document counts.
- Runtime accumulation means runs are not controlled ablation comparisons; the
  UI states this explicitly.
- Only one query/reset at a time. Busy operations return HTTP 409.
- API and CLI share a nonblocking filesystem lock under `DEMO_DATA_DIR`.
  A separate server lock prevents multiple API instances on that directory.
  This is not distributed locking across different machines/data directories.
- Use one uvicorn worker. Shutdown waits for an active query before releasing
  its lock, including when synchronous tools are still writing.

## Backend file map

| File | Responsibility |
| --- | --- |
| `backend/app.py` | FastAPI application factory, static UI, endpoints, input/body limits and SSE |
| `backend/demo_runner.py` | Lazy real-pipeline adapter, one-query orchestration and CLI |
| `backend/configurations.py` | Demo-only environment settings, authoritative presets and frozen snapshots |
| `backend/schemas.py` | Strict immutable query contract and clear request |
| `backend/assets.py` | Decode/validate/normalize real images |
| `backend/database_manager.py` | Demo collection creation/resumption, compatibility, counts and guarded point clearing |
| `backend/locking.py` | Nonblocking exclusive process/thread coordination |
| `backend/event_stream.py` | Typed event envelope, payload bounds/sanitization, domain-event adapter and SSE formatting |
| `backend/run_store.py` | Durable SQLite run index and per-run ordered event recording |
| `backend/run_manager.py` | Single execution thread, lock ownership and terminal result persistence |
| `backend/health.py` | Read-only service/model/configuration readiness checks |

## Phase 3 frontend

The UI lives in `frontend/` and is served at `/` by FastAPI. It has no Node build,
bundler, framework runtime, external font, or CDN dependency.

| File | Responsibility |
| --- | --- |
| `frontend/index.html` | Semantic three-column page, input form, service panel and reset confirmation dialog |
| `frontend/styles.css` | Central design tokens, UIUC theme, focus states and responsive layout |
| `frontend/model.js` | Pure ordered-event folding, repeated stage grouping and safe URL/status helpers |
| `frontend/network.js` | HTTP client and generic SSE frame parsing/reconnection |
| `frontend/view.js` | Safe DOM rendering of context, stages, metrics, sources and outcomes |
| `frontend/app.js` | Input handling, uploads, service/activity polling, run restore and UI state |
| `frontend/favicon.svg` | Local project mark; not an official university logo |

Theme tokens include Illini Blue `#13294B`, Illini Orange `#FF5F05`, white,
light gray and dark text. Altgeld `#C84113` is used for small orange text.
The header identifies MIRAGE-CARMA and the University of Illinois
Urbana-Champaign research-demo affiliation. Desktop uses three columns; smaller
screens stack the panels. The user has approved this visual direction.

Left column:

- Starter/custom question modes; editable text and explicit question type.
- Up to three images with original local previews/removal, state/county/month.
- Existing preset selector, actual read-only feature flags and readiness/busy
  gating for launch.
- Base/runtime status, accurate counts, last successful refresh, displayed-query
  count deltas, refresh and exact runtime-clear confirmation.

Center column:

- Actual ordered events grouped by stage/attempt, including repeated retrieval,
  confidence and augmentation.
- Stages remain running during intermediate candidate evaluations.
- Selection pins stage details; follow-latest mode can be re-enabled.
- Running/completed/skipped/disabled/not-invoked/error meanings remain distinct.
- Routine failed fetches stay in optional diagnostics rather than alarming
  primary timeline failures.
- SSE partial frames, deduplication, sequence-gap recovery and reconnection use
  the last accepted sequence. Disconnecting does not cancel inference.

Right column:

- Original question/images, captured preset and feature flags, crop-enriched text,
  visual observations, and actual retrieval/web queries.
- Per-collection competing strategy scores, eligibility/rejection, selected
  strategies, relevant chunk counts, raw similarities and retrieved passages.
- Actual confidence components/classification and existing thresholds; the
  evidence metric is not labeled as a calibrated probability.
- Web sources, domains, successful ingestion and count changes.
- Safe formatted answer, informational insufficient-evidence result, or distinct
  failed-stage message. Evidence supplied to generation is not represented as a
  statement-level source attribution map.

The browser remembers only a run ID in session storage. Reload restores input,
images, captured configuration and events from the backend. **Clear view** clears
the browser view/input only; it does not delete history, reset Qdrant or cancel a
server-side run. An active run can be followed again after clearing the view.

`examples/catalog.json` contains three **unvalidated starter questions**:
management retrieval, context-aware management, and plant identification requiring
the user's real image. No starter promises to trigger a particular path.

## HTTP and event contracts

| Endpoint | Purpose |
| --- | --- |
| `GET /` / `/assets/*` | UI and local assets |
| `GET /docs` / `/openapi.json` | Interactive API documentation |
| `GET /api/configurations` | Existing presets, default and supported capabilities |
| `GET /api/examples` | Explicitly unvalidated starter catalog |
| `POST /api/configurations/resolve` | Validated effective config snapshot |
| `POST /api/health` | Readiness for effective per-run settings |
| `GET /api/health?preset_id=...` | Readiness for the selected preset |
| `GET /api/activity` | Busy status and active run ID |
| `POST /api/runs` | JSON query or multipart request JSON plus actual images; returns 202/run ID |
| `GET /api/runs/{id}` | Saved input/config metadata, status and result |
| `GET /api/runs/{id}/events` | Live/stored ordered SSE with catch-up |
| `GET /api/runs/{id}/images/{index}` | Owned normalized image with index/resolved-path checks |
| `GET /api/runs?limit=20&offset=0` | Bounded backend history index and recent-run UI |
| `GET /api/database/status` | Base/runtime schema, status and point counts |
| `POST /api/database/runtime/clear` | Exact confirmation plus idle lock |

Query fields: `question`, `task_type`, `state`, `county`, optional `month_year`
(`YYYY-MM`), `preset_id`, and optional strictly boolean `overrides`. County requires
state. Unknown fields, unsupported feature combinations, client-side filesystem
paths and endpoint overrides are rejected.

For images use multipart `request` (query JSON) and repeated `images` file fields.
Allowed formats are still JPEG/PNG/WebP, at most three, 10 MiB and 20 megapixels
per image. Bytes are decoded, EXIF-oriented and normalized to JPEG to match the
existing generation client's JPEG data URLs. Served image paths are owned by
the run; symlink/path escapes are rejected.

Event schema version 1 includes: `run_id`, monotonic `sequence`, UTC `timestamp`,
`type`, `stage`, `iteration`, `status`, `visibility`, and bounded `payload`.
SSE IDs are `RUN_ID:SEQUENCE`. Reconnect via `Last-Event-ID`, or `?after=N`.
Events before subscription are retained. Invalid/wrong-run cursors return 422.

The backend supports both live catch-up and Phase 5 presentation replay. The UI
offers recent history, inspection and replay controls. Genuine validated replay
assets still require cluster runs; no forged recordings are bundled.

## Persistence, diagnostics and readiness

- Default state directory is `Demo/data/`, ignored by Git.
- Run index/event storage is `runs.sqlite3`; normalized images are under
  `runs/<run-id>/`.
- Defaults: 100 retained runs, 2,000 events/run, 48 KB event payload cap, 240 KB
  result cap. Large strings/arrays can be shortened explicitly. On the event
  limit, record a truncation event and reserve room for the terminal event.
- Retention prunes old terminal runs and their images. Run reset does not clear
  history. Interrupted runs are marked failed when the next lock owner recovers.
- Diagnostics rotate at 2 MB with three backups. Detailed errors remain in server
  logs; routine fetch failures can be inspected separately from primary UI events.
- SSE does not scrape stdout. Answer/source rendering uses safe DOM text and a
  small Markdown subset; no retrieved HTML is interpreted. Source links allow
  HTTP(S), rejecting executable/credentialed URLs.
- Readiness checks configured model IDs via `/models`, Qdrant and collection
  compatibility, crop dictionary, dependencies, embedding config cache, web key
  presence and writable image storage. It does not prove model inference or every
  embedding weight file is usable.
- API serves the offline UI and disables launch when required checks fail.
- Deployment is intended for a controlled host/tunnel. No authentication layer
  was added.

## Shared-code changes and protected files

Only optional, additive instrumentation was introduced to existing inference:

| Path | Change |
| --- | --- |
| `rag_agent/utils/observation.py` | New request-local observer context, exception-isolated emitter and signature-preserving tool decorator with no-observer fast path |
| `rag_agent/main.py` | Existing tracked tool boundary decorators; emit ingestion counts that were already measured |
| `rag_agent/utils/ContentUtils.py` | Emit existing candidate diagnostics and per-collection selected strategy |
| `rag_agent/tools/web_search.py` | Emit actual prepared web query and allowed domains |

No score, confidence formula, tool signature, strategy selection or default batch
behavior was intentionally changed. No new shared-code edits were made in Phase 3.

These files were checked byte-for-byte against their original committed versions
and remain unchanged:

- `Inference/generate.py`
- `Inference/bash_generate.sh`
- `rag_agent/ablation_configs.json`
- `rag_agent/model_instructions.md`
- `rag_agent/utils/inference_database_manager.py`

The existing entry point remains `cd Inference && bash bash_generate.sh`.
Never redirect a batch job to the persistent demo collection or modify global
preset/instruction files to configure a demo run.

## How to run

From the repository root in the cluster's existing `mirage` environment:

```bash
python -m pip install -r Demo/requirements.txt

export DEMO_RAG_URL=http://127.0.0.1:11434/v1
export DEMO_GENERATION_URL=http://127.0.0.1:11437/v1
export DEMO_RAG_MODEL=meta-llama/Llama-3.2-11B-Vision-Instruct
export DEMO_GENERATION_MODEL=meta-llama/Llama-3.2-11B-Vision-Instruct
export DEMO_QDRANT_URL=http://127.0.0.1:6333
export DEMO_CROP_DICTIONARY="$PWD/Inference/CropDatabase.json"
export DEMO_DATA_DIR="$PWD/Demo/data"
export DEMO_RUNTIME_COLLECTION=mirage_demo_runtime
export DEMO_DEVICE=cpu

# Set YOU_API_KEY and, if needed, QDRANT_API_KEY in the server environment.
# Use actual endpoint addresses and served model IDs for the allocation.
python -m Demo.backend.demo_runner init
python -m uvicorn Demo.backend.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

Open `http://127.0.0.1:8000/`. Forward port 8000 through the usual SSH tunnel when
the server is on the cluster. UI and API share one origin; no frontend build or
Node installation is needed. On a local machine without compute, start the API
directly to view the UI; model-backed launch will remain disabled.

Port 11437 follows the existing four-GPU batch layout. For a separate two-server
allocation, explicitly use the actual generation endpoint (for example 11435).
RAG and generation URLs must be distinct. Embeddings default to CPU, with
`BAAI/bge-base-en-v1.5` fixed to the existing schema.

Optional settings: `DEMO_TIMEOUT_SECONDS` (600), `DEMO_MAX_RUNS` (100), and
`DEMO_MAX_EVENTS` (2,000, minimum 20). Qdrant URL falls back to `QDRANT_URL`.
Settings never overwrite the batch environment's files.

CLI commands:

```bash
python -m Demo.backend.demo_runner status
python -m Demo.backend.demo_runner run --question 'Your real question' \
  --state Illinois --county Champaign --month-year 2026-06 \
  --output /tmp/demo-result.json
python -m Demo.backend.demo_runner run --task-type identification \
  --question 'Your real identification question' --image /path/to/real-image.jpg \
  --output /tmp/demo-identification.json
# Destructive only to the named demo runtime's points; do this only when intended:
python -m Demo.backend.demo_runner clear --confirm 'CLEAR mirage_demo_runtime'
```

Use the same data directory for API and CLI. CLI also records real events in the
run store. Diagnostics go to stderr, outcome to the requested output file and
stdout. A failed run exits 1; insufficient evidence is an informational outcome.

## Validation already performed

Phase 3 combined suite (historical):

```bash
PLAYWRIGHT_BROWSERS_PATH=/tmp/mirage-demo-browsers \
PYTHONDONTWRITEBYTECODE=1 /tmp/mirage-demo-venv/bin/python -m pytest \
  Demo/tests rag_agent/test_confidence_evaluator.py -q
```

Result: **45 passed, 2 dependency skips, 84 signature subtests passed**; one
upstream Starlette/AnyIO deprecation warning. This includes seven Chromium browser
tests against real loopback HTTP/SSE with explicitly synthetic inference.

```bash
node Demo/tests/frontend_model.test.mjs
```

Result: **6 JavaScript tests passed**. Node is only required for these development
tests, not serving the frontend.

Coverage includes:

- Existing preset/template/tool mapping, public signatures, endpoint partition,
  structured outcomes and pure confidence calculations.
- Observer/no-observer equivalence and observer exceptions preserving behavior.
- Actual strategy method event emission without changing its calculated result.
- Qdrant in-memory persistence, exact clearing, base/batch protection, incompatible
  vectors and alias rejection. This is not real server integration validation.
- Run/event isolation, monotonic order, bounded retention, interruption recovery,
  real local HTTP/SSE disconnect/reconnect and browser stream truncation recovery.
- API configuration/input/body validation, real image decoding/normalization,
  owned image serving and symlink escape protection.
- Single-run locking, busy reset, insufficient evidence and backend failure.
- Desktop three-column layout, mobile stacking/no horizontal overflow, keyboard
  operation, safe answer formatting/links, selected stage details and confidence
  components.
- Synthetic direct retrieval, augmentation loops and diagnostics, image
  identification, correct actual-image routing, exact confirmation, browser run
  restore and clear-view behavior without cancelling inference.
- Actual unmocked app served its offline UI, reported eight missing-service checks,
  and disabled inference. The user viewed this local UI and approved its appearance.
- JavaScript/Python syntax, `bash -n Inference/bash_generate.sh`, protected-file
  equality and `git diff --check` passed.

The two skipped legacy tests require `transformers`, unavailable in the local
lightweight environment. The additional dependency-light actual-method test
covers strategy observer equivalence, but does not replace full transformer
integration.

Optional test setup on another development machine:

```bash
python -m pip install -r Demo/requirements-test.txt
# Optional browser QA, not a cluster inference runtime requirement:
python -m pip install -r Demo/requirements-browser.txt
python -m playwright install chromium
PYTHONDONTWRITEBYTECODE=1 python -m pytest Demo/tests/browser -v
```

Without browser tooling/Chromium, the optional browser checks are skipped.

## Local-only artifacts and environment notes

These paths are temporary conveniences from this session, not portable project
dependencies; recreate them if absent in a later chat:

- `/tmp/mirage-demo-venv`: isolated test/preview Python environment. The local
  Python is 3.14; most packages matched the repository pins, but local Pillow 13
  was used because the pinned Pillow 11 wheel did not support this interpreter.
- `/tmp/mirage-demo-browsers`: downloaded Chromium for Playwright.
- `/tmp/mirage-phase3-ui.png` and `/tmp/mirage-phase3-ui-mobile.png`: actual offline
  UI screenshots without fake responses.
- `/tmp/mirage-phase3-result-fixture.png`: synthetic-result browser QA screenshot;
  do not present it as a real inference result.
- `/tmp/mirage-phase3-preview` and `/tmp/mirage-ui-preview`: temporary local preview
  state directories. They were separate from the default `Demo/data/`.
- The preview server was stopped at the latest user request. No model jobs or
  cluster processes were launched.
- The sandbox stalls the local Starlette TestClient event-loop wakeup before
  startup. Loopback API/browser tests passed outside that sandbox after tool
  approval. Do not interpret that sandbox stall as an application regression.

## Remaining work when cluster compute is available

1. Activate `mirage`, provide the actual endpoint/model IDs, dictionary and keys,
   verify the base schema and make `/api/health` ready for full-system mode.
2. Run a real direct-retrieval query through CLI and UI. Confirm separate RAG and
   final-generation model requests and actual structured evidence/status.
3. Run a real augmentation query. Inspect actual web search, domains, successful
   ingestion, counts and subsequent retrieval/confidence iterations.
4. Run two consecutive real queries without clearing; second `runtime_before`
   must equal first `runtime_after`. If neither ingests, persistence is tested
   but runtime growth still needs a genuine ingestion case.
5. Run real image identification. Extraction must succeed on real image input,
   appear inside the timeline/details, enrich retrieval and preserve actual-image
   input to generation. A fallback does not count as successful extraction.
6. Obtain a real insufficient-evidence outcome. Confirm no final generation
   request or speculative answer is displayed.
7. Validate UI behavior against the real traces: repeated stages, actual strategy
   scores/confidence, sources, SSE reconnect, busy launch/reset and count deltas.
8. When intentionally resetting, record base/batch counts, clear only demo runtime,
   then verify its zero count and unchanged base/batch data.
9. Run the small existing batch startup/multiworker smoke in the real `mirage`
   setup. A full benchmark run is not necessary just to check startup.

Do not claim the live gates passed based on the local fixtures. Document real
commands and outcomes once performed. If the user later authorizes more phases,
follow the original plan sequentially and preserve the existing batch workflow.

## Phase 4 validation

```bash
PLAYWRIGHT_BROWSERS_PATH=/tmp/mirage-demo-browsers \
PYTHONDONTWRITEBYTECODE=1 /tmp/mirage-phase4-venv/bin/python -m pytest \
  Demo/tests rag_agent/test_confidence_evaluator.py -q
node Demo/tests/frontend_model.test.mjs
```

Combined result: **56 passed, 2 dependency skips, 84 signature subtests passed**,
including eight Chromium browser tests. JavaScript: **6 passed**. One upstream
Starlette TestClient deprecation warning. After the combined run, the new browser
check was repeated for final checkbox styling/mobile layout, and the health check
was extended to assert effective custom requirements. Protected batch/config files
match HEAD; Python/JS/shell syntax and tracked whitespace checks passed. Legacy
transformer-dependent tests remain skipped in this lightweight local environment.
No live model/Qdrant inference was performed.

## Phase 4 implementation (2026-10-29)

- The user authorized Phase 4 after reviewing the Phase 3 handoff.
- `configurations.py` resolves optional overrides to existing instruction/tool
  workflows; it never uses the agent's fallback instruction. Five profiles cover
  static, progressive, uncertainty-aware, full without domains, and full with
  domains. DB/crop are independent: 20 supported combinations, 108 rejected.
- No new shared inference edits were required. The runner passes the matching
  actual ablation ID to MainAgent and applies DB/crop through existing inputs.
  Existing instruction and preset files remain authoritative and unchanged.
- Immutable snapshots retain source ID, explicit overrides, effective flags and
  `instruction_preset_id`. Authoritative preset drift rejects initialization.
- Query/API/CLI accept strictly boolean overrides. `/api/configurations` exposes
  supported fields/profiles; `POST /api/configurations/resolve` returns effective
  settings and `POST /api/health` checks their requirements. Run submission uses
  the same effective requirements. GET preset health remains supported.
- The UI offers a custom workflow selector and independent DB/crop controls;
  effective feature indicators refresh with readiness. Saved run details show
  the captured settings and instruction source. Existing enabled/not-invoked/
  disabled distinctions and persistent runtime semantics remain in place.
- Tests enumerate all 128 combinations, execute actual MainAgent configuration,
  instruction selection and tool registration methods for supported combinations,
  run synthetic runner smoke for all eight presets, and check custom API/browser
  snapshots and switching. These are local checks, not successful model inference.
- New isolated test environment: `/tmp/mirage-phase4-venv`; Chromium downloaded to
  `/tmp/mirage-demo-browsers`. These are temporary development tools.
- Remaining Phase 4 acceptance: real cluster smoke query for each of the eight
  presets, representative custom profiles, full-system default, switching after
  genuine ingestion, and batch startup/multiworker smoke. Record commands and real
  outcomes. Earlier live gates also remain pending. Phase 5 was subsequently authorized.

## Phase 5 implementation (authorized 2026-10-29)

Phase 5 concerns genuine saved replay controls/assets, a history UI, validated
real example bundles/provenance, operational runbook/fallback and conference
hardening. Stored-event replay and the history UI are implemented; genuine assets
and live validation remain pending.

Side-by-side comparisons, controlled ablation experiments, new algorithms and
concurrent attendee inference remain outside the initial demo scope.


Phase 5 now provides `backend/replay_manager.py`, POST replay creation and paced
SSE with original events, timestamps and sequence reconnect. Replay IDs reference
retained source runs; no duplicated recording is fabricated. History UI lists 20
recent records, opens saved results and replays traces with a persistent REPLAY
badge. Clear view aborts browser playback. Automatic Qdrant/model status polling
pauses during replay. Truncated traces are disclosed and expired runs report an
error. Replay never invokes runner, health or collection operations.

`CONFERENCE-RUNBOOK.md` documents setup, readiness, accumulated/fresh runtime,
recordings, retention/backup, privacy, interrupted-run recovery and failed-network
fallback. `examples/validation.md` records the pending real scenario validation
requirements. Existing starter questions remain explicitly unvalidated. There are
no genuine conference recordings/assets to bundle in this checkout.

Remaining: execute the full live matrix on the cluster, record genuine direct
retrieval/augmentation/identification traces with provenance, validate/select
reliable example bundles, verify sequential ingestion/counts and preset switching,
check runtime clear against base/batch counts, and perform batch startup smoke.
These cannot be claimed from synthetic local fixtures. Phase 5 acceptance remains
open until those real outcomes are documented.


Phase 5 validation: combined suite command from Phase 4 now reports **58 passed,
2 dependency skips, 84 signature subtests passed**, including nine Chromium
browser tests. Replay API tests compare original/replayed event sequences and
cursor recovery while runner, model readiness and collection status calls are
configured to fail if invoked. Browser coverage checks history, replay with
inference unavailable, persistent REPLAY labeling and saved inspection. JavaScript
suite: **6 passed**. Protected batch/config files remain equal to HEAD. One
upstream TestClient deprecation warning remains. All inference fixtures used in
these tests are explicitly synthetic; these results are not live acceptance.
