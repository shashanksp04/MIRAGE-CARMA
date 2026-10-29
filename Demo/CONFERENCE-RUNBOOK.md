# Conference operation

Use the cluster's `mirage` environment and the endpoint/environment setup in
[README.md](README.md). Start one uvicorn worker and tunnel port 8000. Keep API
keys in the server environment. This deployment is intended for a controlled host.

## Before presentation

1. Check service details for the selected configuration. Confirm model IDs,
   dictionary and embedding cache, Qdrant schema and collection counts.
2. Run real management retrieval, management augmentation and image identification
   inputs. Verify actual tool events and evidence, successful extraction, original
   image routing and the insufficient-evidence path. Starter questions are
   unvalidated until these outcomes have been observed.
3. Check two sequential runs without clearing. Verify matching before/after counts
   and genuine ingestion growth. Switching presets must preserve runtime points.
4. Record the run IDs, endpoint/model IDs, source/input provenance, scenario
   expectations and actual observed outcomes in `examples/validation.md`.
5. Inspect each saved run and replay it. Confirm the REPLAY banner and original
   events/results. Truncated traces are explicitly identified; prefer complete
   traces for the conference. Do not label synthetic fixtures as real recordings.
6. Confirm the existing batch startup/multiworker smoke on the cluster. Run the
   local validation suite documented in status.md after code changes.

## Live and replay operation

Use Live inference for new questions. Use Recent runs to inspect a saved outcome
or choose Replay recording. Replay has a fixed 4x presentation pace (62.5 ms per
recorded event), preserves original timestamps and uses the same timeline and
evidence renderer. It does not call models, web or Qdrant; automatic health/count
polling pauses while replay is displayed. Clear view stops browser playback and
leaves inference, run history and collections intact. Replay may be restarted.

If models/network/web fail, select a previously validated saved run and replay it.
The backend and browser must still be reachable; replay works without inference
services. No genuine recording is bundled in this checkout yet. If history is
empty, genuine runs must first be recorded on the cluster. An active run cannot
be replayed until it ends. Failed outcomes can be replayed for diagnosis.

## Retention and privacy

The SQLite run/event index and owned images live under DEMO_DATA_DIR. The default
retention is 100 runs; newer runs may expire older recordings. Preserve a backup
of the entire data directory while the server/CLI is stopped before presentation.
Use the same configured runtime collection identity on restore. Restore local
state before startup; never copy a live SQLite file alone and assume it is a
complete backup. Saved traces can contain user questions, images and source URLs.
Review them before using them with an audience or sharing a backup.

## Runtime reset and recovery

Accumulated mode is the default. For an intentionally fresh runtime, wait until
idle, record base/batch counts, and use the exact runtime confirmation dialog.
Verify runtime zero and unchanged base/batch counts. Reset retains recordings.
Shared accumulating runs are illustrative, not controlled ablation experiments.

After an interrupted process, restart with one worker. The backend marks unfinished
runs failed; inspect diagnostics under DEMO_DATA_DIR. Missing services disable live
launch but leave history/replay available. Refresh services after recovery. Replay
IDs reference retained source runs, so an expired recording returns an explicit
error and cannot be reconstructed. No authentication or public hosting is added.
