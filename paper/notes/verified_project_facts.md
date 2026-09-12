# Verified Project Facts

Evidence audit date: 2026-09-12. These notes distinguish executable code from design documentation. Claims below are safe source material for the manuscript unless a qualification says otherwise.

## System identity and scope

- The repository calls the implemented system both **MIRAGE-RAG** and **MetaMIRAGE**. The `MetaMIRAGE++` name does not occur in the implementation or project documentation and therefore is not yet a repository-verified system name (`README.MD:1-5`; `MSCdocs/CS597-REPORT.md:1-17`).
- The executable runtime is an agricultural, multimodal RAG pipeline: benchmark records contain a question, one to three image paths, an expert answer, category/entity fields, state, county, and asked time; the runtime adds location text to the question, retrieves textual evidence, and sends that evidence plus the images to a generation model (`Datasets/standard/standard_benchmark.json`; `Inference/generate.py:477-512`, `Inference/generate.py:779-823`).

## End-to-end inference architecture

- `Generate` loads the input JSON array, optionally skips IDs already successfully written to the JSONL output, optionally filters by state, and supports a no-RAG baseline (`Inference/generate.py:585-621`).
- The RAG path resolves one run-level runtime collection before creating workers. It uses Python's `spawn` multiprocessing context, creates one RAG worker per detected GPU (or one if none is detected), and maps workers to OpenAI-compatible endpoints beginning at port 11434 (`Inference/generate.py:623-704`; endpoint construction at `Inference/generate.py:28-50`).
- Rank 0 is started and required to report `READY` before the remaining RAG workers are started. All workers receive the same runtime collection name. A separate multiprocessing pool performs final answer generation; its size is controlled by `--num_processes` rather than GPU count (`Inference/generate.py:651-725`).
- Each RAG worker creates one `MainAgent`, optional `CropQueryEnricher`, and Google ADK `InMemoryRunner`. Each item gets a session ID of the form `rag_session_<item_id>` (`Inference/generate.py:228-267`, `Inference/generate.py:328-364`; `rag_agent/main.py:538-609`).
- The final context is constructed literally as `effective_query + "\n\nadditional context: " + rag_answer`. If RAG has a soft failure, generation receives the effective query without retrieved context. A hard RAG failure is retried up to two total RAG attempts and then skips generation (`Inference/generate.py:472-475`, `Inference/generate.py:779-803`).
- Final open-source-model generation uses `chat_models.Client` with `max_completion_tokens=4096`, `temperature=0.8`, and `top_p=0.95`; all valid images are encoded as data URLs and included unless optional image combining is enabled (`chat_models/Client.py:19-53`). Image combining is independent of ablations, retains at most three images, resizes each into a 512-by-512 panel, and adds a panel-description hint (`Inference/generate.py:57-116`, `Inference/generate.py:477-512`).
- The no-RAG baseline bypasses RAG workers and crop enrichment and generates from the location-prefixed user question and images. It records `RAG_status="disabled"` and `RAG_used=false` (`Inference/generate.py:539-583`).

## Qdrant collection architecture

- Normal inference separates a curated base collection from a mutable run collection. `mirage_base` is required when base use is enabled and is opened with `require_existing=True`; all web/PDF additions are bound to the runtime store (`rag_agent/main.py:40-92`).
- Runtime collection names are `mirage_runtime_<sanitized_ablation_id>_<YYYYMMDD>_<HHMMSS>`. Resume mode selects the newest matching collection; fresh mode deletes only runtime collections matching the selected ablation before creating a new one. A successful run optionally snapshots and then deletes the runtime collection; an interrupted run preserves it (`rag_agent/utils/inference_database_manager.py:10-20`, `rag_agent/utils/inference_database_manager.py:64-161`).
- Qdrant collections use cosine distance. The runtime manager fixes the vector size at 768 and indexes `hardiness_zone`, `month_year`, `title`, and `content_hash` as keyword payload fields (`rag_agent/utils/inference_database_manager.py:10-14`, `rag_agent/utils/inference_database_manager.py:86-107`).
- The default embedding model is `BAAI/bge-base-en-v1.5`. Runtime embeddings are produced by SentenceTransformers with automatic CUDA/CPU selection and normalized vectors (`rag_agent/utils/Embedding.py:6-25`; defaults in `Inference/generate.py:425-454`).
- Dual-collection retrieval queries the base (when enabled) and runtime stores separately, annotates hits with `retrieval_source`, merges them, deduplicates by `content_hash`, then `chunk_id`, then text, prefers a base copy when a duplicate exists in both, globally sorts by raw Qdrant cosine similarity, and returns at most `k` hits (`rag_agent/utils/dual_collection_retriever.py:4-46`). Cross-collection ingestion deduplication checks the base before the runtime collection (`rag_agent/utils/dual_collection_retriever.py:49-59`).

