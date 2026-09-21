# Experimental Setup Review

## Overall assessment

The section is unusually careful about separating verified implementation facts from missing run metadata, and the benchmark audit is useful. It is not yet ready to support an experimental paper, however. The repository does not establish the requested Qwen-3 subject-model experiment, a nine-condition ablation matrix, or completed runs under the controls stated in the prose. The section should remain a provisional protocol until the blocking items below are resolved. In particular, the eight rows currently shown must not be described as nine conditions, and configuration intent must not be presented as executed experimental control.

## Blocking revisions

### 1. Establish Qwen-3's role with run evidence

The model assignment is unresolved at the center of the setup. The checked-in inference launcher selects `meta-llama/Llama-3.2-11B-Vision-Instruct` for both final generation and retrieval control (`Inference/bash_generate.sh:22-38`; `job_scripts/3gpu_4hr_script.slurm:29-63`). `Qwen/Qwen3-32B` is supported by the reasoning client and appears in a historical judge log, but that log records zero successful identification judgments in the displayed run (`chat_models/Reasoning_Client.py:4-41`; `Evaluation/logs/benchmark_run_Qwen3-32B.log:5-18,64-66`). The current evaluation wrapper selects Llama rather than Qwen (`Evaluation/bash_LLMsAsJudges.sh:6-20`). Thus, the Qwen paragraph at manuscript line 11 describes a possible or historical judge configuration, not a verified evaluator used for this study, and it provides no evidence that Qwen-3 is the subject model.

Before revision, obtain the actual run commands or manifests and state separately: (a) final multimodal answer checkpoint and revision, (b) retrieval-agent checkpoint and revision, (c) crop-enrichment/keyword-extraction checkpoint, and (d) judge checkpoint and revision. For each, report modality, reasoning mode, dtype or quantization, context limit, decoding parameters, serving engine/version, tool-call parser, endpoint topology, and hardware. If Qwen-3 serves only as judge, say so directly. If it is the subject model, verify that the exact checkpoint accepts the benchmark images. Remove the historical Qwen judge paragraph from the final setup unless it describes the judge actually used.

### 2. Resolve the nine-condition claim and make every row runnable

The table contains eight rows: one direct-generation baseline and seven RAG configurations. This matches the repository, which has only IDs 2, 3, 4, 5, 7, 8, and 9 in `rag_agent/ablation_configs.json`, plus a separate `--no-rag` path. No ninth runnable condition is checked in. The missing numeric IDs do not establish what the absent condition was intended to be.

There is also a gap between the table and execution. `db_on` and `crop_dict_on` are declarative JSON fields that `MainAgent` never applies; curated-base access and crop enrichment are controlled by separate driver flags (`rag_agent/main.py:164-196`; `Inference/generate.py:850-930`). The checked-in wrapper comments out `--ablation_id` and passes `base` to a boolean parser that recognizes only `1`, `true`, `yes`, or `on`, so that command selects the fallback/full agent policy while disabling the curated base (`Inference/bash_generate.sh:37-77`; `Inference/generate.py:850-869`). It cannot reproduce the table as written.

Supply an authoritative matrix and one validated launch manifest per row. Either add and define the missing ninth condition, or rename the study as eight conditions. Clarify whether “nine ablations” means nine total conditions or nine component removals in addition to a baseline. The manifest must bind each agent ID to `--no-rag`, `--use_base_collection`, crop dictionary path and disable flag, runtime mode, output path, and all five agent-level toggles. Until then, label the current table “repository-supported candidate configurations” rather than the executed experimental matrix.

### 3. Replace intended controls with verified controls

Manuscript lines 9, 36, and 52 say that image handling *is held fixed*, the protocol *holds fixed* models and hardware, and “we use” fresh collections. The adjacent verification markers acknowledge that no run manifests establish these facts. Convert these sentences to protocol requirements until manifests exist, then replace the markers with exact values and hashes from completed runs. At minimum, verify identical ordered benchmark rows, model revisions, prompts, generation and controller sampling, embedding revision, crop dictionary hash, base snapshot, image mode, retry policy, hardware, worker count, and code revision for every condition.

