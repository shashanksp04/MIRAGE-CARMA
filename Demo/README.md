# MIRAGE-CARMA demo (phases 0–5 implementation; live acceptance pending)

For future-chat handoff context, read [status.md](status.md) first. It records
the authorized stopping point, completed work, validation evidence and remaining
cluster checks.

This adds a three-column web UI, standalone query runner and HTTP/SSE API on top
of the existing inference environment. Research presets, prompts,
retrieval/confidence formulas, and `Inference/generate.py` / `bash_generate.sh`
retain their existing behavior.

The default is `ablation_8_full_domain_filtered`: curated DB and crop dictionary
enabled. Identification queries with images always attempt visual extraction on
the RAG endpoint. Final generation receives the actual images and accepted
retrieved evidence. An `insufficient_evidence` outcome skips final generation.

## Cluster setup

Activate your existing `mirage` Python environment and work from the repository
root. This manifest is intentionally separate from batch requirements; most
packages already appear in the repository's inference manifest.

```bash
python -m pip install -r Demo/requirements.txt

# Existing model servers, one endpoint per role. Set actual served model IDs.
export DEMO_RAG_URL=http://127.0.0.1:11434/v1
export DEMO_GENERATION_URL=http://127.0.0.1:11437/v1
export DEMO_RAG_MODEL=meta-llama/Llama-3.2-11B-Vision-Instruct
export DEMO_GENERATION_MODEL=meta-llama/Llama-3.2-11B-Vision-Instruct
export DEMO_QDRANT_URL=http://127.0.0.1:6333
export DEMO_CROP_DICTIONARY="$PWD/Inference/CropDatabase.json"
export DEMO_DATA_DIR="$PWD/Demo/data"
export DEMO_RUNTIME_COLLECTION=mirage_demo_runtime
export DEMO_DEVICE=cpu
# Set YOU_API_KEY in this server environment for web-enabled presets.
# Set QDRANT_API_KEY if your Qdrant server requires it.

python -m Demo.backend.demo_runner init
python -m uvicorn Demo.backend.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

Open **http://127.0.0.1:8000/** in your browser. The same process serves the UI
and API; there is no frontend build, Node installation, or extra runtime package
to install for Phase 4. When running on your cluster, forward port 8000 using
your usual SSH tunnel, then open the local forwarded address.

The interface is visible even when model/Qdrant services are unavailable. It
reports readiness and disables inference until required services are ready.

## Phase 3 interface

- **Your question:** editable starter questions or a custom question, explicit
  question type, up to three actual images with previews, state/county/month,
  existing preset selection, and live collection status with confirmed reset.
- **Live pipeline:** ordered real events, repeated attempts, skipped/disabled
  states, selectable stages, follow-latest mode, and automatic SSE catch-up.
- **Evidence & answer:** original query/images, captured preset, crop enrichment,
  visual observations, actual retrieval/search queries, strategy scores and
  rejection reasons, confidence components/thresholds, sources, augmentation,
  and the final answer or insufficient-evidence/failure message.

Visual extraction stays in the timeline and details column. Source passages are
the actual evidence supplied to generation; individual answer statements are not
claimed to have mapped citations. Answer formatting uses a small text-only
Markdown renderer; retrieved HTML is not interpreted.

The page restores the run remembered in its browser session after reload. It
can follow a server-side active run and locks query/reset controls while busy.
**Clear view** only clears the browser view and input; it never cancels inference,
deletes history, or changes Qdrant. The runtime clear dialog requires the exact
collection-specific confirmation token and remains protected by the API lock.

`Demo/examples/catalog.json` is an explicitly unvalidated starter catalog.
The identification starter requires your image. No prepared examples claim to
trigger a particular retrieval or web-search path. Validated conference scenarios,
presentation replay and a run-history UI are implemented in Phase 5. Supported
custom configurations are implemented in Phase 4, described below.

Frontend source is isolated in `Demo/frontend/`: `model.js` folds events,
`network.js` handles the API/SSE connection, `view.js` renders safe DOM content,
and `app.js` manages inputs and application state. Central CSS tokens follow the
[Illinois color palette](https://brand.illinois.edu/visual-identity/color) and
[accessible web color pairings](https://brand.illinois.edu/web/web-color).

The model servers must support the existing agent's tool calling; the RAG model
must support image input for identification. `DEMO_GENERATION_URL` defaults to
the existing batch generation port 11437; use 11435 instead if you have a new
two-server allocation. CPU embedding is the demo default so the API does not
implicitly reserve a third GPU. The embedding model remains
`BAAI/bge-base-en-v1.5`, 768 dimensions, cosine.

Use one deployment and the same `DEMO_DATA_DIR` for the API and CLI. Local file
locks exclude overlapping runs and runtime clears, including between processes.
A separate server lock rejects multiple API instances on that data directory.
This is not a distributed lock across different machines/data directories.
Keep the API on the controlled conference host/tunnel; it has no authentication
layer. Do not use multiple uvicorn workers or reload during a live run.

Optional settings: `DEMO_TIMEOUT_SECONDS` (600), `DEMO_MAX_RUNS` (100), and
`DEMO_MAX_EVENTS` (2000, minimum 20). Qdrant's connection setting falls back to
`QDRANT_URL`. Configuration is server-side; clients cannot set endpoints, paths,
or collection names for inference. Feature overrides are strictly validated.

Readiness reports model IDs listed by `/models`, Qdrant collection/schema/counts,
crop dictionary validity, dependency availability, the embedding configuration
cache, and web-search key presence. It does not claim a model inference or all
weight files have been tested. Load/cache the embedding in the existing
environment before presentation. Startup creates/resumes only the demo runtime;
it never creates or modifies the base. If Qdrant was unavailable during startup,
run the CLI `init` command after it becomes available, then refresh health.

## CLI smoke runs

```bash
python -m Demo.backend.demo_runner status
python -m Demo.backend.demo_runner run \
  --question 'How should I manage corn rootworm in this field?' \
  --state Illinois --county Champaign --month-year 2026-06 \
  --output /tmp/demo-query-1.json