## Metadata representation and progressive retrieval

- The canonical runtime chunk payload contains `source_type`, `source_id`, `title`, `url`, `page`, `chunk_index`, `location`, `month_year`, `content_hash`, `language`, and `hardiness_zone`. If the hardiness zone is not supplied, it is derived from location (`rag_agent/utils/metadata.py:304-338`).
- Hardiness-zone lookup uses `Datasets/county_state_hardiness_zone.csv`. County-plus-state lookup is preferred; a state-only or unmatched-county query falls back to the modal hardiness zone for that state (`rag_agent/utils/metadata.py:212-301`).
- With progressive filtering enabled, each available combination in this set is evaluated: `hardiness_zone+month_year+title`, `hardiness_zone+title`, `title`, `month_year`, `hardiness_zone+month_year`, `hardiness_zone`, and semantic-only. With it disabled, only semantic-only retrieval runs (`rag_agent/utils/ContentUtils.py:177-224`).
- Each strategy retrieves up to five hits by default. Its selection score is the mean of `1/(2-s)` over returned raw cosine similarities `s`; among strategies returning at least one result, the highest-scoring strategy is selected (`rag_agent/utils/ContentUtils.py:226-316`).
- Location itself is not used as a Qdrant equality filter; it is normalized and converted to a hardiness zone (`rag_agent/utils/ContentUtils.py:177-185`).
- Query text is truncated to 512 tokens with the embedding model tokenizer before embedding (`rag_agent/utils/ContentUtils.py:242-256`).

## Confidence mechanism

- Confidence evaluation performs its own retrieval over the same dual retriever; it does not reuse a previously returned retrieval object (`rag_agent/tools/confidence_evaluator.py:76-91`).
- No results or a retrieval exception yields low confidence with score 0.0 rather than terminating the item (`rag_agent/tools/confidence_evaluator.py:92-118`).
- For nonempty evidence, the score is
  `0.50 * mean_similarity + 0.20 * coverage + 0.20 * consistency + 0.10 * scope`, rounded to three decimals. Coverage is `min(number_of_hits/5, 1)`. Consistency is `max(0, 1 - 5*population_variance)` for multiple hits and 0.7 for one hit (`rag_agent/tools/confidence_evaluator.py:120-152`).
- Scope weights are 1.0 for `hardiness_zone+month_year+title`, 0.9 for `hardiness_zone+month_year`, 0.85 for `hardiness_zone+title`, 0.8 for `hardiness_zone`, 0.75 for `month_year`, 0.7 for `title`, and 0.4 for semantic-only. Scores at least 0.75 are high, scores at least 0.5 and below 0.75 are medium, and lower scores are low (`rag_agent/tools/confidence_evaluator.py:133-171`).

## Agent control flow and web augmentation

