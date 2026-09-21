Here is your structured `.md` documentation file content:

---

# RAG Pipeline Architecture & Change Log

This document serves as a **living architectural record** of major design decisions and structural changes made to the RAG + Generation pipeline.

Every time a significant change is made to the system, it should be documented here along with:

* What changed
* Why it changed
* What problem it solves
* Any trade-offs introduced

---

# 1️⃣ Original System Design

## Architecture Overview

Original pipeline structure:

```
Input Dataset
      ↓
Multiprocessing Pool Workers (N)
      ↓
Each worker independently:
    1. Run RAG
    2. Run Generation
      ↓
Write Output
```

### Characteristics

* Each pool worker triggered its own RAG execution.
* All RAG calls hit a **single GPU endpoint**.
* RAG and Generation were tightly coupled per request.
* No centralized RAG coordination.
* No backpressure control.
* No GPU-aware scaling.

---

## ❌ Flaws in Original Design

### 1. GPU Bottleneck

* Only **1 GPU**
* But multiple pool workers tried to use it simultaneously.
* Led to:

  * Queuing delays
  * Timeouts
  * Unpredictable latency

---

### 2. No Concurrency Control for RAG

* Multiple workers could overload the RAG model.
* No centralized request queue.
* No control over inflight requests.

---

### 3. Tight Coupling Between RAG and Generation

If RAG failed:

* Generation logic was unclear.
* Could skip or inconsistently handle failures.

---

### 4. Not Scalable to Multiple GPUs

If new GPUs were added:

* System would not automatically scale.
* No endpoint replication.
* No load balancing.

---

# 2️⃣ New Architecture (Current Implementation)

We redesigned the pipeline into a **multi-stage, GPU-aware architecture**.

---

## New High-Level Pipeline

```
Input Dataset
      ↓
Query enrichment
      ↓
Shared RAG Request Queue
      ↓
Three RAG Worker Processes (GPUs 0–2)
      ↓
Structured RAG Response Queue
      ↓
Single-concurrency Generation Worker (GPU 3)
      ↓
Write Output
```

---

## Stage 1: Shared RAG Request Queue

* All items first go into a **shared multiprocessing queue**
* RAG workers pull from this queue
* This ensures:

  * Controlled concurrency
  * No GPU overload
  * Proper backpressure

---

## Stage 2: RAG Worker Layer (GPU-Aware)

The default four-GPU allocation is fixed by workload:

* GPUs 0–2 run RAG workers at `11434`, `11435`, and `11436`.
* GPU 3 runs final benchmark generation at `11437`.
* Final generation starts with one active request at a time.

The split is controlled by `--rag_gpu_count` and `--generation_gpu_count`. It is intentionally not dynamically shared during initial experiments, so RAG and generation do not compete for model memory, KV cache, or server scheduling.

Each GPU runs:

* One independent SGLang server
* One independent model replica
* Tensor parallel size = 1
* Fully independent batching & scheduling

### Benefits

* True data-parallel scaling
* No shared model memory
* No GPU contention
* Clear workload isolation and predictable generation latency

---

## Stage 3: Generation Worker (Dedicated GPU)

After RAG completes, generation consumes the structured RAG result on the dedicated generation endpoint. It is intentionally limited to one active request initially; `--num_processes` remains a compatibility option but does not override this controlled generation concurrency.

---

## RAG Outcome and Failure Handling

The current implementation does not use a generic `soft_fail` state or response-length heuristics. Outcomes are mutually exclusive:

* `success`: structured retrieved evidence passed semantic relevance and confidence requirements; evidence is appended to the effective query.
* `insufficient_evidence`: RAG completed correctly but reliable evidence was not found; generation uses the effective query without a fabricated context message.
* `invalid_output`: orchestration completed but structured retrieval state was malformed or missing; generation falls back to the effective query and records the invalid state.
* `hard_fail_timeout`, `hard_fail_connection`, `hard_fail_model_service`, `hard_fail_worker`: infrastructure failures. These are retried only by the pipeline layer and are skipped after the retry limit.

The application owns structured retrieval state (`RetrievalResult` / `RAGResult`), including evidence, strategy, confidence, web-search activity, and ingestion counts. The agent controls tool calls, but its final prose is diagnostic and does not determine RAG success.

Confidence evaluation is pure computation over the existing retrieval result. It performs no second Qdrant search, model call, or embedding. A query embedding is computed once per request and reused across progressive metadata strategies and post-ingestion retrieval.

---

