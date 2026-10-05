# Experimental Setup

## Model Roles and Inference Configuration

MIRAGE-CARMA separates final multimodal response generation from textual evidence acquisition. The response model receives the location-prefixed effective question, the available benchmark images, and, when retrieval succeeds, textual evidence produced by the evidence-acquisition stage. A separate tool-using evidence controller selects and invokes retrieval, confidence evaluation, query enrichment, keyword extraction, web search, and runtime ingestion capabilities according to the active experimental configuration.

The implementation exposes the response-generation and evidence-controller model endpoints separately, although both roles may use the same underlying checkpoint in a given experiment. Crop-query enrichment and keyword extraction also use the controller model endpoint. This separation defines functional roles rather than requiring distinct model families.

The study evaluates Qwen-3 vision-language models across the experimental conditions described below. The exact model checkpoints, revisions, and role assignments used in the final experiments remain to be recorded once all model runs are finalized. [DETAIL REQUIRES VERIFICATION: exact Qwen-3 checkpoints and revisions evaluated; model assigned to final response generation, evidence control, crop enrichment, keyword extraction, and judging; whether the same checkpoint is used across roles; context length; numerical precision or quantization; decoding settings; reasoning configuration; and final serving commands.]

Open-source models are served through SGLang's OpenAI-compatible interface. The repository pins

- `sglang==0.5.7`,
- `openai==2.6.1`,
- `litellm==1.80.0`,
- `google-adk==1.21.0`.

The Qwen-3 serving examples use the Qwen tool-call parser, multimodal support, and trusted remote model code. The exact context length and memory fraction may vary with model size and must therefore be recorded for each executed model configuration rather than inferred from example launch commands.

Final response generation uses the OpenAI-compatible client with a maximum completion length of 4,096 tokens, temperature

\[
T = 0.8,
\]

and nucleus-sampling parameter

\[
p = 0.95.
\]

Crop-query enrichment uses deterministic decoding with

\[
T = 0
\]

and a maximum output length of 1,024 tokens. The evidence controller does not independently set sampling parameters in the inference driver and therefore inherits behavior from the serving stack unless otherwise configured.

Input images are transmitted separately by default. An optional preprocessing path can combine at most three images into labeled panels with individual dimensions of

\[
512 \times 512
\]

pixels. Image combining is independent of the RAG ablation configuration and is disabled by default.

## Experimental Conditions

The evaluation comprises one direct-generation baseline and eight RAG configurations, for a total of nine experimental conditions.

The eight RAG configurations are defined in `rag_agent/ablation_configs.json`. The direct-generation baseline is selected independently through the `--no-rag` path.

| Experimental condition | Curated base | Crop enrichment | Progressive metadata filtering | Confidence | Web search | Domain filter | Runtime ingestion |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Direct-generation baseline (`--no-rag`) | off | off | off | off | off | off | off |
| Static RAG (`ablation_2_static_rag`) | on | off | off | off | off | off | off |
| Static RAG + crop dictionary (`ablation_3_static_rag_crop_dict`) | on | on | off | off | off | off | off |
| Progressive RAG (`ablation_4_progressive_rag`) | on | off | on | off | off | off | off |
| Confidence-aware RAG (`ablation_5_uncertainty_aware_rag`) | on | on | on | on | off | off | off |
| Full system without domain filtering (`ablation_7_full_no_domain_filter`) | on | on | on | on | on | off | on |
| Full system with domain filtering (`ablation_8_full_domain_filtered`) | on | on | on | on | on | on | on |
| Full adaptive system without curated base or crop dictionary (`ablation_9_full_no_db_no_crop_dict`) | off | off | on | on | on | on | on |
| Full adaptive system without curated base, crop dictionary, or domain filtering (`ablation_10_full_no_db_no_crop_dict_no_domain_filter`) | off | off | on | on | on | off | on |

