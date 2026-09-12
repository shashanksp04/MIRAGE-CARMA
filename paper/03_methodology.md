# Methodology

## Task Formulation

We study retrieval-augmented response generation for agricultural questions that may require visual diagnosis, geographic context, and time-sensitive management guidance. For item $i$, the MIRAGE benchmark [@dongre2025mirage] supplies a natural-language question $q_i$, one to three images $I_i$, and location metadata $\ell_i$ consisting of a state and, when available, a county. Let $D$ denote an optional state-indexed crop dictionary. The implemented input transformation serializes $\ell_i$ as a textual prefix and may insert an allowlisted crop name into the question:

\[
q'_i=g(q_i,\ell_i,D).
\]

The generator receives no separate structured location channel. Let $K_b$ be the curated base collection and $K_r$ the mutable runtime collection. An evidence-acquisition stage $A$ operates on the effective text query, and a multimodal response stage generates

\[
E_i=A(q'_i;K_b,K_r), \qquad
y_i \sim p_\theta\!\left(y \mid q'_i,I_i,E_i\right).
\]

The two stages describe functional roles rather than necessarily distinct model checkpoints: the evidence agent, crop enricher, keyword extractor, and response generator may be served by the same checkpoint in a given configuration. The evidence stage receives text but no images; the response stage receives the effective query, image inputs, and any accepted evidence-agent output. The benchmark's structured asked-time field is not independently serialized by the prompt builder. Temporal and title filters are applied only when the tool-using model supplies `month_year` or `title` arguments, although a date may also occur in the question text itself.

MIRAGE denotes the underlying agricultural benchmark. We provisionally use *MetaMIRAGE++* for the proposed system; its implementation lineage is called MIRAGE-RAG or MetaMIRAGE in the repository artifacts, and the final manuscript name remains an author decision.

## MetaMIRAGE++ Overview

MetaMIRAGE++ comprises an offline knowledge-preparation procedure and an adaptive runtime pipeline. Offline workers are configured to extract web pages, PDF documents, and tabular records into a canonical representation, qualify their agricultural relevance, divide accepted material into overlapping token chunks, embed those chunks, and write them to a Qdrant build collection. Inference reads a fixed curated base collection named `mirage_base` and isolates online acquisition in a run-scoped runtime collection. A common payload and vector-search interface allows the retriever to merge evidence from these two inference collections without writing to the curated base.

At inference time, the system constructs $q'_i$ and invokes a tool-using language model. Python determines which tools are registered, while a natural-language instruction requests an evidence policy comprising retrieval, confidence evaluation, and conditional web augmentation. The driver accepts the agent's terminal text and, when its length-based success test passes, appends that text to $q'_i$ before response generation. The crop dictionary is therefore a query-transformation artifact rather than a retrieval corpus; it contributes no evidence directly.

The method-specific design lies in the combination of score-selected metadata strategies, a fixed confidence-routing heuristic, separation of curated and online-acquired evidence, and constrained crop insertion. Qdrant search, BGE embeddings through SentenceTransformers, Google ADK/LiteLLM orchestration, You.com search, and Trafilatura extraction are supporting components rather than contributions claimed by the method.

## Offline Knowledge Preparation

The implemented preload procedure is organized around independent state-level workers. Each worker extracts its assigned web, PDF, and CSV sources, persists canonical text and metadata in a state-local store, and records stage status in a state-local SQLite ledger. A coordinator serializes cross-worker state leases and content claims with atomic SQLite transactions. Document and chunk claims use normalized content hashes and expiring leases to support cross-worker deduplication and restart. Workers are configured to write vectors directly to the shared Qdrant build collection `mirage_base_build`; snapshot creation belongs to a separate wave finalizer.

Agricultural qualification is an LLM-based corpus-selection gate. The worker configuration uses `meta-llama/Meta-Llama-3.1-8B-Instruct` with 4-bit NF4 quantization. Canonical documents are divided into segments of 7,000 characters with 700-character overlap, up to 20 segments per document. The model assigns one of `crops`, `pest`, `disease`, `management`, `multi`, or `msc` and extracts crop-linked entities. Outputs undergo schema and content validation, failed segments are retried, and successful segment decisions are merged. A document is accepted exactly when its merged tag is not `msc`.

Accepted documents are independently re-chunked for retrieval. PDF text is chunked within page boundaries, whereas web and CSV text is chunked as a document stream. Retrieval chunks contain at most 480 embedding-model tokens with an overlap of 80 tokens and a hard limit of 512 tokens. The configured worker embeds batches of 64 chunks, upserts batches of 128 points, and assigns each point a deterministic UUID derived from source identifier, page, chunk index, and content hash. After all expected states in a wave report completion, the finalizer is configured to validate their manifests, merge state-level crop artifacts, snapshot the cumulative Qdrant build collection, and write a wave manifest.

These statements describe the implemented preload configuration. The completed experimental corpus is not established by checked-in run artifacts: its input sources, coverage, build identifier, snapshot identity and hash, and final document and chunk counts are [DETAIL REQUIRES VERIFICATION]. Inference additionally requires that the build artifact be provisioned as `mirage_base`; the snapshot promotion or restoration procedure is [DETAIL REQUIRES VERIFICATION].

## Metadata Representation

Each indexed chunk stores its text together with a canonical payload containing `source_type`, `source_id`, `title`, `url`, `page`, `chunk_index`, `location`, `month_year`, `content_hash`, `language`, and `hardiness_zone`. The source fields preserve provenance; page and chunk indices locate a passage within its source; and the SHA-256 content hash, computed after lowercasing and whitespace normalization, supports idempotent ingestion and cross-collection deduplication. Payload indexes are created for hardiness zone, month-year, title, and content hash because these fields participate directly in filtering or duplicate checks.

The `month_year` field is a mixed-provenance date proxy in `YYYY-MM` form. Offline extraction records a source date when one can be determined. Runtime search first uses a provider-reported page age, then a provider-reported month-year, and otherwise substitutes the acquisition month. Exact-match temporal retrieval can therefore filter either source time or retrieval time; the current payload does not distinguish them.

Geographic metadata is represented at two levels. The original state or state-county string is retained as `location`, while retrieval filters on a derived USDA plant hardiness zone [@usda2023phzm]. County-state pairs are resolved from a common mapping; when only a state is available or a county does not match, the implementation uses that state's modal zone. At query time, the same mapping contract converts the benchmark location into a zone. Unresolvable locations yield no geographic filter.

Optional query enrichment occurs before retrieval. The enrichment model receives a state-specific crop dictionary and an allowlist of crop names, and its instruction permits only the insertion of an allowlisted crop when the question clearly refers to one without naming it. Python post-validation requires a nonempty JSON response and checks that the original question remains a character-level subsequence of the enriched version, thereby rejecting deletions, substitutions, and reordered text. It does not independently verify that inserted characters form an allowlisted crop name; allowlist compliance remains prompt-directed. Parse failures, missing state data, and violations of the insertion-only constraint return the original query unchanged. The location prefix is separated before enrichment and restored afterward. The configured default dictionary path is absent from the repository, so the dictionary artifact used for the experiment, if any, is [DETAIL REQUIRES VERIFICATION].

## Progressive Metadata Retrieval

Questions and chunks are embedded with `BAAI/bge-base-en-v1.5` through SentenceTransformers and searched in Qdrant using cosine similarity. The preload worker submits unnormalized chunk embeddings, whereas runtime ingestion and query encoding request normalized embeddings. The precise cross-path equivalence under the deployed Qdrant version is [DETAIL REQUIRES VERIFICATION]. Runtime query text is truncated to the embedding model's 512-token limit. Let $s_j$ denote the raw Qdrant cosine score for hit $j$, where larger values indicate greater similarity. Given the metadata arguments in a tool call, the retriever constructs every applicable member of the candidate family

\[
\{z{+}m{+}t,\; z{+}t,\; t,\; m,\; z{+}m,\; z,\; \varnothing\},
\]

where $z$, $m$, and $t$ denote exact-match filters on hardiness zone, month-year, and title, respectively, and $\varnothing$ denotes semantic-only retrieval. A candidate is omitted when one of its required metadata values is absent or represented by a null-like sentinel. Candidates are evaluated in the displayed order, which also determines tie behavior in Python's first-maximum selection. When a retrieval call uses `use_progressive_filtering=false`, only the semantic-only candidate is evaluated. The run configuration supplies the default value, but the model-visible tool interface permits a call-specific override, as discussed below.

Rather than accepting the first nonempty filtered search, the system searches all applicable candidates using the same truncated query and embedding model; the implementation recomputes the query embedding inside each candidate iteration. The initial retrieval uses $k=5$. A candidate $a$ returning $n_a\geq1$ hits receives the selection score

\[
R(a)=\frac{1}{n_a}\sum_{j=1}^{n_a}\frac{1}{2-s_{a,j}}.
\]

The candidate with the greatest $R(a)$ supplies that collection's passages. The nonlinear transform is used only for within-collection strategy selection; cross-collection ranking and confidence evaluation use raw Qdrant scores. The intended effect is to retain metadata-scoped evidence when it has strong semantic matches while keeping semantic-only retrieval available when structured scope is incomplete or restrictive.

## Dual-Collection Retrieval and Runtime Isolation

Progressive metadata retrieval is applied independently to the read-only base collection and the active runtime collection. Each hit is labeled with its collection of origin, after which results are pooled, deduplicated, sorted by raw cosine similarity, and truncated to the global top $k$ (five by default). Duplicate identity is determined by content hash, then chunk identifier, and finally passage text; when equivalent content appears in both enabled collections, the base copy is retained. With the base disabled, duplicate checks and retrieval operate only on the runtime collection.

The diagnostic strategy label is inherited from the collection whose selected strategy returned more passages, while the evidence itself is the globally merged list. Equal result counts select the base collection's label because it is evaluated first. This label supplies the scope term in confidence scoring and consequently need not characterize every passage in the merged evidence.

The runtime collection is created once for an experimental run and shared by all inference workers. Its name contains the ablation identifier and a timestamp. Web additions are written only to this collection, so an acquisition completed for one item can affect another item's initial or confidence retrieval. Because worker retrieval and ingestion interleave, exposure depends on item order, worker count, queue scheduling, retries, and collection state. The experimental unit is therefore a stateful run rather than an independent item unless runtime state is explicitly isolated per item.

Fresh mode deletes matching runtime collections for the selected ablation before creating a new one; resume mode reconnects to the newest matching interrupted collection. Successful runs delete the runtime collection after an optional snapshot, whereas interrupted runs preserve it. These lifecycle choices prevent writes to `mirage_base`, but they also make freshness and resume policy part of the experimental condition. A PDF-ingestion tool can write page-aware content to runtime when registered; the evaluated low-confidence instruction, however, specifies URL ingestion from web-search results, and runtime PDF use is not established by persisted traces.

## Confidence Routing Heuristic

The confidence tool performs a fresh retrieval through the dual-collection path rather than scoring the passages returned by the initial tool call. Its model-supplied query, title, month-year, and $k$ arguments can therefore differ from the first retrieval, and concurrent runtime ingestion may change the searchable collection between the two calls. The default is $k=5$, but the tool accepts other positive values. For $n\geq1$ retrieved chunks with raw cosine similarities $s_1,\ldots,s_n$, it computes mean similarity $S$, count coverage $V$, score consistency $K$, and metadata scope $P$:

\[
S=\frac{1}{n}\sum_{j=1}^{n}s_j, \qquad
V=\min\left(\frac{n}{5},1\right),
\]

\[
K=\max\left(0,1-5\operatorname{Var}_{\mathrm{pop}}(s_1,\ldots,s_n)\right).
\]

For a single passage, $K$ is set to 0.7. Coverage always uses the fixed denominator five, even when the confidence call requests another $k$. The scope term assigns 1.0 to zone-month-title, 0.90 to zone-month, 0.85 to zone-title, 0.80 to zone, 0.75 to month, 0.70 to title, and 0.40 to semantic-only retrieval. As described above, $P$ is based on one collection's diagnostic label rather than the composition of the merged evidence. The overall routing score is

\[
C=0.50S+0.20V+0.20K+0.10P.
\]

Scores are rounded to three decimal places and mapped to *high* when $C\geq0.75$, *medium* when $0.50\leq C<0.75$, and *low* otherwise. The $n=0$ branch, including a confidence-retrieval exception, assigns $C=0$ and *low*. Coverage measures evidence quantity rather than semantic aspect coverage, and consistency measures dispersion in retrieval scores rather than factual agreement among sources. The weights and thresholds are fixed design choices with no recorded calibration procedure. Because $S$ is an unclipped cosine score, $C$ is an uncalibrated routing heuristic rather than a probability or a measure of epistemic uncertainty.

## Agent Control Flow and Web Augmentation

The evidence controller is a Google ADK language-model agent connected through LiteLLM to an OpenAI-compatible endpoint. Python always registers retrieval and conditionally registers confidence evaluation, keyword extraction, web search, and web/PDF ingestion. The model request specifies required function calling, but the multi-step policy is expressed in the agent instruction rather than a deterministic Python state machine. For the full configuration, that prompt-directed policy is

\[
\text{retrieve} \rightarrow \text{evaluate confidence} \rightarrow
\begin{cases}
\text{return evidence}, & C \text{ is high or medium},\\
\text{search} \rightarrow \text{ingest} \rightarrow \text{retrieve} \rightarrow \text{re-evaluate}, & C \text{ is low}.
\end{cases}
\]

The instruction asks for one keyword-extraction call and one web search when confidence is low, followed by URL ingestion until five pages succeed or ten URLs have been attempted, another retrieval, and another confidence call. It also asks the agent to reproduce retrieved passages verbatim and to return a fixed no-evidence message if confidence remains low. The driver observes tool-call events but does not validate their sequence or count, compare terminal text with tool returns, verify the confidence label, or enforce verbatim copying. These behaviors are therefore requested policies rather than guaranteed trajectories.

Run settings determine which tools are visible and provide default values for progressive retrieval and domain filtering, but model-visible arguments weaken strict configuration isolation. Both the retrieval and confidence tools accept `use_progressive_filtering`, and the web-search tool accepts `use_domain_filter`; when supplied, these arguments override the corresponding run-level values. Model-generated tool calls can therefore depart from the configured progressive-retrieval or domain-filtering condition even though tool availability remains configuration-gated.

Every registered web-search call uses the You.com API. When domain filtering is enabled and location-linked educational domains are available, the system builds a site-restricted query from at most six domains and adds exclusions for `.com` and `.org`. Candidate domains come from land-grant institutions associated with the state and universities associated with the derived hardiness zone. Their union is used when it contains at most six entries; for a larger union, the helper uses the intersection when nonempty and otherwise falls back to state-linked domains. If the mapping returns no domain, an enabled filter falls back to the raw keyword query with no site or suffix restrictions. Deliberately disabling filtering sends the same unrestricted query to the same endpoint.

Search results provide a URL, title, and the mixed-provenance month-year described above. Trafilatura extracts main page text, after which short lines and repeated whitespace are removed. Content longer than 512 embedding-model tokens is divided into 480-token windows with 80-token overlap. For recognized `.edu` domains, web ingestion replaces the supplied location with the university's mapped state; it also rejects calls without a valid month-year. Chunks are deduplicated against the enabled base collection and runtime collection, embedded, and upserted only into runtime. PDF ingestion is a separately exposed capability, but it is not part of the prompt-specified web augmentation path.

## Context Construction and Response Generation

The benchmark state and county are formatted as `[User location: <state>, <county>]` and prepended to the question. If query enrichment is enabled, its validated output becomes $q'_i$ for both evidence acquisition and final generation. The driver selects the last text event authored by the evidence agent. It does not parse or validate the requested `CONFIDENCE`/`EVIDENCE` template. If that text passes the success heuristic, context is constructed literally as $q'_i$ followed by the delimiter `additional context:` and the terminal agent text. The response model receives this text and the item images. Optional image combining places at most three images into labeled 512-by-512 panels and appends a panel-description hint.

The success heuristic treats a missing response or terminal text shorter than 30 characters as a soft failure and generates from $q'_i$ alone. Errors containing infrastructure keywords trigger at most one retry. After that retry, an error response with no agent text also falls through to the soft-failure path. A material mismatch remains between the prompt and driver: the full prompt's canonical low-confidence message, `No sufficient reliable information available to return.`, exceeds the 30-character threshold. If emitted without an accompanying error, the current driver marks it successful, appends it as additional context, and records `RAG_used=true`. The implemented success test therefore does not convert this prompt-specified no-evidence decision into an empty $E_i$.

## Behavioral Logging

The inference pipeline records an item-level summary of retrieval behavior in its JSONL output. For RAG-enabled runs, persisted fields identify the serving endpoint, retrieval attempt, whether a web-search call was observed, whether terminal agent text was used according to the length-based heuristic, and the final RAG status (`successful`, `soft_fail`, or `hard_fail`). Direct-generation records instead mark RAG as `disabled` and unused. A successful response generation also stores the response model's message history. Function-call names are printed as transient execution traces. Confidence values, selected retrieval strategies, retrieved chunk identifiers and text, the full tool-call sequence, and $q'_i$ are not persisted and cannot be reconstructed from JSONL alone. State-local preload ledgers record extraction, qualification, metadata, embedding, duplicate, retry, and upsert status; the coordinator separately records lease and cross-worker content-claim events.