# 3️⃣ Multi-GPU Workload Isolation

The standard four-GPU configuration is intentionally split by workload:

* GPUs 0–2: RAG workers on ports `11434`–`11436`.
* GPU 3: final benchmark generation on port `11437`.
* Final generation: one active request at a time.

The split is configured with `--rag_gpu_count` and `--generation_gpu_count`. A later experiment may evaluate a different split, such as 2+2, using observed RAG utilization and generation queue metrics. RAG and generation should not be dynamically shared in the initial architecture.

---

# 4️⃣ Historical Rank0 Initialization & Collection Reset Design

> This section documents the former ChromaDB runtime design. It is retained as
> migration history. The current runtime uses a server-managed Qdrant base and
> run-scoped runtime collection; rank 0 is a readiness barrier, not a
> collection-reset owner.

This section documents a critical architectural fix related to ChromaDB.

---

## The Problem

ChromaDB uses persistent collections.

When `reset_collection()` is called:

* It deletes the collection
* Then recreates it

However:

Each worker holds a **collection handle tied to an internal UUID**.

If one worker deletes the collection:

* Other workers still hold stale handles
* This causes:

```
Collection [UUID] does not exist
```

Even though the collection exists.

---

## Historical Solution: Rank0 Barrier Initialization

We implemented a startup coordination mechanism.

---

### Step 1: Start Rank0 First

In the former Chroma implementation, only the first RAG worker (Rank0):

* Calls `reset_collection()`
* Recreates the collection

---

### Step 2: Rank0 Signals READY

Rank0 sends:

```
("READY", endpoint)
```

through `rag_status_q`

---

### Step 3: Main Process Waits

The main process:

* Blocks until Rank0 reports READY
* If Rank0 fails → crash early

---

### Step 4: Start Remaining Workers

Only after Rank0 is READY:

* Other RAG workers are started
* They connect to the already-created collection
* No stale handles occur

---

## Why This Is Necessary

Because:

* Deleting a Chroma collection invalidates existing handles.
* Multiprocessing does not auto-refresh collection references.
* PersistentClient + SQLite backend makes this especially fragile.

This barrier ensures:

* Deterministic initialization
* No race conditions
* No UUID mismatch errors
* Stable startup behavior

---

# 5️⃣ Self-Healing Collection Rebinding

In addition to Rank0 control, we added a safety mechanism:

If `_tracked_retrieve_content()` detects:

```
Collection does not exist
```

It:

1. Rebinds the collection via `get_or_create_collection()`
2. Rebinds dependent tools
3. Retries once

This converts a crash into a recoverable event.

---

## Why This Matters

Multi-process systems must assume:

* External state may change
* Handles may become stale
* Recovery should be automatic

This makes the system production-resilient.

---

# 6️⃣ Current Architecture Summary

### ✔ GPU-Isolated

Three RAG workers use GPUs 0–2; GPU 3 is reserved for single-concurrency final generation.

### ✔ Controlled Scaling

The RAG/generation split is configurable through explicit GPU-count flags and should be adjusted using runtime utilization metrics.

### ✔ Qdrant Server Mode

Workers use HTTP clients against one server-managed Qdrant instance; the
curated base collection is read-only during inference.

### ✔ Deterministic Startup

Rank0 readiness is confirmed before remaining workers start, while collection
lifecycle is owned by the main driver.

### ✔ Clean Separation

RAG and Generation decoupled.

---

# 7️⃣ Future Changes Section

When making major changes, document:

```
Date:
Change:
Reason:
Impact:
Trade-offs:
```

---

Example Entry:

```
Date: YYYY-MM-DD
Change: Added self-healing collection rebinding.
Reason: Workers previously crashed due to stale Chroma UUID handles.
Impact: Increased reliability in multi-process environment.
Trade-offs: Slight overhead on first failure detection.
```

KeywordExtractor Fresh Client per Call:

```
Date: 2025-03-18
Change: KeywordExtractor now creates a fresh Client per extract_keywords call.
Reason: Reused Client accumulated messages across calls, causing context overflow, timeouts, and "Unknown error" failures in RAG logs.
Impact: Eliminates message accumulation; each keyword extraction is stateless. Prevents context window overflow and improves reliability.
Trade-offs: Slight overhead from creating a new Client per call (negligible compared to LLM latency).
```

---

# Final Notes

This pipeline is now:

* Multi-GPU scalable
* Backpressure-controlled
* Failure-aware
* Deterministically initialized
* Production-oriented

---

**End of Documentation**

---