The five controller-level switches governing progressive metadata filtering, confidence evaluation, web search, domain filtering, and runtime ingestion are loaded from the ablation configuration and applied by `MainAgent`. Tool registration is gated accordingly.

Curated-base access and crop-query enrichment are controlled separately at the inference-driver level. Curated-base retrieval is enabled or disabled through `--use_base_collection`. Query enrichment requires a usable crop-dictionary artifact and is disabled through `--disable_query_enrichment` when necessary. The direct-generation baseline bypasses the entire RAG path through `--no-rag`.

Consequently, a condition is defined jointly by its ablation identifier and its driver-level controls. For reported experiments, these bindings must be retained in the launch configuration or run manifest.

The experimental design supports several controlled comparisons. Static RAG versus Static RAG + Crop Dictionary isolates access to crop-aware query enrichment. Static RAG versus Progressive RAG isolates progressive metadata filtering when crop enrichment is disabled. The two full-system configurations with and without domain filtering isolate the domain-filtering mechanism while retaining confidence-aware web augmentation. Ablations 9 and 10 further examine adaptive retrieval when the immutable curated corpus and crop dictionary are unavailable.

Enabled capabilities represent access to a mechanism rather than proof that the controller invokes that mechanism on every benchmark item. Invocation behavior is therefore examined through manipulation checks and execution traces where available.

## Controlled Variables and Runtime State

Across experimental conditions, the intended controlled variables include

- benchmark records and ordering,
- collision-free record identifiers,
- model checkpoint and revision,
- prompt versions apart from condition-specific control instructions,
- embedding model,
- image-input policy,
- generation parameters,
- inference retry behavior,
- GPU allocation,
- worker topology,
- software environment,
- and, where applicable, the same immutable curated knowledge collection and crop-dictionary artifact.

Runtime collections are created independently for each experimental run. Fresh-mode execution creates a new collection for the selected ablation and prevents evidence accumulated under another condition from carrying into the new run.

Within a single web-enabled run, however, all RAG workers share the same mutable runtime collection. Evidence acquired for one benchmark item may therefore become available to subsequent items in that run. Because multiple retrieval requests can execute concurrently, the precise state visible to a query may depend on dispatch order, completion order, retries, and ingestion timing.

This shared runtime memory is an architectural property of MIRAGE-CARMA rather than an independent per-item cache. The final analysis must explicitly state whether accumulating cross-item runtime memory is retained as the intended experimental policy or whether additional isolation or replay controls are applied. [DETAIL REQUIRES VERIFICATION: final runtime-memory policy, number of independently initialized runs, and preservation or replay of ingestion order/state.]

## Benchmark and Evaluation Cohort

The standard MIRAGE benchmark contains 8,188 agricultural question-answer records distributed across seven task categories.

The three identification categories contain 4,324 records:

- 2,600 Plant Identification,
- 1,146 Insect and Pest Identification,
- 578 Plant Disease Identification.

The four management and guidance categories contain 3,864 records:

- 1,611 Plant Care and Gardening Guidance,
- 1,049 Plant Disease Management,
- 725 Insect and Pest Management,
- 479 Weeds/Invasive Plants Management.

Each benchmark record contains an expert response, one to three images, task-category information, entity annotations, geographic metadata, and an asked-time field. Expert answers and entity annotations are reserved for evaluation and are not supplied to the inference model.

The benchmark contains 8,184 unique identifier strings because four identifiers occur on two distinct rows. These duplicate identifiers correspond to distinct image filenames and therefore cannot safely be treated as unique row identifiers by an ID-keyed inference or splitting pipeline.

The final experimental cohort should therefore use a collision-free row identity or a documented duplicate-handling rule. The same frozen ordered cohort should be used for all experimental conditions.

[DETAIL REQUIRES VERIFICATION: final benchmark file/hash, collision-free identifier policy, any category or geographic filtering, validated image-path counts, final evaluation cohort size, and treatment of records with terminal generation or judging failures.]

## Retrieval and Corpus Configuration

