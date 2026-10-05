# Limitations and Threats to Validity

## Scope and Generalizability

This study is scoped to multimodal agricultural questions represented by the MIRAGE benchmark [@dongre2025mirage]. MIRAGE covers seven task categories spanning identification, management, and gardening guidance and provides one to three images per record together with geographic metadata when available. Results obtained on this benchmark do not establish generality to other agricultural workflows, languages, countries, sensing modalities, or longitudinal decision settings.

A generated model response is also not equivalent to a diagnosis supported by field sampling, laboratory testing, repeated observation, or consultation with a domain expert. MIRAGE-CARMA should therefore be understood as an evidence-supported reasoning and response-generation framework evaluated within the benchmark setting rather than as a substitute for field-based agricultural diagnosis or management decisions.

Model-related conclusions are necessarily conditional on the checkpoints and serving configurations evaluated. Differences in model scale, revision, reasoning behavior, tool-call reliability, visual capabilities, decoding, or numerical precision may affect both evidence acquisition and final response quality. Results for the selected Qwen-3 models therefore should not be interpreted as estimates for the Qwen-3 family as a whole or for vision-language models generally.

The same restriction applies to the retrieval architecture. MIRAGE-CARMA evaluates dense retrieval using BGE embeddings, exact-match metadata constraints, progressive metadata filtering, a fixed confidence-routing heuristic, prompt-directed tool use, and run-scoped knowledge acquisition. The study therefore does not establish that the same effects would hold under alternative embedding models, sparse or hybrid retrieval, learned rerankers, calibrated confidence estimators, different agent-control mechanisms, or other adaptive-RAG designs.

## Curated Corpus Coverage and Selection

Retrieval quality is bounded by the content present in the immutable curated collection and, for adaptive configurations, evidence successfully acquired into the runtime collection. Relevant information absent from both stores cannot be recovered by retrieval.

The curated corpus is itself produced through an automated qualification procedure. Candidate source documents are segmented and classified by an LLM into agricultural relevance categories, after which segment-level decisions are combined into a document-level inclusion decision. This procedure provides scalable corpus construction but introduces dependence on the qualification model and its classification boundary.

No comprehensive human-labeled audit of the qualification stage is currently part of the experimental protocol. As a result, false-negative qualification decisions could exclude relevant sources, while false positives could introduce less relevant material. Corpus coverage and topical composition should therefore be interpreted as outputs of the implemented qualification pipeline rather than as a complete representation of authoritative agricultural knowledge.

The final composition of the curated database also depends on the source inventory gathered during preload. Even when the retrieval algorithm operates correctly, differences in source coverage across states, crops, pests, diseases, or management topics may influence downstream performance.

## Geographic Metadata as a Proxy

MIRAGE-CARMA derives geographic retrieval constraints using USDA plant hardiness zones [@usda2023phzm]. Hardiness zones summarize average annual extreme minimum winter temperature and are useful for broad regional growing conditions, but they are not comprehensive representations of agricultural context.

They do not directly encode factors such as

- soil type,
- rainfall,
- humidity,
- elevation,
- irrigation conditions,
- local pest pressure,
- cultivar,
- farm management practices,
- regulatory jurisdiction,
- or extension-service boundaries.

Two locations within the same hardiness zone may therefore differ substantially along variables relevant to diagnosis or management recommendations.

County-state pairs are mapped to a hardiness zone when possible. When only a state is available or a county cannot be resolved, the implementation falls back to the modal zone for that state. This improves coverage but suppresses within-state geographic variation.

The domain-filtering mechanism is similarly centered on U.S. agricultural institutions. It uses state-linked land-grant universities and hardiness-zone-linked academic domains. This design is appropriate for the current benchmark setting but would require a different authority and geographic mapping scheme for other countries or advisory systems.

## Temporal Metadata

The `month_year` retrieval field has heterogeneous provenance.

Depending on the source and ingestion path, it may represent

- an identified source publication date,
- a provider-reported page age,
- a provider-provided month-year value,
- or the month in which the page was acquired.

Consequently, exact temporal filtering does not always compare semantically equivalent notions of time.

This limitation is particularly relevant when the current month is used as a fallback for web-acquired evidence. In such cases, the value describes acquisition time rather than publication time. Temporal metadata should therefore be interpreted primarily as a retrieval signal rather than as a guaranteed representation of when the underlying agricultural claim was produced.

The MIRAGE benchmark also contains an asked-time field, but the current retrieval pipeline does not independently inject that structured field into retrieval. Temporal constraints arise only when suitable temporal information is available through the effective query or controller-generated tool arguments.

## Crop-Aware Query Enrichment

Crop-aware query enrichment depends on a state-indexed crop dictionary and a language model that is instructed to insert only an allowlisted crop name when the original question implicitly refers to that crop.

The implementation applies an insertion-only validation rule that requires the original question to remain a character-level subsequence of the enriched question. This prevents deletion, substitution, and reordering of the original query text.

However, the validator does not independently prove that every inserted character forms an allowlisted crop name or that an insertion is agronomically appropriate. Compliance with those semantic constraints remains partly dependent on the enrichment model.