Randomness and replication also need a policy. The answer model samples at temperature 0.8, the controller's sampling configuration is not fixed in the driver, crop enrichment uses temperature 0, and live web search changes independently of model randomness. Define seeds where supported, the number of independent runs or judgments, and whether reported comparisons average over repeats. A single nominally controlled run cannot justify strong component-level causal language under this stochastic execution.

### 4. Account for within-condition shared-memory effects

A fresh runtime collection prevents cross-condition leakage, but it does not prevent cross-example influence within a web-enabled condition. All retrieval workers share one mutable runtime collection, and successful web ingestion remains available to later or concurrently processed benchmark items (`Inference/generate.py:623-704`; `rag_agent/utils/inference_database_manager.py:116-141`). With multiple workers and multiple in-flight requests, completion order can change which evidence is visible to another item. Benchmark order alone therefore does not reproduce a run, and the examples are not independent under web augmentation.

Decide whether this accumulating memory is an intended online-learning protocol. If it is, describe it explicitly, fix or record dispatch and completion order, preserve the runtime snapshot/traces, and analyze the dependence it creates. If each item is intended to be evaluated independently, isolate or reset the runtime collection per item, or ingest from a frozen per-item cache. Also state whether repeated conditions start from identical empty runtime stores.

### 5. Fix the benchmark unit and missing-output policy before scoring

The full file has 8,188 rows but only 8,184 unique ID strings. Resume logic uses IDs as keys, and `Inference/split.py` constructs an ID-keyed dictionary, silently retaining one row from each duplicate pair (`Inference/generate.py:590-606`; `Inference/split.py:71-76`). The splitter then writes only rows with completed model responses (`Inference/split.py:107-122`). Consequently, different failure rates can produce different evaluation sets across conditions, while duplicate-image records can disappear before scoring.

Define collision-free experimental record IDs and freeze the exact ordered ID list before inference. Require one terminal status for every intended row in every condition. Predefine whether hard retrieval failures, generation failures, soft RAG fallback, and invalid judge outputs count as failures, are rerun, or are excluded; report counts by condition. Scores should be computed on the same record set, with any paired analysis preserving row identity. Replace the benchmark marker with the selected benchmark hash, any geographic/category filters, the duplicate rule, and final counts for identification and management.

### 6. Specify and harden the evaluation protocol

The exact judge remains unverified. In addition, the local-judge paths only assert that expected keys exist; they do not validate score type or range. After five failed attempts, the scripts write `"score": -1`, while `print_scores.py` assumes `score` is a dictionary (`Evaluation/LLMsAsJudges_ID.py:91-139`; `Evaluation/LLMsAsJudges_MG.py:98-145`; `Evaluation/print_scores.py:66-76,105-122`). This can either admit malformed values or break aggregation. The management composite is also calculated from metric means rounded to two decimals, rather than from unrounded item-level values.

Record the final judge checkpoint/revision, full prompt hash, decoding settings, judgment count per response, repeat aggregation, and invalid-output policy. Enforce the declared integer ranges before accepting a judgment. State whether a human agreement or spot-check study was conducted; if none was, avoid implying that LLM scores are ground truth. Predefine confidence intervals and paired significance tests appropriate to the shared benchmark items. Preserve raw judge outputs and reasons for any exclusions.

### 7. Provide the actual curated-corpus artifact

Naming `mirage_base` and the embedding family is insufficient to reproduce the retrieval conditions. The repository does not contain a verified completed corpus manifest or the promotion step from `mirage_base_build` to `mirage_base`. Add the snapshot name and cryptographic hash, point/chunk/document counts, state and source coverage, build date, inclusion rules, embedding checkpoint revision, Qdrant server version, and promotion/restore procedure. Resolve the preload/runtime normalization discrepancy noted in `paper/notes/unresolved_questions.md` before asserting vector equivalence across the curated and runtime collections.

### 8. Make live-web comparisons reproducible

The domain-filter contrast can isolate its configuration switch only if other web inputs are controlled. Separate live searches at different times can return different pages for reasons unrelated to domain filtering, and the current output JSONL does not preserve queries, URLs, retrieved passages, or ingested hashes. Run both conditions against a versioned search-response cache or preserve complete request/response artifacts with timestamps and content hashes. Report provider parameters, requested result count, time window, failure/retry behavior, and ingestion success counts. Missing source dates are replaced with the current month (`rag_agent/tools/web_search.py:155-171`); label this as an ingestion-time fallback or remove it before using `month_year` as publication metadata.