All retrieval experiments use

`BAAI/bge-base-en-v1.5`

through SentenceTransformers. The resulting embedding dimensionality is

\[
d = 768.
\]

Runtime query encoding and runtime content ingestion explicitly request L2-normalized embeddings. Preload embeddings are submitted without explicit client-side normalization.

The live experimental Qdrant server was verified to run version

`1.18.0`

with commit

`db3fca327851e360c521065649e0f65a57fe7d3c`.

Both the live immutable base collection and a live ablation runtime collection were verified to use Qdrant's `Cosine` distance metric. Because cosine collections normalize vectors internally, the difference in explicit client-side normalization between preload and runtime embedding paths does not introduce a cosine-ranking inconsistency.

Runtime query text is truncated to the embedding model's 512-token limit.

The default retrieval budget is

\[
k = 5.
\]

Progressive metadata filtering evaluates every applicable strategy formed from a derived USDA plant hardiness zone and controller-supplied `month_year` and `title` metadata, together with unrestricted semantic retrieval. The benchmark's structured asked-time field is not independently serialized into the retrieval call and should therefore not be interpreted as the direct source of `month_year`.

For a candidate strategy \(a\) returning \(n_a\) semantically relevant hits with raw Qdrant cosine scores \(s_{a,j}\), its strategy-selection score is

\[
R(a)
=
\frac{1}{n_a}
\sum_{j=1}^{n_a}
\frac{1}{2-s_{a,j}}.
\]

The selected strategy is

\[
a^{*}
=
\operatorname*{arg\,max}_{a\in\mathcal{A}_{\mathrm{eligible}}}
R(a).
\]

Progressive metadata filtering is performed independently for the immutable curated collection and the run-scoped runtime collection. Retrieved passages are subsequently merged, deduplicated, globally ranked by raw cosine similarity, and truncated to the requested evidence budget.

The immutable curated database used by the experiments is `mirage_base_build`. When curated-base retrieval is enabled, inference assumes that this collection already exists and treats it as read-only. When the corresponding flag disables curated-base retrieval, the inference pipeline continues to use the mutable runtime collection.

The final preload-produced `mirage_base_build` corpus is still under construction. Its final source inventory, build identifier, snapshot identity, cryptographic hash, point count, document count, chunk count, geographic coverage, source coverage, and build date remain [DETAIL REQUIRES VERIFICATION].

The crop dictionary is a separate query-enrichment artifact rather than part of the vector corpus. Its final experimental version is also still under construction. [DETAIL REQUIRES VERIFICATION: final `CropDatabase.json` path, artifact hash/version, state and crop coverage, and binding to crop-enrichment-enabled conditions.]

## Web Search Protocol

Web-enabled configurations use the You.com search API through the endpoint

`https://ydc-index.io/v1/search`.

The system sends HTTP GET requests with a search query and requested result count. The evidence-controller wrapper requests up to 10 search results by default.

Each request uses a network timeout of

\[
15\ \text{seconds}.
\]

The web-search implementation itself does not implement an automatic retry loop after a failed HTTP request; request exceptions are returned to the controller as explicit search errors.

When domain filtering is disabled, the controller-generated keyword query is submitted directly to the search service.

When domain filtering is enabled, the system derives educational domains from the query's geographic context. Candidate domains are constructed from land-grant institutions associated with the benchmark state and universities associated with the derived USDA plant hardiness zone. At most six domains are used.

When eligible domains are available, the effective search query has the form

```text
<query> (site:<domain_1> OR ... OR site:<domain_n>) -site:.com -site:.org
```

for

\[
n \leq 6.
\]

If no appropriate domain mapping is available, the system falls back to the unrestricted keyword query even when domain filtering is enabled.

For each returned web result, the system retains the page title and URL. Temporal metadata is derived in the following order:

1. the You.com `page_age` field,
2. a provider-supplied `month_year` field,
3. the current machine month at search time.

The last case represents acquisition metadata rather than verified publication metadata.