The usefulness of enrichment is also bounded by the coverage and quality of the final crop dictionary. Crops absent from the state-level dictionary cannot be inserted, while state-level association is itself a coarse proxy for the crop implied by an individual user's question.

## Progressive Metadata Filtering

Progressive metadata filtering evaluates multiple metadata-constrained retrieval strategies together with unrestricted semantic retrieval and selects the strategy with the strongest aggregate retrieval score.

This design mitigates the risk of committing to a single overly restrictive metadata filter, but it remains dependent on exact-match metadata values and a fixed candidate strategy family. Metadata noise can therefore change which strategies are eligible, and potentially useful combinations outside the predefined family are not explored.

The strategy-selection function

\[
R(a)
=
\frac{1}{n_a}
\sum_{j=1}^{n_a}
\frac{1}{2-s_{a,j}}
\]

is a hand-designed aggregation rule rather than a learned ranking objective. The nonlinear transformation preserves monotonicity for individual similarity values but can change ordering between strategies relative to a simple mean of their raw similarities.

The experiments therefore evaluate this particular strategy-selection mechanism rather than progressive metadata retrieval in all possible forms. Alternative aggregation functions, learned selection policies, metadata-aware reranking, or joint optimization of semantic and metadata relevance remain outside the present scope.

## Confidence Routing

MIRAGE-CARMA uses a deterministic routing heuristic built from mean cosine similarity, relevant-result count, retrieval-score consistency, and a metadata-strategy term.

The resulting score

\[
C
=
0.70S
+
0.15V
+
0.10K
+
0.05P
\]

is not calibrated as a probability of correctness or evidence sufficiency.

The individual components are also proxies rather than direct measurements of evidence quality. In particular:

- high embedding similarity does not imply factual correctness;
- retrieval count does not measure coverage of every semantic aspect of the question;
- low score variance does not imply agreement among sources;
- and the diagnostic strategy label used in the score may originate from one collection even when final evidence contains passages from both the curated and runtime collections.

The thresholds controlling low-, medium-, and high-confidence routing are fixed design choices rather than thresholds learned from labeled evidence-sufficiency data.

The study can therefore evaluate whether this heuristic is useful operationally, but it should not be interpreted as demonstrating calibrated uncertainty estimation.

## Prompt-Directed Agent Control

The adaptive retrieval process is only partially deterministic.

Python determines which tools are available for a particular experimental condition. The evidence controller then receives a natural-language instruction describing the intended sequence of retrieval, confidence evaluation, keyword extraction, web search, ingestion, and re-retrieval.

The controller is therefore instructed to follow the intended policy but is not implemented as a deterministic state machine. Tool availability and tool execution are distinct concepts: enabling a capability does not imply that the model invokes it on every record.

This limitation is especially important for component-level ablation analysis. A comparison between two configurations establishes a difference in available behavior, but attribution to a particular mechanism is strongest when execution traces also verify that the relevant tool or branch was actually invoked.

The tool interface additionally allows some call-level arguments to override default progressive-filtering or domain-filter settings. Effective behavior should therefore be interpreted from the resolved calls rather than solely from configuration labels.

## Live Web Search

Adaptive configurations rely on live You.com search results. Search-provider rankings, indexed content, page availability, and source content may change over time.

The current search implementation does not cache responses internally. Two nominally identical experimental runs performed at different times can therefore observe different URL rankings or entirely different pages even when all model and retrieval parameters remain unchanged.

Retaining search timestamps, returned URLs, provider responses where practical, and downloaded page hashes improves auditability but cannot guarantee that an identical live search result can be recreated later.

The location-aware domain-filtering comparison has an additional interpretation limitation. Enabling domain filtering does not merely post-filter a common search-result set. It changes the actual search query by adding academic `site:` restrictions and `.com`/`.org` exclusions.

Consequently, the comparison between filtered and unfiltered search reflects the joint effect of source restriction and changed provider query formulation. Any measured difference should not be interpreted solely as the effect of source authority.

## Shared Runtime Memory

All RAG workers participating in one experimental run share the same mutable runtime collection.

When web evidence is acquired for one benchmark record, that evidence can subsequently be retrieved for another record within the same run. MIRAGE-CARMA therefore supports accumulation and reuse of acquired knowledge across queries.

This design is useful for evaluating an adaptive knowledge store, but it introduces dependence between benchmark examples. A response for item \(i\) may depend not only on its own inputs but also on evidence acquired while processing previous items.

Under concurrent execution, runtime state may additionally depend on

- dispatch order,
- worker scheduling,
- completion order,
- search latency,
- ingestion latency,
- failures,
- and retries.

Identical benchmark ordering alone therefore does not guarantee identical runtime state at each query.

If accumulating knowledge is retained as the final experimental protocol, the run rather than the individual record becomes the natural unit for some aspects of reproducibility. Multiple fresh runs would provide stronger evidence about variability introduced by concurrent adaptive memory.

Conversely, resetting the runtime collection per record would provide cleaner item-level independence but would evaluate a different system from the intended accumulating-memory architecture.

[DETAIL REQUIRES VERIFICATION: final experimental policy for shared runtime memory and number of independently initialized runs used for the reported analysis.]