- Control is hybrid: Python deterministically gates which tools are registered, while ablation-specific natural-language instructions tell the tool-calling model which sequence to execute. The ADK `LlmAgent` is configured through LiteLLM against an OpenAI-compatible endpoint with `tool_choice="required"` (`rag_agent/main.py:185-224`, `rag_agent/main.py:538-582`).
- The full instruction requires retrieval first and confidence evaluation second. High or medium confidence returns retrieved passages; low confidence instructs one keyword-extraction call, one web search, ingestion until five successful URLs or ten attempted URLs, then retrieval and confidence evaluation again (`rag_agent/model_instructions.md:20-69`). This loop is prompt-enforced rather than implemented as a deterministic Python loop.
- Keyword extraction uses the same served model as the RAG agent, asks for a JSON list, and has tolerant JSON/Python-literal parsing (`rag_agent/main.py:88-92`; `rag_agent/tools/keyword_extractor.py:91-180`).
- Web search calls the You.com search endpoint. When domain filtering is enabled and location-linked domains are available, it restricts the query to at most six domains and excludes `.com` and `.org`; otherwise it submits the unmodified search query (`rag_agent/tools/web_search.py:12-17`, `rag_agent/tools/web_search.py:101-125`).
- Candidate domains are drawn from state-linked land-grant domains and hardiness-zone-linked university domains. If their union has more than six entries, the helper prefers their intersection, falling back to state domains when the intersection is empty (`rag_agent/utils/metadata.py:71-182`).
- Search results preserve title and URL and derive `month_year` from provider `page_age`, a provider `month_year`, or, as the last fallback, the current month (`rag_agent/tools/web_search.py:152-196`). Runtime web ingestion rejects calls without `month_year` in `YYYY-MM` form (`rag_agent/main.py:417-435`).
- Runtime web pages are fetched and cleaned with Trafilatura/BeautifulSoup, chunked only when longer than 512 embedding-model tokens, using 480-token chunks with 80-token overlap, deduplicated by normalized-text SHA-256 across base and runtime, and upserted only to runtime (`rag_agent/utils/ContentUtils.py:28-48`; `rag_agent/tools/web_addition.py:238-353`). For recognized `.edu` domains, ingestion replaces the passed location with the university's state (`rag_agent/tools/web_addition.py:164-267`).
- The registered PDF tool extracts page text and tables with `pdfplumber`, turns table rows into header/value narratives, chunks each page into 480-token chunks with 80-token overlap, and writes canonical, deduplicated chunks to runtime (`rag_agent/tools/pdf_addition.py:31-119`, `rag_agent/tools/pdf_addition.py:168-259`). The supplied ablation prompts direct the low-confidence path through web addition, not PDF addition.

## Crop-context query enrichment

- The inference prompt prefix is `[User location: <state>, <county>]` when location metadata is available (`Inference/generate.py:477-482`).
- Crop enrichment is enabled only when the dictionary file can be resolved and `--disable_query_enrichment` is absent. The default requested file is `Inference/CropDatabase.json`, but no such file exists in the current repository checkout (`Inference/generate.py:386-401`, `Inference/generate.py:425-469`, `Inference/generate.py:870-920`; filesystem audit on 2026-09-12).
- When enabled, enrichment selects only the dictionary entry for the query's state, gives the served model an explicit crop-name allowlist, uses temperature 0.0 and a 1,024-token output limit, and accepts only outputs that preserve the original body as a subsequence (insertions only). Failures return the original query (`rag_agent/crop_query_enrichment.py:28-45`, `rag_agent/crop_query_enrichment.py:166-301`).

## Behavioral and output logging

- During RAG execution, the worker inspects ADK events, collects function-call names, extracts the last text emitted by `Rag_Agent`, and infers whether web search occurred from tool names (`Inference/generate.py:328-369`).
- Persisted per-item JSONL fields include the generated answer and chat history plus `RAG_endpoint`, `RAG_attempt`, `RAG_web_search_performed`, `RAG_status`, and `RAG_used`; generation failures also receive `generation_error` (`Inference/generate.py:155-195`, `Inference/generate.py:732-823`).
- Tool calls, confidence scores, selected retrieval strategies, retrieved chunk IDs/text, and effective enriched queries are printed or held transiently but are not written as structured fields to the inference JSONL by the current driver.

## Concurrent offline preload architecture

