# Methodology Review

## Overall assessment

The section is unusually strong in its coverage of the implemented retrieval algorithm, confidence formula, dual-collection design, and runtime lifecycle. Most numerical details agree with the executable code. It is not yet ready for submission, however, because several sentences present prompt-directed behavior as guaranteed behavior, one failure-path description contradicts the driver, and essential corpus and controller details remain unverified. The revision should preserve the technical specificity while drawing a clear boundary among (i) behavior enforced in Python, (ii) behavior requested in a language-model instruction, and (iii) behavior intended for the experiment but not established by repository artifacts.

## Blocking factual errors and method-integrity issues

These issues should be corrected before the section is treated as an accurate account of the current system.

### 1. The system name is not repository-verified

The draft introduces *MetaMIRAGE++* as the system name in lines 5 and 13, but repository sources use **MIRAGE-RAG** and **MetaMIRAGE**; *MetaMIRAGE++* does not occur in the implementation or project documentation (`paper/notes/verified_project_facts.md:7`; `paper/notes/unresolved_questions.md`, question 13). Obtain an explicit naming decision or use a repository-supported name. If the new name is retained, define its relationship to MIRAGE, MIRAGE-RAG, and MetaMIRAGE once and use it consistently across all sections.

### 2. “Two models” is not an accurate architectural invariant

Lines 5--11 describe responsibilities assigned to “the two models.” The code defines two roles or stages, but the evidence agent, crop enricher, keyword extractor, and final generator can use the same served checkpoint. The current experiment's exact model assignment is unresolved. Revise this to “two stages” or “two model invocations/roles” unless the experimental configuration verifies distinct models (`Inference/generate.py:228-264`, `:815-823`; `paper/notes/unresolved_questions.md`, questions 1--3).

### 3. Verbatim evidence return and agent control flow are instructed, not enforced

Lines 11, 17, 80--92, and 96 state or imply that the evidence agent follows the prescribed retrieve/evaluate/search/ingest sequence and returns retrieved passages verbatim. Those constraints exist in `rag_agent/model_instructions.md:20-27`, `:37-69`, and `:108-130`, but there is no deterministic controller or output validator enforcing them. The driver takes the last text event authored by `Rag_Agent` and does not compare it with tool-returned passages, validate the confidence label, validate the output template, or verify the required number/order of tool calls (`Inference/generate.py:328-375`). Required function calling ensures a tool call at the model interface, but it does not make the entire multi-step trajectory deterministic (`rag_agent/main.py:567-582`).

Revise all such claims to distinguish the **prompt-specified policy** from the **Python-enforced path**. State explicitly that tool traces are observed but not validated for policy compliance. If the authors want to claim guaranteed verbatim evidence and bounded control flow, add deterministic orchestration or post-hoc validation and document it.

### 4. The described “insufficient evidence” soft-failure path contradicts the code

Line 98 says that an “empty or insufficient evidence response” is a soft failure that causes generation from the enriched query alone. Empty/short responses are soft failures, but the exact low-confidence response required by the full prompt—`No sufficient reliable information available to return.`—is longer than the driver's 30-character cutoff. With no accompanying error, it is classified as a successful RAG answer and appended under `additional context` (`rag_agent/model_instructions.md:124-130`; `Inference/generate.py:141-148`, `:779-795`).

This is a blocking factual error and likely an implementation bug. Either update `_is_soft_rag_failure` to recognize the canonical no-evidence messages and then describe that behavior, or revise the manuscript to report the current behavior. The former is scientifically preferable because it aligns the runtime with the stated method.

### 5. Configuration toggles are not strictly enforced against tool-call overrides

Line 41 claims that disabling progressive filtering leaves only semantic retrieval, and line 80 says the active configuration determines tool behavior. Tool registration is configuration-gated, but the registered retrieval and confidence tools expose `use_progressive_filtering`, and the web-search tool exposes `use_domain_filter`; a model-supplied value overrides the run-level setting (`rag_agent/main.py:329-364`, `:373-408`, `:484-522`). Thus a tool call can re-enable progressive filtering or domain filtering in a condition intended to disable it. This threatens ablation isolation.

