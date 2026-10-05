# Methodology

## Task Formulation

We study retrieval-augmented response generation for agricultural questions that may require visual diagnosis, geographic context, and time-sensitive management guidance. For item \(i\), the MIRAGE benchmark [@dongre2025mirage] supplies a natural-language question \(q_i\), one to three images \(I_i\), and location metadata \(\ell_i\) consisting of a state and, when available, a county. Let \(D\) denote an optional state-indexed crop dictionary. The implemented input transformation serializes \(\ell_i\) as a textual prefix and may insert an allowlisted crop name into the question:

\[
q'_i = g(q_i, \ell_i, D).
\]

The generator receives no separate structured location channel. Let \(K_b\) denote the immutable preloaded base collection and \(K_r\) the mutable runtime collection. An evidence-acquisition stage \(A\) operates on the effective text query, and a multimodal response stage generates

\[
E_i = A(q'_i; K_b, K_r),
\]

\[
y_i \sim p_{\theta}\left(y \mid q'_i, I_i, E_i\right).
\]

The two stages describe functional roles rather than necessarily distinct model checkpoints: the evidence controller, crop enricher, keyword extractor, and response generator may be served by the same checkpoint in a given configuration. The evidence stage receives text but no images; the response stage receives the effective query, image inputs, and any accepted retrieved evidence. The benchmark's structured asked-time field is not independently serialized by the prompt builder. Temporal and title filters are applied only when the tool-using model supplies `month_year` or `title` arguments, although a date may also occur in the question text itself.

*MIRAGE* denotes the underlying agricultural benchmark. We use *MIRAGE-CARMA* (Context-Adaptive Retrieval with Metadata Awareness for Multimodal Reasoning) to denote the proposed system.

## MIRAGE-CARMA Overview

MIRAGE-CARMA comprises an offline knowledge-preparation procedure and an adaptive runtime pipeline. Offline workers are configured to extract web pages, PDF documents, and tabular records into a canonical representation, qualify their agricultural relevance, divide accepted material into overlapping token chunks, embed those chunks, and write them to the Qdrant collection `mirage_base_build`.

At inference time, `mirage_base_build` serves as the immutable preloaded knowledge collection when curated-base retrieval is enabled. Inference assumes that this collection already exists. If the base collection is unavailable or intentionally disabled for an experimental condition, the corresponding configuration disables curated-base retrieval and the system operates using only the run-scoped runtime collection. Online acquisition is isolated in this mutable runtime collection, and no web-acquired evidence is written back into `mirage_base_build`.

The system constructs \(q'_i\) and invokes a tool-using language model that acts as an evidence controller. Python determines which tools are registered, while a natural-language instruction specifies a policy comprising retrieval, confidence evaluation, and conditional web augmentation. Retrieved evidence is represented structurally and passed to the downstream response-generation stage when retrieval succeeds. The controller's terminal message is retained for diagnostic purposes rather than serving as the authoritative evidence source.

The crop dictionary is a query-transformation artifact rather than a retrieval corpus; it contributes no evidence directly. The method-specific design lies in the combination of progressive metadata filtering, a fixed confidence-routing heuristic, separation of curated and online-acquired evidence, run-scoped adaptive knowledge ingestion, and constrained crop insertion. Qdrant search, BGE embeddings through SentenceTransformers, Google ADK/LiteLLM orchestration, You.com search, and Trafilatura extraction are supporting components rather than contributions claimed by the method.

## Offline Knowledge Preparation

The implemented preload procedure is organized around independent state-level workers. Each worker extracts its assigned web, PDF, and CSV sources, persists canonical text and metadata in a state-local store, and records stage status in a state-local SQLite ledger. A coordinator serializes cross-worker state leases and content claims with atomic SQLite transactions. Document and chunk claims use normalized content hashes and expiring leases to support cross-worker deduplication and restart. Workers write vectors directly to the shared Qdrant collection `mirage_base_build`; snapshot creation belongs to a separate wave finalizer.

Agricultural qualification is an LLM-based corpus-selection gate. The worker configuration uses `meta-llama/Meta-Llama-3.1-8B-Instruct` with 4-bit NF4 quantization. Canonical documents are divided into segments of 7,000 characters with 700-character overlap, up to 20 segments per document. The model assigns one of `crops`, `pest`, `disease`, `management`, `multi`, or `msc` and extracts crop-linked entities. Outputs undergo schema and content validation, failed segments are retried, and successful segment decisions are merged. A document is accepted exactly when its merged tag is not `msc`.

Accepted documents are independently re-chunked for retrieval. PDF text is chunked within page boundaries, whereas web and CSV text is chunked as a document stream. Retrieval chunks contain at most 480 embedding-model tokens with an overlap of 80 tokens and a hard limit of 512 tokens. The configured worker embeds batches of 64 chunks, upserts batches of 128 points, and assigns each point a deterministic UUID derived from source identifier, page, chunk index, and content hash. After all expected states in a wave report completion, the finalizer is configured to validate their manifests, merge state-level crop artifacts, snapshot the cumulative Qdrant collection, and write a wave manifest.

These statements describe the implemented preload configuration. The completed experimental corpus is not yet available: its final source inventory, coverage, build identifier, snapshot identity, and final document and chunk counts remain [DETAIL REQUIRES VERIFICATION].

## Metadata Representation

Each indexed chunk stores its text together with a canonical payload containing `source_type`, `source_id`, `title`, `url`, `page`, `chunk_index`, `location`, `month_year`, `content_hash`, `language`, and `hardiness_zone`. The source fields preserve provenance; page and chunk indices locate a passage within its source; and the SHA-256 content hash, computed after lowercasing and whitespace normalization, supports idempotent ingestion and cross-collection deduplication. Payload indexes are created for hardiness zone, month-year, title, and content hash because these fields participate directly in filtering or duplicate checks.

The `month_year` field is a mixed-provenance date proxy in `YYYY-MM` form. Offline extraction records a source date when one can be determined. Runtime search first uses a provider-reported page age, then a provider-reported month-year, and otherwise substitutes the acquisition month. Exact-match temporal retrieval can therefore filter either source time or retrieval time; the current payload does not distinguish them.

Geographic metadata is represented at two levels. The original state or state-county string is retained as `location`, while retrieval filters on a derived USDA plant hardiness zone [@usda2023phzm]. County-state pairs are resolved from a common mapping; when only a state is available or a county does not match, the implementation uses that state's modal zone. At query time, the same mapping contract converts the benchmark location into a zone. Unresolvable locations yield no geographic filter.

Optional query enrichment occurs before retrieval. The enrichment model receives a state-specific crop dictionary and an allowlist of crop names, and its instruction permits only the insertion of an allowlisted crop when the question clearly refers to one without naming it. Python post-validation requires a nonempty JSON response and checks that the original question remains a character-level subsequence of the enriched version, thereby rejecting deletions, substitutions, and reordered text. It does not independently verify that inserted characters form an allowlisted crop name; allowlist compliance remains prompt-directed. Parse failures, missing state data, and violations of the insertion-only constraint return the original query unchanged. The location prefix is separated before enrichment and restored afterward. The final crop-dictionary artifact used in the experiments is not yet available and remains [DETAIL REQUIRES VERIFICATION].

## Progressive Metadata Filtering

Questions and chunks are embedded with `BAAI/bge-base-en-v1.5` through SentenceTransformers and searched in Qdrant using cosine similarity. Runtime ingestion and query encoding explicitly request L2-normalized embeddings, whereas preload embeddings are submitted without explicit normalization.

Both the live `mirage_base_build` collection and the live runtime collection used during ablation execution were verified to use Qdrant's `Cosine` distance metric under Qdrant server version `1.18.0`. Because Qdrant's cosine metric normalizes vectors internally for cosine search, the preload and runtime embedding paths are expected to be equivalent for cosine-based retrieval ranking despite the difference in explicit client-side normalization.

Runtime query text is truncated to the embedding model's 512-token limit.

Let \(s_j\) denote the raw Qdrant cosine-similarity score for retrieved hit \(j\), where larger values indicate greater similarity. Given the metadata arguments supplied in a retrieval-tool call, the retriever constructs every applicable member of the candidate strategy family

\[
\mathcal{A}
=
\left\{
z+m+t,\;
z+t,\;
t,\;
m,\;
z+m,\;
z,\;
\varnothing
\right\},
\]

where \(z\), \(m\), and \(t\) denote exact-match constraints on hardiness zone, month-year, and title, respectively, and \(\varnothing\) denotes unrestricted semantic retrieval.

A candidate strategy is omitted whenever one of its required metadata values is absent or represented by a null-like sentinel. Candidates are evaluated in the displayed order, which also determines tie behavior under Python's first-maximum selection. When a retrieval call uses `use_progressive_filtering=false`, the eligible strategy family reduces to

\[
\mathcal{A}_{\mathrm{semantic}}
=
\left\{
\varnothing
\right\}.
\]

The run configuration supplies the default value, but the model-visible tool interface permits a call-specific override, as discussed below.

We refer to this procedure as *progressive metadata filtering*. The term denotes evaluation across metadata-constrained retrieval strategies of varying specificity together with unrestricted semantic retrieval. It does not denote a sequential fallback that terminates at the first nonempty filtered result.

Instead, the system searches every applicable strategy using the same truncated query and embedding model. The implementation recomputes the query embedding inside each candidate iteration. Initial retrieval uses

\[
k = 5.
\]

For a candidate strategy \(a \in \mathcal{A}\) that returns \(n_a \geq 1\) hits with similarity scores

\[
s_{a,1}, s_{a,2}, \ldots, s_{a,n_a},
\]

the system computes the strategy-selection score

\[
R(a)
=
\frac{1}{n_a}
\sum_{j=1}^{n_a}
\frac{1}{2-s_{a,j}}.
\]

The selected retrieval strategy is

\[
a^{*}
=
\operatorname*{arg\,max}_{a \in \mathcal{A}_{\mathrm{eligible}}}
R(a),
\]

where

\[
\mathcal{A}_{\mathrm{eligible}}
\subseteq
\mathcal{A}
\]

contains only strategies whose required metadata fields are available.

The passages returned under \(a^{*}\) supply that collection's candidate evidence. The nonlinear transformation in \(R(a)\) is used only for within-collection strategy selection; cross-collection ranking and confidence evaluation use the raw Qdrant cosine-similarity scores. The intended effect is to retain metadata-constrained evidence when it provides strong semantic matches while keeping unrestricted semantic retrieval available when structured metadata is incomplete, overly restrictive, or less relevant.

## Dual-Collection Retrieval and Runtime Isolation

Progressive metadata filtering is applied independently to the immutable base collection \(K_b\) and the active runtime collection \(K_r\).

Let

\[
H_b
=
\operatorname{Retrieve}(q'_i, K_b, a_b^{*}),
\]

and

\[
H_r
=
\operatorname{Retrieve}(q'_i, K_r, a_r^{*}),
\]

denote the passage sets selected independently from the base and runtime collections when those collections are enabled.

The two result sets are pooled:

\[
H
=
H_b \cup H_r.
\]

The pooled results are then deduplicated, ranked by raw cosine similarity, and truncated to the global top \(k\):

\[
E_i
=
\operatorname{TopK}
\left(
\operatorname{Deduplicate}(H),
k
\right).
\]

When curated-base retrieval is disabled, retrieval reduces to

\[
E_i
=
\operatorname{TopK}
\left(
\operatorname{Deduplicate}(H_r),
k
\right).
\]

Duplicate identity is determined by content hash, then chunk identifier, and finally passage text. When equivalent content appears in both enabled collections, the base copy is retained.

The diagnostic strategy label is inherited from the collection whose selected strategy returned more passages, while the evidence itself is the globally merged list. Equal result counts select the base collection's label because it is evaluated first. This label supplies the strategy term in confidence scoring and consequently need not characterize every passage in the merged evidence.

The runtime collection is created once for an experimental run and shared by all inference workers. Its name contains the ablation identifier and a timestamp. Web additions are written only to this collection, so an acquisition completed for one item can affect another item's subsequent retrieval. Because worker retrieval and ingestion interleave, exposure depends on item order, worker count, queue scheduling, retries, and collection state. The experimental unit is therefore a stateful run rather than an independent item unless runtime state is explicitly isolated per item.

Fresh mode deletes matching runtime collections for the selected ablation before creating a new one; resume mode reconnects to the newest matching interrupted collection. Successful runs delete the runtime collection after an optional snapshot, whereas interrupted runs preserve it. These lifecycle choices prevent writes to `mirage_base_build`, but they also make freshness and resume policy part of the experimental condition. A PDF-ingestion tool can write page-aware content to runtime when registered; the evaluated low-confidence instruction, however, specifies URL ingestion from web-search results, and runtime PDF use is not established by persisted traces.

## Confidence Routing Heuristic

The confidence tool scores the structured retrieval result returned by the preceding retrieval call; it does not retrieve, embed, or call a model again.

Retrieval uses

\[
k = 5,
\]

a hard raw-cosine similarity floor

\[
s_{\min} = 0.60,
\]

and requires at least

\[
n_{\min} = 2
\]

chunks whose raw cosine similarity satisfies

\[
s_j \geq 0.65.
\]

Let the semantically relevant retrieved chunks have similarities

\[
s_1, s_2, \ldots, s_n.
\]

The heuristic computes mean similarity \(S\), relevant-evidence coverage \(V\), score consistency \(K\), and metadata-strategy score \(P\).

Mean similarity is

\[
S
=
\frac{1}{n}
\sum_{j=1}^{n}
s_j.
\]

Relevant-evidence coverage is

\[
V
=
\min\left(
\frac{n}{5},
1
\right).
\]

For multiple relevant passages, consistency is defined as

\[
K
=
S
\max
\left(
0,
1
-
5\operatorname{Var}_{\mathrm{pop}}
(s_1,\ldots,s_n)
\right).
\]

For a single relevant passage,

\[
K = 0.
\]

The metadata-strategy term \(P\) is defined as

\[
P=
\begin{cases}
1.00, & \text{zone + month + title},\\
0.90, & \text{zone + month},\\
0.85, & \text{zone + title},\\
0.80, & \text{zone only},\\
0.75, & \text{month only},\\
0.70, & \text{title only},\\
0.40, & \text{semantic-only retrieval}.
\end{cases}
\]

The overall confidence-routing score is

\[
C
=
0.70S
+
0.15V
+
0.10K
+
0.05P.
\]

If the retrieved evidence fails the hard-floor or minimum-relevant-result requirement, the heuristic directly assigns

\[
C = 0.
\]

Otherwise, \(C\) is rounded to three decimal places and mapped to a categorical confidence level according to

\[
\operatorname{Confidence}(C)
=
\begin{cases}
\text{high}, & C \geq 0.78,\\
\text{medium}, & 0.60 \leq C < 0.78,\\
\text{low}, & C < 0.60.
\end{cases}
\]

Coverage measures relevant-evidence quantity rather than coverage of all semantic aspects of the question, and consistency measures dispersion in retrieval scores rather than factual agreement among sources. The weights and thresholds are initial design choices requiring empirical calibration. Because \(S\) is an unclipped cosine-similarity score, \(C\) is an uncalibrated routing heuristic rather than a probability or measure of epistemic uncertainty.

## Agent Control Flow and Web Augmentation

The evidence controller is a Google ADK language-model agent connected through LiteLLM to an OpenAI-compatible endpoint. Python always registers retrieval and conditionally registers confidence evaluation, keyword extraction, web search, and web/PDF ingestion. The model request specifies required function calling, but the multi-step policy is expressed in the agent instruction rather than a deterministic Python state machine.

For the full configuration, the intended prompt-directed control flow is

\[
\text{Retrieve}
\rightarrow
\text{EvaluateConfidence}
\rightarrow
\begin{cases}
\text{ReturnEvidence},
&
C \in \{\text{high},\text{medium}\},
\\[4pt]
\text{Search}
\rightarrow
\text{Ingest}
\rightarrow
\text{Retrieve}
\rightarrow
\text{ReEvaluate},
&
C=\text{low}.
\end{cases}
\]

If \(E_i^{(0)}\) denotes the initial retrieved evidence and \(C_i^{(0)}\) its confidence score, the adaptive branch can be summarized as

\[
E_i
=
\begin{cases}
E_i^{(0)},
&
C_i^{(0)} \geq 0.60,
\\[4pt]
A_{\mathrm{web}}
\left(
q'_i,
E_i^{(0)},
K_r
\right),
&
C_i^{(0)} < 0.60,
\end{cases}
\]

where \(A_{\mathrm{web}}\) denotes the prompt-directed search, ingestion, re-retrieval, and re-evaluation procedure rather than a deterministic Python transition function.

The instruction asks for one keyword-extraction call and one web search when confidence is low, followed by URL ingestion until either five pages have been successfully ingested or ten candidate URLs have been attempted. The controller then performs another retrieval and another confidence evaluation. It is also instructed to return retrieved passages and to return a fixed no-evidence message if confidence remains low. The driver observes tool-call events but does not deterministically validate the complete sequence or count of controller tool calls. These behaviors are therefore requested policies rather than guaranteed trajectories.

Run settings determine which tools are visible and provide default values for progressive metadata filtering and domain filtering, but model-visible arguments weaken strict configuration isolation. Both the retrieval and confidence tools accept `use_progressive_filtering`, and the web-search tool accepts `use_domain_filter`; when supplied, these arguments override the corresponding run-level values. Model-generated tool calls can therefore depart from the configured progressive-filtering or domain-filtering condition even though tool availability remains configuration-gated.

Every registered web-search call uses the You.com API. When domain filtering is enabled and location-linked educational domains are available, the system builds a site-restricted query from at most six domains and adds exclusions for `.com` and `.org`. Candidate domains come from land-grant institutions associated with the state and universities associated with the derived hardiness zone. Their union is used when it contains at most six entries; for a larger union, the helper uses the intersection when nonempty and otherwise falls back to state-linked domains. If the mapping returns no domain, an enabled filter falls back to the raw keyword query with no site or suffix restrictions. Deliberately disabling filtering sends the same unrestricted query to the same endpoint.

Search results provide a URL, title, and the mixed-provenance month-year described above. Trafilatura extracts main page text, after which short lines and repeated whitespace are removed. Content longer than 512 embedding-model tokens is divided into windows of at most

\[
480
\]

tokens with an overlap of

\[
80
\]

tokens. For recognized `.edu` domains, web ingestion replaces the supplied location with the university's mapped state; it also rejects calls without a valid month-year. Chunks are deduplicated against the enabled base collection and runtime collection, embedded, and upserted only into \(K_r\). PDF ingestion is a separately exposed capability, but it is not part of the prompt-specified web-augmentation path.

## Context Construction and Response Generation

The benchmark state and county are formatted as `[User location: <state>, <county>]` and prepended to the question. If query enrichment is enabled, its validated output becomes \(q'_i\) for both evidence acquisition and final generation.

The application records the structured retrieval evidence and uses its chunk text to construct the final context. Let

\[
\mathcal{C}_i
=
\operatorname{Concat}(E_i)
\]

denote the textual retrieval context constructed from the accepted evidence. The multimodal generator therefore conditions on

\[
\left(q'_i, I_i, \mathcal{C}_i\right).
\]

The controller's terminal message is diagnostic rather than the authoritative evidence source. Optional image combining places at most three images into labeled \(512\times512\) panels and appends a panel-description hint.

The driver records mutually exclusive structured RAG statuses:

\[
r_i
\in
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

When

\[
r_i = \texttt{success},
\]

the final generation context includes the accepted retrieved evidence.

When

\[
r_i
\in
\{
\texttt{insufficient\_evidence},
\texttt{invalid\_output}
\},
\]

the effective query \(q'_i\) is passed to generation without appending a fabricated no-evidence sentence. Hard infrastructure failures are retried by the pipeline layer and skipped after retry exhaustion.

## Behavioral Logging

The inference pipeline records an item-level summary of retrieval behavior in its JSONL output. For RAG-enabled runs, persisted fields identify the serving endpoint, retrieval attempt, structured RAG status, confidence category, confidence score, web-search activity, ingestion activity, authoritative retrieval state, and diagnostic controller message. Direct-generation records instead mark RAG as `disabled` and unused. A successful response generation also stores the response model's message history. Function-call names remain transient execution traces.