- The implemented concurrent preload consists of one generic notebook per state, a FastAPI/SQLite coordinator, a shared Qdrant service, and a separate wave finalizer (`preload_pipeline/NEW-ARCHITECTURE/MetaMIRAGE_Concurrent_Preload_Worker.ipynb`; `preload_pipeline/NEW-ARCHITECTURE/preload_coordinator.py`; `preload_pipeline/NEW-ARCHITECTURE/finalize_wave.ipynb`).
- The coordinator is a control plane only: it provides state leases/heartbeats, atomic document and RAG-chunk content claims, completion/status endpoints, and an audit-event table. Workers send vectors directly to Qdrant (`preload_pipeline/NEW-ARCHITECTURE/preload_coordinator.py:6-90`, `preload_pipeline/NEW-ARCHITECTURE/preload_coordinator.py:184-344`).
- State and content acquisition decisions use SQLite `BEGIN IMMEDIATE`; the database uses WAL mode. Default state and content leases are 1,800 seconds, with a minimum of 30 seconds and maximum of 24 hours (`preload_pipeline/NEW-ARCHITECTURE/preload_coordinator.py:114-133`, `preload_pipeline/NEW-ARCHITECTURE/preload_coordinator.py:271-347`).
- The worker auto-discovers PDF ZIP, CSV ZIP, and URL-list inputs; writes state-local ledger/canonical/crop/manifest artifacts; and runs the sequence discover, extract/canonicalize and document claim, qualify, retry/decide, create RAG chunks and metadata, validate Qdrant and index, retry/finalize documents, then validate and finalize the state (worker notebook cells 5, 19, and 39).
- The worker configuration uses `meta-llama/Meta-Llama-3.1-8B-Instruct` as a 4-bit NF4 qualification model and `BAAI/bge-base-en-v1.5` for embedding. It defines qualification chunks of 7,000 characters with 700-character overlap, at most 20 qualification chunks, and RAG chunks of 480 tokens with 80-token overlap and a 512-token hard cap. Embedding batches are 64 and Qdrant upsert batches are 128 (worker notebook cells 5 and 23).
- The worker's configured build collection is `mirage_base_build`; it validates but does not create/reset/restore/delete that collection. The finalizer uses the same collection name, validates explicit expected-state manifests and coordinator completion, atomically merges per-state crop output into the global crop artifact, creates a cumulative Qdrant snapshot, and writes the wave manifest last as the commit marker (worker notebook cell 5; finalizer notebook cells 2 and finalization workflow; architecture document `preload_pipeline/NEW-ARCHITECTURE/new-architecture-preload-pipeline.md:1171-1246`).

## Benchmark and evaluation protocol visible in the repository

- `Datasets/standard/standard_benchmark.json` contains 8,188 records, 8,184 unique IDs, 56 distinct `meta_data_state` values (including blank and non-U.S. labels), seven categories, and one to three images per record. Category counts are: 2,600 Plant Identification; 1,611 Plant Care and Gardening Guidance; 1,146 Insect and Pest Identification; 1,049 Plant Disease Management; 725 Insect and Pest Management; 578 Plant Disease Identification; and 479 Weeds/Invasive Plants Management (direct JSON audit on 2026-09-12).
- Four IDs occur twice: `#885475`, `#886705`, `#887327`, and `#883270`. Each duplicate pair has the same text metadata but distinct copied image filenames (`Datasets/standard/standard_benchmark.json`, direct JSON audit).
- `Inference/split.py` partitions three identification categories from four management categories and writes only completed model responses. It constructs an ID-keyed dictionary first, which collapses duplicate IDs (`Inference/split.py:7-18`, `Inference/split.py:71-122`).
- The identification judge is restricted to the three identification categories and produces a binary identification-accuracy score (0 or 1) plus a 0--4 reasoning-accuracy score (`Evaluation/LLMsAsJudges_ID.py:13-17`, `Evaluation/LLMsAsJudges_ID.py:37-80`).
- The management/general judge produces four 0--4 rubric scores: accuracy, relevance, completeness, and parsimony, using the question, expert answer, and model response (`Evaluation/LLMsAsJudges_MG.py:13-24`, `Evaluation/LLMsAsJudges_MG.py:41-90`).
- The score-reporting script reports identification accuracy as `mean * 100` and reasoning accuracy as its raw mean. For management, it reports raw metric means and a normalized weighted sum with accuracy weighted 2 and the other metrics weighted 1 (`Evaluation/print_scores.py:53-84`, `Evaluation/print_scores.py:93-123`).

## Qwen-3 evidence