The checked-in web-search implementation also contains an API credential in source rather than using the loaded environment variable (`rag_agent/tools/web_search.py:12-17,88-120`). Rotate that credential and remove it before any artifact release; do not include it in a manifest or manuscript.

### 9. Correct the description of temporal and progressive metadata

Manuscript line 50 refers to the “question month,” but `Generate.get_prompt` passes only the question plus state/county location and images; it does not pass the benchmark asked-time field (`Inference/generate.py:477-512`). `month_year` and `title` are optional arguments produced by the tool-calling model, not benchmark fields deterministically supplied to retrieval. Revise the prose to say that retrieval evaluates eligible combinations of hardiness zone and any agent-supplied `month_year` or title. If asked time is intended as an experimental feature, wire it explicitly into the query/tool call and document the transformation.

Also clarify that strategy selection occurs independently in the curated and runtime stores. After merging results, the reported strategy is taken from the store returning the larger result list, rather than from a global comparison of strategy scores (`rag_agent/utils/dual_collection_retriever.py:24-46`). Because this label contributes to the confidence score, the method and setup must either describe that rule or revise the implementation before the experiment.

### 10. Add manipulation checks for agent-mediated ablations

Tool registration and natural-language instructions make a capability available; they do not prove that the controller invoked it as prescribed. This matters for confidence evaluation, web search, the ingestion loop, and crop enrichment, each of which can fail or leave the query unchanged. The current JSONL records structured RAG status, confidence, retrieval state, web-search activity, ingestion count, and diagnostic agent text, while the complete tool sequence and source URLs remain outside the item-level record.

For each condition, retain and summarize manipulation checks: crop-enrichment attempted/changed/failed counts; retrieval and confidence call counts; selected strategies; low-confidence frequency; web calls; pages successfully ingested; structured retrieval-state reuse; explicit RAG outcomes; and evidence actually passed to generation. Without these checks, describe results as effects of *configuration access* rather than effects of components that definitely executed.

## Major but nonblocking revisions

1. Replace “uncertainty-aware” in explanatory prose with “retrieval-confidence-aware,” or explicitly state that the configuration name is inherited from the code. The implemented score is a fixed heuristic over similarity, coverage, consistency, and metadata scope; it is not calibrated model uncertainty.

2. Qualify “a retrieval call returns at most five chunks.” The tool exposes `k`, and confidence evaluation can receive an agent-provided value. Report the enforced experimental value or state that five is the default.

3. Describe endpoint loading accurately. Retrieval workers are distributed over consecutive endpoints, while final generation processes all use the single `--openai_api_base` endpoint. This affects throughput, contention, and reproducibility when the same server handles both roles.

4. State how missing image files are handled. The driver silently skips missing paths, which can change the visual input across rows. Validate all image paths before the run and report the count supplied per item after validation.

5. Distinguish environment availability from the executed environment. The dependency pins are useful, but call them the run environment only after recording Python, CUDA, driver, operating system, and Qdrant server versions from the actual jobs.

6. Explain that successful completion normally deletes the runtime collection unless snapshotting is enabled (`rag_agent/utils/inference_database_manager.py:143-157`). Any reproducibility claim based on retained adaptive evidence requires `--snapshot_runtime` or an equivalent export.

7. Keep the benchmark field inventory concise in the manuscript. The exact category and image-count audit is defensible, but the discussion of 56 state labels and duplicate filenames may fit better in a dataset-audit paragraph or appendix once the final cohort is fixed.

## Required revision order

The owning writers should first resolve the Qwen-3 role and authoritative condition matrix, then produce validated per-condition launch manifests. Next, freeze the benchmark IDs and failure policy, decide whether runtime evidence is shared across examples, and specify the web cache/artifact protocol. Only after those decisions should they revise the controlled-variable, inference-environment, and evaluation subsections. The remaining terminology and presentation edits can then be applied without risking another structural rewrite.