Remove these per-call overrides from the model-visible signatures, or ignore them in favor of the run-level setting. Until that is done, describe the toggles as defaults rather than hard controls and do not claim clean component isolation. The separate fact that `db_on` and `crop_dict_on` are declared but not applied also belongs in Experimental Setup, but the Methodology should avoid implying that one configuration object governs the entire pipeline (`paper/notes/verified_project_facts.md`, “Ablation implementation”).

### 6. The web-search description overstates domain restrictions and misstates the endpoint behavior

Line 90 says the resulting search excludes commercial and organizational domains and that the unrestricted variant uses an “open search endpoint.” The exclusion terms are added only when the location lookup returns at least one mapped educational domain. If no mapped domains are available—even when domain filtering is enabled—the code sends the raw keyword query with no `.edu`, `.com`, or `.org` restriction. Disabling the filter also sends a raw query to the same You.com API endpoint; it does not select a different endpoint (`rag_agent/tools/web_search.py:101-124`).

Revise this paragraph to describe the three actual cases: mapped-domain restricted query, enabled-but-unavailable mapping fallback to an unrestricted query, and deliberately disabled filtering using an unrestricted query. Name the search provider and move provider version/date/API details to Experimental Setup.

### 7. `month_year` does not have one consistent semantic meaning

Line 27 frames `month_year` as a credible source date, while line 92 correctly notes that missing web-result dates are replaced by the retrieval month. Consequently, runtime `month_year` may denote provider-reported page age, provider-reported month, or acquisition time; it is not uniformly a publication date (`rag_agent/tools/web_search.py:155-171`). Define this field as a date proxy with explicit provenance, or store separate `source_month_year` and `retrieved_month_year` fields. Exact-match temporal filtering is scientifically hard to interpret without this distinction.

### 8. Base-corpus realization and promotion remain unverified

Line 21 includes an appropriate marker for the `mirage_base_build` to `mirage_base` promotion step, but the larger evidentiary gap is not visible: the repository contains no completed state/wave manifests or final snapshot manifest establishing that the concurrent preload was run to completion for the experimental corpus. Its sources, inclusion window, state coverage, document/chunk counts, build identifier, snapshot hash, and collection parameters are also unresolved (`paper/notes/unresolved_questions.md`, questions 22--25).

The section may describe the implemented preload procedure, but it should use implementation-oriented phrasing (“the worker is configured to…”) rather than implying a verified completed corpus. Retain a concise verification marker for the exact experimental snapshot and record the final corpus facts in Experimental Setup once available.

## High-priority scientific and reproducibility revisions

### 9. Formalize the actual input transformation

