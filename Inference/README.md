# Batch inference (`generate.py`)

Place the runtime crop dictionary JSON as **`CropDatabase.json`** in this directory (same folder as `generate.py`) for query enrichment, or pass `--crop_dictionary_path` with another path. Use `--disable_query_enrichment` or `--crop_dictionary_path ""` to turn enrichment off.

Input-image combining is an independent run-level option and is not controlled by ablations. It is disabled by default. Pass `--combine_input_images true` (or `false`) to control whether valid input images are rendered into one labeled panel image before generation. `Inference/bash_generate.sh` exposes this as `COMBINE_INPUT_IMAGES`; enable it only for models or runs that require this workaround.

## Runtime architecture

`generate.py` uses a staged inference pipeline. In the standard four-GPU configuration, GPUs 0–2 are dedicated to RAG and GPU 3 is dedicated to final benchmark generation:

```text
Input dataset
    ↓
Shared bounded RAG request queue
    ↓
Three RAG workers on GPUs 0–2
    ↓
RAG response queue
    ↓
Single-concurrency generation worker on GPU 3
    ↓
Incremental JSONL output
```

The default endpoint mapping is `11434`–`11436` for RAG and `11437` for generation. Configure it with `--rag_gpu_count`, `--generation_gpu_count`, and `--rag_timeout_seconds`. Final generation concurrency is intentionally one request at a time so RAG and generation workloads do not compete for GPU memory or scheduling capacity. `--num_processes` is retained for CLI compatibility; generation uses controlled concurrency.

RAG outcomes are mutually exclusive:

- `success`: structured evidence passed retrieval/confidence requirements.
- `insufficient_evidence`: RAG completed, but reliable evidence was not found; generation falls back to the effective query.
- `invalid_output`: orchestration completed without valid structured retrieval state; generation falls back to the effective query.
- `hard_fail_timeout`, `hard_fail_connection`, `hard_fail_model_service`, or `hard_fail_worker`: infrastructure failure; the pipeline retries at the RAG layer and skips generation after the retry limit.

The final agent message is diagnostic only. Downstream generation receives the actual retrieved evidence recorded in structured RAG state, not a paraphrase of the agent response.

Query enrichment remains enabled by default and runs before RAG. It does not replace retrieval or change the structured outcome rules.

## Qdrant collections

Before a normal run, start Qdrant and set `QDRANT_URL` (default: `http://127.0.0.1:6333`). Inference uses two collection roles:

- `mirage_base` is the curated preload collection. It is read-only during inference and is required when `--use_base_collection true` is selected.
- `mirage_runtime_<ablation_id>_<YYYYMMDD>_<HHMMSS>` is selected or created for the run. Runtime web/PDF ingestion writes only to this collection.

The runtime collection is shared by all RAG workers and all queries in one run. `--runtime_mode resume` reuses the newest matching interrupted runtime collection; `--runtime_mode fresh` deletes matching runtime collections and starts a new one. A successful run optionally creates a snapshot with `--snapshot_runtime` and then deletes its runtime collection. Interrupted runs preserve it for resumption. `--runtime_collection_override` can select an existing runtime collection when resuming.

Use `--use_base_collection false` only for runtime-only development/testing. This skips base verification, base retrieval, and base-side deduplication while retaining the same runtime lifecycle and RAG code path.