Live search responses are not cached by `web_search.py`. Consequently, provider ranking, indexed content, and page availability may vary between runs. Reproducibility therefore requires retaining search timestamps and preferably the returned URLs or complete provider responses for the final experiments.

[DETAIL REQUIRES VERIFICATION: final search execution window and retained search-response artifacts used for the reported runs.]

## Runtime Web Ingestion

When the controller receives low confidence under a web-enabled configuration, its instruction requests keyword extraction followed by one web-search call. The controller is then instructed to attempt ingestion until either

\[
5
\]

pages have been successfully ingested or

\[
10
\]

candidate URLs have been attempted.

Downloaded page content is extracted and cleaned before chunking. Content exceeding the embedding model's 512-token limit is divided into windows of at most

\[
480
\]

tokens with an overlap of

\[
80
\]

tokens.

Runtime chunks are deduplicated against enabled collections using normalized-content hashes before insertion. Newly acquired web evidence is written only to the run-scoped runtime collection and never modifies the immutable curated base.

For recognized `.edu` sources, location metadata can be replaced by the mapped university state before canonical chunk metadata are constructed.

After ingestion, the controller is instructed to retrieve again and re-evaluate confidence. This multi-step sequence is prompt-directed rather than enforced as a deterministic Python state machine.

## Inference Hardware and Software Environment

Experiments are run on four NVIDIA A40 GPUs allocated concurrently:

\[
N_{\mathrm{GPU}} = 4.
\]

The standard inference topology assigns three GPUs to RAG/evidence-controller workers and reserves one GPU for final response generation:

\[
N_{\mathrm{RAG}} = 3,
\qquad
N_{\mathrm{generation}} = 1.
\]

The inference wrapper uses

\[
8
\]

generation worker processes and a RAG timeout of

\[
600\ \text{seconds}.
\]

The model servers expose consecutive OpenAI-compatible endpoints to the inference pipeline, with the final-generation endpoint separated from the RAG/controller endpoints.

The live Python environment observed during the ablation execution uses Python

`3.12.1`.

The repository dependency snapshot pins, among others:

- PyTorch `2.9.1`,
- Transformers `4.57.1`,
- SentenceTransformers `5.2.0`,
- SGLang `0.5.7`,
- Google ADK `1.21.0`,
- LiteLLM `1.80.0`,
- OpenAI Python `2.6.1`,
- Qdrant Client `1.18.0`,
- Trafilatura `2.0.0`,
- NumPy `2.2.5`,
- Pandas `2.2.3`.

The live Qdrant server independently reports version `1.18.0`.

The dependency set contains CUDA 12-series Python libraries, but the effective CUDA driver/runtime should be reported from the actual A40 execution environment rather than inferred solely from package pins. [DETAIL REQUIRES VERIFICATION: final CUDA version, NVIDIA driver version, operating-system environment, exact per-model SGLang launch command, and dependency-file/code revision used for each reported run.]

## Failure Handling

RAG execution distinguishes successful evidence acquisition from soft retrieval failure and infrastructure failure.

The structured RAG statuses include

\[
\{
\texttt{success},
\texttt{insufficient\_evidence},
\texttt{invalid\_output},
\texttt{timeout},
\texttt{connection\_error},
\texttt{model\_service\_error},
\texttt{worker\_error}
\}.
\]

On successful retrieval, structured evidence is appended to the effective query before final response generation.

For

\[
\texttt{insufficient\_evidence}
\]

or

\[
\texttt{invalid\_output},
\]

generation proceeds using the effective query without fabricated retrieval evidence.

Infrastructure failures are retried by the pipeline layer. After retry exhaustion, terminal hard failures skip final response generation.

The direct-generation baseline bypasses the RAG workers and crop-query enrichment entirely and generates from the location-prefixed benchmark question and images.

Final response generation makes up to five attempts per record, with a five-second interval between attempts.

## Evaluation Protocol