python -m Demo.backend.demo_runner run \
  --question 'What management options are supported for corn rootworm?' \
  --state Illinois --county Champaign --month-year 2026-06 \
  --output /tmp/demo-query-2.json

# Replace with a real identification question and image available on your cluster.
python -m Demo.backend.demo_runner run \
  --task-type identification --question 'What is affecting this plant?' \
  --state Illinois --image /path/to/real-image.jpg \
  --output /tmp/demo-identification.json
```

These are input examples, not validated conference scenarios or promises of an
augmentation path. Images must be still JPEG/PNG/WebP, at most three, 10 MiB each,
20 megapixels each. They are decoded, EXIF-oriented and normalized to JPEG because
the existing generation client uses JPEG data URLs. API callers upload bytes;
only the local CLI accepts filesystem paths. Query task type is explicit
(`management` by default); it is never inferred from question wording.

Each CLI run also saves its real event stream in the same run store as the API.
CLI diagnostics go to stderr, with the outcome written to the requested output
file and stdout. Exit code 1 means a failed run; insufficient evidence is a
completed informational outcome. No runtime cleanup occurs on exit.

## HTTP contract

OpenAPI is available at `/docs` and `/openapi.json`. API/event schema version is 1.

| Method and path | Behavior |
| --- | --- |
| `GET /` and `/assets/*` | Phase 3 UI and local static assets |
| `GET /api/examples` | Explicitly unvalidated, editable starter catalog |
| `GET /api/activity` | Busy status and currently active run ID |
| `GET /api/health?preset_id=…` | Readiness for a real preset; `ready` is explicit |
| `GET /api/configurations` | Eight authoritative presets, full-system default, supported override fields and workflow profiles |
| `POST /api/configurations/resolve` | Validate query configuration and return its effective snapshot |
| `POST /api/health` | Readiness for a query with overrides |
| `POST /api/replays` | Start presentation replay of a retained terminal run |
| `GET /api/replays/{id}/events` | Paced original events; sequence reconnect and speed 0.25–8 supported |
| `POST /api/runs` | JSON query or multipart upload; returns 202 with run ID and SSE URL |
| `GET /api/runs/{id}` | Immutable input/config metadata, status, result, last sequence, truncation flag |
| `GET /api/runs/{id}/events` | SSE for live or stored events; disconnect does not cancel inference |
| `GET /api/runs/{id}/images/{index}` | Owned normalized input image; bounded index and path checks |
| `GET /api/runs?limit=20&offset=0` | Bounded recent-run index |
| `GET /api/database/status` | Base/runtime compatibility, point counts, read-only role and check time |
| `POST /api/database/runtime/clear` | Exact confirmation, demo name allowlist and idle lock required |

```bash
curl -s http://127.0.0.1:8000/api/health
curl -s http://127.0.0.1:8000/api/runs \
  -H 'Content-Type: application/json' \
  -d '{"question":"How should I manage corn rootworm?","task_type":"management","state":"Illinois","county":"Champaign","month_year":"2026-06"}'

curl -s http://127.0.0.1:8000/api/runs \
  -F 'request={"question":"What is affecting this plant?","task_type":"identification","state":"Illinois"}' \
  -F 'images=@/path/to/real-image.jpg;type=image/jpeg'

# Use the returned run ID. Reconnect with the last received SSE id.
curl -N http://127.0.0.1:8000/api/runs/RUN_ID/events
curl -N -H 'Last-Event-ID: RUN_ID:17' \
  http://127.0.0.1:8000/api/runs/RUN_ID/events
```

Events contain `schema_version`, `run_id`, monotonic `sequence`, UTC `timestamp`,
`type`, `stage`, stage `iteration`, `status`, `visibility` and bounded `payload`.
SSE IDs are `RUN_ID:SEQUENCE`; numeric sequence cursors and `?after=N` also work.
An event from another run or a cursor beyond stored history returns 422. Events
emitted before subscription are retained. A slow/disconnected client does not
create an unbounded memory queue or stop the worker.

Strategy events carry the physical collection name. `strategy_selected` is the
winner within that collection; `retrieval_completed` describes the existing
dual-collection merged result. Scores and confidence diagnostics are the actual
repository calculations, not probabilities or recomputed UI metrics. Failed
fetch/ingestion operations have diagnostic entries and a skipped stage; only
successful ingestion emits `content_ingested`. Enabled-but-uninvoked tool stages
are listed explicitly in `tool_activity`.

Outcomes are `completed`, `insufficient_evidence`, or `failed`. Cancellation is
not offered in this phase. Busy submission/reset returns 409, invalid input 422,
unsupported content type 415, oversized request 413, and unavailable services 503.
Unknown custom fields are rejected. Missing original image files, unsupported
formats and image decoding errors fail before starting a query. Individual visual
extraction failure follows the existing text-only fallback and is recorded;
visual observations never replace the actual generation image.

Model/RAG timeouts are configurable; existing synchronous tools retain their own
timeouts. Graceful server shutdown waits for the active query so it cannot release
the collection lock while a tool is still writing.

## Collection safety and retention

The base is always `mirage_base`, read-only. Runtime must be `mirage_demo_runtime`
or `mirage_demo_runtime_<suffix>` and must name a physical collection, never an
alias. Existing incompatible vectors fail verification; stored data is not
recreated to change its schema. Reset deletes points only from the exact configured
demo runtime and retains the collection, indexes, base, batch collections and
run history. For the default name:

```bash
curl -s http://127.0.0.1:8000/api/database/runtime/clear \
  -H 'Content-Type: application/json' \
  -d '{"collection":"mirage_demo_runtime","confirmation":"CLEAR mirage_demo_runtime"}'
# Equivalent CLI, which also acquires the exclusive lock:
python -m Demo.backend.demo_runner clear --confirm 'CLEAR mirage_demo_runtime'
```

Do not clear between queries when validating accumulation. Runtime evidence is
shared across presets, including presets with ingestion disabled; disabling base
or ingestion does not clear prior evidence. Therefore these runs are not
controlled ablation comparisons. Counts refer to Qdrant points/chunks.

`Demo/data/runs.sqlite3` stores the durable index and append-only per-run events.
The oldest terminal runs and their images are pruned after the run limit. Event
payloads are capped at 48 KB; a run hitting the event limit records an explicit
truncation event and reserves room for its terminal event. Full results are capped
at 240 KB. Larger strings/nested arrays may be explicitly shortened. SSE readers
of an expired run receive 404 (or `history_expired` if already streaming).
Interrupted runs are marked failed when the next owner recovers the store.
Diagnostic files rotate at 2 MB with three backups. Raw tool logging may also
appear in the server console; SSE never scrapes that output. Stored questions,
evidence and images are private deployment artifacts, not public export traces.

## Validation

```bash
python -m pip install -r Demo/requirements-test.txt
PYTHONDONTWRITEBYTECODE=1 python -m pytest Demo/tests rag_agent/test_confidence_evaluator.py -q
node Demo/tests/frontend_model.test.mjs
```

Node is needed only for the optional event-model tests, not for serving the UI.
The browser suite is optional and uses explicitly synthetic inference fixtures
behind the real local HTTP/SSE API:

```bash
python -m pip install -r Demo/requirements-browser.txt
python -m playwright install chromium
PYTHONDONTWRITEBYTECODE=1 python -m pytest Demo/tests/browser -v
```

Local tests use explicit synthetic inference adapters and Qdrant's in-memory
client for lifecycle tests. A real loopback HTTP server tests SSE disconnect and
reconnect. With Chromium installed, the final result is **45 passed, 2 dependency
skips, 84 signature subtests passed**, plus **6 JavaScript tests passed**.
The Python suite includes seven browser tests. Without the optional browser
tooling, those tests are skipped. These do not substitute for the cluster
acceptance checks:

1. Confirm `/api/health` is ready with the full-system preset. Check both model
   services' logs to verify that RAG/visual/crop work and final generation use
   their respective endpoints.
2. Run two consecutive real queries without resetting. Confirm query 2's
   `runtime_before` equals query 1's `runtime_after`, and that runtime growth is
   explained by actual successful `content_ingested` events. If neither query
   ingests, persistence is checked but growth is not yet validated.
3. Run a real image identification query. Check visual extraction succeeds,
   attributes appear only in retrieval, and generation receives the normalized
   actual image. An extraction fallback is not a passing extraction test.
4. Use a real query that yields `insufficient_evidence`; verify no generation
   request occurs. A successful-evidence query does not validate this branch.
5. Disconnect/reconnect a live SSE client; check sequence continuity and repeated
   retrieval iterations. Submit a second run/reset while busy and expect 409.
6. Record base/batch counts, clear only demo runtime with confirmation, then
   verify demo count is zero and base/batch counts are unchanged.
7. Run your existing batch startup/small dataset smoke in the unchanged `mirage`
   setup. Keep the existing batch runtime lifecycle and outputs separate from
   demo state. The production entry point remains `cd Inference && bash
   bash_generate.sh`; do not use a full dataset run merely as a quick smoke test.
8. In the UI, validate one direct-retrieval query, one query that actually invokes
   augmentation, and an identification query with a real image. Check the timeline,
   query transformations, selected stage details, and final outcome against the
   real cluster trace. Local synthetic browser tests do not satisfy this live gate.

See [implementation-notes.md](implementation-notes.md) for phase boundaries,
test outcomes, shared edits and the explicit deferred cluster validation.


## Phase 4 configurations

Select an existing preset, then enable **Customize this preset** to choose a
supported workflow and independently enable curated knowledge and crop enrichment.
The feature list displays the effective seven flags. Identification image
observations remain always enabled for applicable inputs.

Five workflows are supported: static retrieval; progressive retrieval;
progressive retrieval with confidence; full augmentation without domain filtering;
and full augmentation with domain filtering. Each uses an existing instruction
section with exactly matching retrieval, confidence, search, domain and ingestion
flags. With the independent DB/crop settings this supports 20 combinations.
Web search and ingestion are currently coupled in supported templates; search
without ingestion, confidence without progressive retrieval, and other absent
workflow combinations return HTTP 422. The UI offers supported workflows together
rather than independent switches that would produce those unsupported combinations.
Existing runtime evidence remains searchable with ingestion disabled.

The API accepts an optional `overrides` object alongside `preset_id`. Keys are
`db_on`, `crop_dict_on`, `progressive_filtering_on`, `confidence_on`,
`web_search_on`, `domain_filter_on`, and `ingestion_loop_on`. Values must be actual
JSON booleans; unknown keys, strings, numbers and null values are rejected.
Omitted keys inherit the source preset. For example:

```json
{"question": "How should I manage corn?", "preset_id": "ablation_8_full_domain_filtered",
 "overrides": {"db_on": false, "crop_dict_on": false, "web_search_on": false,
               "domain_filter_on": false, "ingestion_loop_on": false}}
```

This selects the existing uncertainty-aware workflow with runtime-only retrieval
and crop enrichment disabled. The request retains the source preset ID; the
resolved snapshot records all flags, explicit overrides, and
`instruction_preset_id`. The same snapshot is used for readiness, execution,
events and saved results. Later changes to input controls do not alter a recorded
run. A preset edit between submission and initialization rejects the run.

For CLI use, pass the same JSON object to `--overrides`, for example:

```bash
python -m Demo.backend.demo_runner run --question 'How should I manage corn?' \
  --overrides '{"db_on": false, "crop_dict_on": false}' --output /tmp/demo-result.json
```

Custom settings do not reset the persistent demo runtime. Runs sharing accumulated
evidence remain illustrative rather than controlled ablation comparisons.
No new `MainAgent` override interface is needed: the demo passes the exact matched
instruction preset and applies the DB/crop flags through existing explicit inputs.
Live smoke queries for every preset and batch startup still require cluster compute.


## Phase 5 history and replay

The Recent runs panel lists the latest 20 retained executions. Inspect loads the
saved inputs, evidence and results. Replay recording presents stored events using
the same timeline with a persistent REPLAY badge and original timestamps. The UI
uses a fixed 4x presentation pace; the API supports `speed=0.25` through `8`.
An event is paced at 250 ms at 1x rather than reproducing original wall-clock delays.
Clear view stops playback. Neither inspection nor replay reruns inference or
changes collections. Periodic service/count polling pauses during replay.

Replay IDs refer to retained source run IDs. Running/no-event runs are rejected;
missing/expired recordings return 404. Truncated recordings are disclosed. No
model, web or Qdrant service is required for replay; the demo backend and its saved
data directory must remain available. There are no bundled genuine recordings
or validated conference examples yet. See [CONFERENCE-RUNBOOK.md](CONFERENCE-RUNBOOK.md)
and [scenario validation](examples/validation.md) for recording, retention,
privacy, fallback and outstanding live acceptance.