- The current generation/RAG launch configuration does **not** configure Qwen-3. `Inference/bash_generate.sh` and `job_scripts/3gpu_4hr_script.slurm` select `meta-llama/Llama-3.2-11B-Vision-Instruct`; the Slurm script requests one node, three H200 GPUs, 125 GB RAM, eight CPUs, and five hours, and launches three SGLang servers on ports 11434--11436 (`Inference/bash_generate.sh:18-38`; `job_scripts/3gpu_4hr_script.slurm:2-11`, `job_scripts/3gpu_4hr_script.slurm:27-71`).
- Repository evidence for `Qwen/Qwen3-32B` is limited to its use as an **evaluation judge**, not the subject generation/RAG model. A historical log records judge model `Qwen/Qwen3-32B`, temperature 0.6, and 100 processes, scoring `gpt-4o-mini`; the current evaluation wrapper instead selects Llama-3.2-11B-Vision-Instruct (`Evaluation/logs/benchmark_run_Qwen3-32B.log:1-16`; `Evaluation/bash_LLMsAsJudges.sh:5-21`).
- `chat_models/Reasoning_Client.py` defaults to `Qwen3-32B`, sends `max_completion_tokens=10000` and a caller-provided temperature (default 0.6), and returns both content and `reasoning_content`. This client is used by the LLM-as-judge scripts for non-GPT judges (`chat_models/Reasoning_Client.py:4-41`; `Evaluation/LLMsAsJudges_MG.py:98-130`; `Evaluation/LLMsAsJudges_ID.py:91-126`).

## Ablation implementation

- `rag_agent/ablation_configs.json` contains seven configured IDs, not nine: IDs 2, 3, 4, 5, 7, 8, and 9. Matching instruction templates exist for those seven IDs plus `fallback_ablation` (`rag_agent/ablation_configs.json:1-72`; template markers in `rag_agent/model_instructions.md:1`, `:140`, `:304`, `:379`, `:454`, `:530`, `:632`, `:768`).

| Configured ID | Curated DB (declared) | Crop dictionary (declared) | Progressive | Confidence | Web | Domain filter | Ingestion |
|---|---:|---:|---:|---:|---:|---:|---:|
| `ablation_2_static_rag` | on | off | off | off | off | off | off |
| `ablation_3_static_rag_crop_dict` | on | on | off | off | off | off | off |
| `ablation_4_progressive_rag` | on | off | on | off | off | off | off |
| `ablation_5_uncertainty_aware_rag` | on | on | on | on | off | off | off |
| `ablation_7_full_no_domain_filter` | on | on | on | on | on | off | on |
| `ablation_8_full_domain_filtered` | on | on | on | on | on | on | on |
| `ablation_9_full_no_db_no_crop_dict` | off | off | on | on | on | on | on |

- Python applies only `progressive_filtering_on`, `confidence_on`, `web_search_on`, `domain_filter_on`, and `ingestion_loop_on`. It gates registered tools accordingly: retrieval is always registered; confidence adds the confidence tool; web adds web search and keyword extraction; ingestion adds web and PDF addition (`rag_agent/main.py:164-196`).
- `db_on` and `crop_dict_on` are declarative fields that are never read by the implementation. Base-collection use is controlled by `--use_base_collection`; crop enrichment is controlled by dictionary-file presence and `--disable_query_enrichment`; the pure baseline is controlled by `--no-rag` (`Inference/generate.py:619-637`, `Inference/generate.py:850-930`).
- An unknown or omitted ablation ID leaves all five Python toggles at their `True` defaults and selects `fallback_ablation`, which also registers the full tool list (`rag_agent/main.py:94-109`, `rag_agent/main.py:153-224`).
- The current `Inference/bash_generate.sh` defines `ABLATION_ID="ablation_8_full_domain_filtered"` but comments out the `--ablation_id` argument, so the launched driver receives its `default` ablation ID. It also sets `USE_BASE_COLLECTION="base"`; the CLI boolean parser recognizes only `1`, `true`, `yes`, or `on`, so that value evaluates to false (`Inference/bash_generate.sh:37-47`, `Inference/bash_generate.sh:62-77`; `Inference/generate.py:860-869`).
- The repository therefore verifies seven configuration records plus a separate `--no-rag` baseline path. It does not verify a complete nine-configuration experimental matrix or a launch harness that automatically iterates those conditions.