The equation in lines 5--9 conditions the generator separately on structured location $\ell_i$, but the implementation serializes location into the text prefix `[User location: ...]`; the generator receives no independent structured location channel (`Inference/generate.py:477-482`, `:779-823`). Introduce an effective query, for example $q'_i=g(q_i,\ell_i,D)$, and formulate evidence acquisition as $E_i=A(q'_i;K_b,K_r)$ and generation as $p_\theta(y\mid q'_i,I_i,E_i)$. This will also make the crop-dictionary role and no-evidence fallback precise.

The benchmark contains an asked-time field, but `get_prompt` does not serialize it and retrieval receives `month_year` only if the language-model agent supplies it in a tool call. Similarly, `title` is model-supplied rather than deterministically derived from the item. State this explicitly so readers do not infer that benchmark time metadata automatically drives temporal filtering.

### 10. Specify the qualification gate, not only its outputs

Lines 21--23 give detailed chunking and coordination mechanics but omit scientifically important corpus-selection parameters. The preload worker is configured to use `meta-llama/Meta-Llama-3.1-8B-Instruct` with 4-bit NF4 quantization, qualification segments of 7,000 characters with 700-character overlap and at most 20 segments, a fixed label set, validation/retry logic, and acceptance when the merged document tag is not `msc` (`paper/notes/verified_project_facts.md`, “Concurrent preload architecture”; preload worker around cells 5 and 10--12). Add these facts, including the exact acceptance rule. Describe this as an LLM-based qualification stage rather than an unspecified “classifier.”

Also state whether these configured values produced the experimental base snapshot. Configuration evidence alone does not establish execution.

### 11. Clarify query-vector computation and metadata arguments

Line 43 says all strategies use “the same query vector.” The implementation truncates the same query and calls the embedder separately inside each strategy iteration (`rag_agent/utils/ContentUtils.py:242-264`). SentenceTransformer inference is expected to be stable, but the vector is recomputed rather than reused. Say “the same truncated query and embedding model,” or move embedding outside the loop if literal vector reuse is intended.

The initial retrieval uses a fixed default $k=5$, whereas the confidence tool exposes $k$ to the language model and normalizes malformed values. The confidence call can also use independently generated query/title/month arguments. Therefore, the “second retrieval” need not reproduce the first result set. State the defaults and argument source, or cache the first retrieval result and score that result directly (`rag_agent/main.py:329-364`, `:484-536`; `rag_agent/tools/confidence_evaluator.py:67-91`).

### 12. Present confidence as an uncalibrated routing heuristic

The equations in lines 59--76 match the code, including population variance, the single-result constant, weights, rounding, and thresholds. Add that the weights and thresholds are fixed design choices with no repository evidence of calibration (`paper/notes/unresolved_questions.md`, question 18). Define the equations for $n\geq1$ before giving the $n=0$ branch. Because $S$ is an unclipped raw cosine score, $C$ should not be described or interpreted as a probability. “Confidence heuristic” or “routing score” is more precise than model uncertainty.

Coverage is hard-coded as $n/5$ even if the confidence call uses a nondefault $k$. Either fix $k=5$ at the API boundary or disclose that denominator choice. The scope term is also inherited from one collection rather than computed over the merged evidence; this limitation is correctly hinted at in line 53 but should be repeated briefly where $P$ is defined.

### 13. Document tie behavior in dual-collection retrieval

Line 53 says the diagnostic strategy is inherited from the collection with the larger result set. When the base and runtime collections return equally many passages, Python's `max` selects the first evaluation, which is the base collection when enabled (`rag_agent/utils/dual_collection_retriever.py:24-46`). Add this tie rule. Also qualify cross-collection duplicate checks as operating on the enabled base collection plus runtime; with the base disabled, only runtime is checked.

### 14. Address order and concurrency dependence of runtime augmentation

Line 55 correctly notes that evidence acquired for one item can affect later items, but “later” is completion-order dependent because multiple RAG workers share the mutable runtime collection. Retrieval and ingestion can interleave, and the confidence tool runs a fresh search after the initial retrieval. The resulting evidence can therefore depend on benchmark order, GPU count, queue scheduling, retries, and whether the runtime collection is fresh or resumed (`Inference/generate.py:639-745`; `paper/notes/unresolved_questions.md`, questions 8 and 16).

This is a central property of the method, not merely an implementation detail. State whether the experimental unit is an independent item or a stateful run. Experimental Setup must fix item order, worker count, collection freshness, and resume policy. If item-level independence is desired, isolate runtime collections per item or otherwise freeze augmentation between examples.

### 15. Separate registered PDF capability from the evaluated web loop

Lines 55 and 80 mention PDF additions alongside web additions. The PDF ingestion tool is registered when ingestion is enabled, but the low-confidence templates direct the agent to ingest URLs returned by web search; repository traces do not establish that runtime PDF ingestion occurred (`paper/notes/unresolved_questions.md`, question 20). It is fine to describe PDF ingestion as an exposed capability, but do not imply it participated in evaluated trajectories without trace evidence.

### 16. Add missing component and version references needed for reproduction

The methodology should identify Qdrant cosine search, BGE embeddings, SentenceTransformers, Google ADK/LiteLLM tool orchestration, the You.com search provider, and Trafilatura extraction, with citations where appropriate. Exact software versions, server settings, model revisions, hardware, and environment hashes can live in Experimental Setup. The current embedding-normalization marker in line 35 is appropriate and should remain until the deployed Qdrant version and cosine-normalization behavior are verified.

The crop-enrichment description is accurate about the subsequence check, but readers may infer that inserted text is validated against the allowlist. It is not: allowlist compliance is prompt-directed, while post-generation code validates JSON/nonempty output and insertion-only preservation of the original string (`rag_agent/crop_query_enrichment.py:28-45`, `:272-290`). State this enforcement boundary, and verify the actual dictionary artifact/path/hash before presenting enrichment as an active experimental component.

## Novelty and terminology

The section catalogs components but never clearly states which combination or algorithm is proposed and which pieces are standard infrastructure. Add one restrained paragraph that locates the methodological contribution in the metadata-strategy selection, heuristic confidence routing, isolated mutable acquisition collection, and constrained crop insertion, if these are indeed the claimed contributions. Do not claim novelty for Qdrant, BGE, generic agent tool use, web search, or ordinary chunking without literature support.

Use the terminology note consistently:

- Prefer **progressive metadata retrieval** to generic “progressive filtering.”
- Call $C$ a **confidence evaluation/routing score**, never a calibrated probability or epistemic uncertainty.
- Use **curated base collection** and **runtime collection** on first mention before implementation names.
- Use **query enrichment** for constrained crop insertion; avoid “query rewriting.”
- Reserve **behavioral logging** for fields actually persisted. Console traces are transient execution traces.

The current line 102 mostly handles the logging distinction well. Tighten its final sentence to assign metadata/embedding/upsert events to state-local ledgers and lease/content-claim events to the coordinator rather than implying that every event type is recorded in both places.

## Equations and presentation

The retrieval and confidence equations are useful and should remain. Make the following corrections:

1. Define $K_b$ and $K_r$ for the curated and runtime collections and define the effective query before the generation equation.
2. State $n_a\geq1$ beside $R(a)$ and $n\geq1$ beside $S,V,K$ so no displayed expression is undefined.
3. Define `Var` as population variance, matching `statistics.pvariance`.
4. Use one notation for zone/month/title throughout. The set in line 38 is a candidate family rather than an evaluation order; if order matters for ties, list the actual order in prose. The actual order is zone-month-title, zone-title, title, month, zone-month, zone, semantic-only (`rag_agent/utils/ContentUtils.py:187-224`).
5. Explain that $R(a)$ uses transformed scores only for within-collection strategy selection, while cross-collection ranking and $S$ use raw Qdrant scores. The draft already says this; retain it.
6. Avoid bare Unicode `∅` in surrounding prose if the target LaTeX workflow expects `\varnothing`.

## Optional polish after factual revision

- Lines 15--17 and 51--55 partly repeat the two-collection architecture. Keep the overview conceptual and leave lifecycle/deduplication details to the later subsection.
- The preload section currently gives more operational coordination detail than it gives corpus-selection detail. Compress lease/snapshot mechanics after adding the qualification gate and corpus provenance.
- Replace causal language such as “ensuring” and “prevents” with directly testable descriptions unless concurrency or recovery tests are cited. “Uses the same mapping contract” and “is designed to prevent” are safer where execution artifacts are absent.
- Line 49 offers design rationale but no evidence that the strategy improves retrieval. Frame it as the intended effect pending Results.
- Line 98's final sentence (“This policy keeps…”) is unnecessary once the actual failure behavior is stated precisely.
- Consider a compact algorithm block for the intended full-system policy after deterministic enforcement is clarified. It would be easier to reproduce than relying on the current prose and flow equation alone.

## Prioritized revision checklist

1. Fix the no-evidence classification contradiction and audit the final agent output before appending it to the generation prompt.
2. Enforce run-level ablation toggles against model-supplied overrides.
3. Recast prompt-directed agent behavior as intended policy unless deterministic validation is added.
4. Resolve the system name and model-role assignments.
5. Add the qualification model, acceptance rule, and qualification segmentation parameters.
6. Correct the web-domain and `month_year` semantics.
7. Formalize the effective textual query and disclose that asked-time/title filters are not automatically populated.
8. Mark the experimental base snapshot, crop dictionary, and completed preload build as unverified until artifacts are supplied.
9. Describe shared-runtime order/concurrency dependence and fix the corresponding controls in Experimental Setup.
10. Add citations and versioned component references, then perform the optional compression and style pass.