Evaluation treats identification and management/guidance tasks separately.

### Identification Tasks

For identification categories, the judge receives the benchmark question, expert response, annotated entity names, and generated model response. The judge produces

- binary entity-identification accuracy, and
- a reasoning-quality score from 0 to 4.

For \(N\) valid identification examples, with binary identification score

\[
a_i \in \{0,1\},
\]

mean identification accuracy is

\[
\operatorname{Acc}_{\mathrm{ID}}
=
\frac{1}{N}
\sum_{i=1}^{N}
a_i.
\]

The reporting script expresses this value as a percentage.

If

\[
r_i \in [0,4]
\]

denotes the identification reasoning score, mean reasoning quality is

\[
\overline{R}_{\mathrm{ID}}
=
\frac{1}{N}
\sum_{i=1}^{N}
r_i.
\]

This score is reported on its original 0--4 scale.

### Management and Guidance Tasks

For management and guidance categories, the judge assigns four scores from 0 to 4:

- factual accuracy \(A\),
- relevance \(R\),
- completeness \(C\),
- parsimony \(P\).

The reporting pipeline computes the composite management score

\[
S_{\mathrm{MG}}
=
\frac{2A + R + C + P}{20}.
\]

Accuracy therefore receives twice the weight of each of the other three dimensions.

For valid rubric scores,

\[
S_{\mathrm{MG}} \in [0,1].
\]

The existing evaluation scripts contain incomplete validation of malformed judge outputs. In particular, unsuccessful judge attempts can produce a sentinel value of `-1`, and existing cleanup behavior can remove these records rather than preserve an explicit terminal evaluation failure.

Before final reported evaluation, judge outputs should therefore undergo schema and range validation, and exhausted judge failures should receive explicit terminal statuses rather than silent exclusion.

[DETAIL REQUIRES VERIFICATION: final judge checkpoint and revision, judge prompt, decoding parameters, number of judgments per model response, handling of invalid outputs, repeated-judgment aggregation if used, expert/human validation or spot-check procedure, confidence intervals, and paired statistical testing.]

## Logging, Manipulation Checks, and Reproducibility

The inference pipeline persists per-item JSONL records containing the generated response or failure result together with retrieval-related execution information.

Recorded fields include information such as

- RAG endpoint,
- RAG attempt,
- RAG status,
- whether RAG context was used,
- web-search activity,
- confidence-related state,
- and final model chat history when generation succeeds.

Some internal controller behavior remains transient unless an additional execution trace is retained. In particular, complete tool sequences, tool arguments, selected retrieval strategies, retrieved chunk identities, effective enriched queries, URLs, and individual ingestion outcomes are not guaranteed to be represented as a complete structured trace in the primary output file.

For each reported experimental condition, the reproducibility record should bind at least

- code revision,
- experimental-condition identifier,
- benchmark hash and ordered cohort,
- model checkpoint and revision,
- response-generation and controller assignments,
- prompt versions,
- embedding model,
- `mirage_base_build` artifact identity when enabled,
- crop-dictionary artifact identity when enabled,
- runtime-memory policy,
- image-input mode,
- decoding parameters,
- hardware allocation,
- endpoint topology,
- concurrency,
- software versions,
- and execution timestamps.

For web-enabled conditions, the record should additionally retain search timestamps, returned URLs or provider responses, page-fetch outcomes, and runtime-ingestion behavior.

Manipulation checks should establish, where relevant,

- whether crop enrichment changed the query,
- whether progressive metadata filtering was invoked,
- which retrieval strategy was selected,
- confidence score and category,
- whether web search occurred,
- which URLs were returned,
- which pages were successfully ingested,
- whether previously ingested runtime evidence was reused,
- and which evidence was supplied to the final response model.

[DETAIL REQUIRES VERIFICATION: final per-condition launch manifests, complete inference outputs, retained controller/retrieval traces, runtime-state artifacts where required, search-response artifacts, and final judge outputs.]