## Benchmark Validity

MIRAGE provides a finite benchmark distribution and cannot represent the complete space of real agricultural questions.

Each benchmark item also contains one expert reference response. A generated answer can be agronomically reasonable while differing in emphasis, specificity, or recommendation from that single reference. Reference-mediated evaluation may therefore underestimate valid alternative responses or favor stylistic agreement with the provided answer.

The benchmark also contains four identifier strings that each occur on two distinct rows with different image files. ID-keyed processing can collapse these rows if the identifier alone is treated as the record key.

This is an implementation-level cohort issue rather than an inherent conceptual limitation of MIRAGE, and it can be eliminated by assigning collision-free row identities before final inference and evaluation.

[DETAIL REQUIRES VERIFICATION: final collision-free cohort policy and benchmark hash used in the reported experiments.]

## LLM-as-a-Judge Evaluation

The evaluation protocol uses a language model to score generated responses against benchmark reference material.

For identification tasks, the judge evaluates entity identification and reasoning. For management tasks, it evaluates factual accuracy, relevance, completeness, and parsimony.

These scores measure agreement with a rubric-mediated model judgment rather than direct real-world agricultural outcomes. They therefore inherit limitations from

- the judge model,
- judge prompt,
- decoding configuration,
- reference answer,
- and scoring rubric.

Judge outputs can also exhibit stochastic or model-specific variation. Repeated judging, expert spot checks, or agreement studies can characterize this variability but cannot eliminate the underlying construct limitation.

Identification and management metrics should additionally remain separate. Identification combines a binary entity metric with a 0--4 reasoning score, whereas management uses several 0--4 rubric dimensions and a weighted composite. Their scales do not support a meaningful pooled overall score without an additional prespecified normalization and aggregation scheme.

[DETAIL REQUIRES VERIFICATION: final judge checkpoint and revision, invalid-output handling, judgment repetition policy, any expert or human validation, and statistical uncertainty analysis.]

## Reproducibility of Model Execution

The experimental environment fixes many software components, including SGLang, PyTorch, Transformers, SentenceTransformers, Google ADK, LiteLLM, and Qdrant. The live vector database used during ablation execution has additionally been verified as Qdrant `1.18.0`, with both curated and runtime collections using cosine distance.

Nevertheless, exact numerical reproducibility of large-model inference may still be affected by GPU kernels, concurrency, serving-engine scheduling, model sampling, and CUDA or driver differences.

The experiments are executed using four NVIDIA A40 GPUs, with three allocated to RAG/controller endpoints and one to response generation. Concurrent request processing can further affect timing and the state of the shared runtime store even when model outputs themselves are deterministic.

The final reported experiments should therefore retain model-serving commands, model revisions, software versions, CUDA and driver information, and code revisions.

[DETAIL REQUIRES VERIFICATION: final Qwen-3 checkpoint assignments and serving configuration, CUDA and driver versions, and per-run manifests.]

## Interpretation of Ablation Results

The experimental matrix contains one direct-generation baseline and eight RAG configurations that vary access to curated retrieval, crop enrichment, progressive metadata filtering, confidence routing, web search, location-aware domain filtering, and runtime ingestion.

Not every pair of conditions differs in exactly one mechanism. Some comparisons remove or add multiple interacting components. Such results should be interpreted as comparisons between system bundles rather than as isolated causal effects of a single mechanism.

Where two configurations differ in only one intended component, stronger attribution is possible, provided that the remaining execution conditions are controlled and manipulation checks verify the expected behavior.

In particular, the experimental design can directly support contrasts such as

- Static RAG versus Static RAG + Crop Dictionary,
- Static RAG versus Progressive RAG,
- Full System without Domain Filtering versus Full System with Domain Filtering,
- and the corresponding runtime-only adaptive variants with and without domain filtering.

Even in these cases, model-controlled tool invocation means that configured access does not guarantee identical exposure to every other mechanism on every item.

Ablation conclusions should therefore distinguish between

1. the effect of enabling a capability,
2. the frequency with which that capability was actually invoked,
3. and the effect conditional on its invocation.

## Remaining Experimental Artifacts

Most architectural and implementation details can be established directly from the codebase. The remaining unresolved items principally concern artifacts that do not exist until the final experimental runs are complete.

The final curated `mirage_base_build` corpus remains under construction. Its completed build identifier, source inventory, snapshot identity, hash, document count, chunk count, point count, geographic coverage, and source coverage remain [DETAIL REQUIRES VERIFICATION].

The final `CropDatabase.json` artifact likewise remains [DETAIL REQUIRES VERIFICATION], including its final version/hash and state/crop coverage.

The final model configuration also depends on the completed evaluation schedule. [DETAIL REQUIRES VERIFICATION: exact Qwen-3 checkpoints and revisions used for each reported model, role assignments, serving commands, context limits, and numerical precision.]

Finally, final results require a frozen benchmark cohort, run manifests, inference outputs, judge outputs, and any search/runtime-state artifacts needed for reproduction. These should be reported in the Experimental Setup or supplementary reproducibility materials rather than treated as permanent methodological limitations.