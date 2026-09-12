# Introduction Review

## Overall Assessment

**Recommendation: major revision before manuscript integration.** The section has a clear problem-to-system progression and gives a readable account of the implemented retrieval architecture. Its strongest material is the explanation of why visual evidence may be insufficient for agricultural guidance and the concise distinction between the text-only evidence controller and multimodal answer generator. The main weaknesses are evidentiary rather than structural: the Introduction currently presents an unverified experiment as completed, frames common architectural separations as contributions without establishing novelty against prior work, and makes literature-dependent claims for which no citation record yet exists.

## Blocking Corrections

### 1. Do not present the experimental matrix as executed or fully controlled

The paragraph beginning “We study this architecture” states that the study is a controlled ablation analysis and that the answer-generation interface is fixed across conditions. Neither statement is yet established by the repository evidence.

- The repository verifies seven named RAG configurations plus a separate no-RAG path, not the requested nine-condition matrix. The missing conditions and authoritative run names remain unresolved (`notes/unresolved_questions.md`, questions 4–8).
- The checked-in launcher comments out `--ablation_id` and passes a value for `--use_base_collection` that the Boolean parser interprets as false. It therefore cannot substantiate the intended full-system run (`notes/verified_project_facts.md`, “Ablation implementation”).
- Common checkpoints, benchmark subset, corpus snapshot, image policy, sampling configuration, runtime-collection freshness, search interval, hardware, and retry policy are proposed controls in `04_experimental_setup.md`, but their executed values have not been verified.

Revise this paragraph to describe the **planned experimental design** unless completed run manifests establish execution. Preserve the verified benchmark description, but qualify geographic metadata as available rather than universal. Do not claim attribution to individual mechanisms where a comparison changes multiple factors. The Experimental Setup already identifies the uncertainty-aware comparison, the addition of web search plus ingestion, and the no-base/no-dictionary condition as bundled interventions.

### 2. Resolve or mark the system name

“MetaMIRAGE++” is used as an established system name throughout the section and contribution list, but the name does not appear in the implementation and awaits project-owner approval (`notes/unresolved_questions.md`, question 13). Confirm the name before finalization. Until then, either attach `[DETAIL REQUIRES VERIFICATION]` to its first occurrence or use a neutral description such as “the proposed system.”

### 3. Reframe the contribution claims around what is both supported and plausibly novel

The current contributions mostly enumerate system components. Contribution 1—the separation of textual retrieval from multimodal answer generation—is a useful design choice, but the Introduction has not shown that this decomposition is new. Likewise, “introduce” and “develop” in Contributions 2 and 3 make priority claims that cannot be assessed while `02_related_work.md` and `notes/citation_notes.md` are empty.

After the literature review is complete, state the specific gap that remains after prior multimodal RAG, metadata-filtered retrieval, self-reflective or adaptive RAG, and web-augmented RAG. Then frame the contribution at the narrowest defensible level. The most technically specific candidates are:

1. comparison of all eligible hardiness-zone, month-year, and title filter scopes against semantic-only retrieval using a common selection rule;
2. a dual-collection design that isolates a curated base from run-scoped online ingestion while permitting within-run reuse; and
3. an agricultural multimodal ablation protocol that separates or explicitly bundles these mechanisms.

Avoid presenting the deterministic confidence formula as calibrated uncertainty. The Methodology and terminology notes correctly describe it as a fixed score over similarity, hit count, score dispersion, and selected metadata scope.

### 4. Correct the behavioral-logging claim in Contribution 4

The claim that the framework “records whether retrieval, retries, and web search were used for each generated response” is too broad. The output JSONL records `RAG_used`, `RAG_attempt`, `RAG_web_search_performed`, endpoint, and terminal RAG status for completed outputs, but it does not persist the retrieval tool-call sequence, confidence values, chosen strategy, retrieved chunks, source URLs, or effective enriched query (`03_methodology.md`, “Behavioral Logging”; `notes/unresolved_questions.md`, question 15). `RAG_used` represents successful contextual use, not a complete trace of every retrieval action.

Rewrite this contribution as an item-level summary of RAG status, retry attempt, and observed web-search use. Do not call it a reproducibility or audit trail without additional trace artifacts.

### 5. Separate implemented policy from verified runtime behavior

The system-description paragraphs are generally faithful to the code, but they blur deterministic implementation with prompt-directed agent behavior. The confidence calculation is deterministic; the subsequent low-confidence loop is specified in natural-language agent instructions rather than enforced as a Python state machine. Compliance with the requested sequence, including the five-success/ten-attempt ingestion limits, is not recoverable from the current JSONL (`notes/unresolved_questions.md`, questions 14–16).

Retain “can form search terms, query the web … and repeat retrieval,” which appropriately describes capability. In the contribution summary and final synthesis, replace “recognize weak retrieval” with wording that makes the mechanism explicit, such as assigning a low-confidence label under the fixed retrieval heuristic. Avoid implying that the score measures factual reliability or calibrated uncertainty.

### 6. Add citations for every literature- and domain-dependent premise

The first four paragraphs currently contain no citations, and `notes/citation_notes.md` is empty. Repository inspection cannot support these general claims. At minimum, the revised section needs traceable sources for:

- the MIRAGE benchmark and its agricultural visual-question-answering task;
- multimodal language models as joint image-text response systems;
- the use of retrieval augmentation to provide external passages or provenance;
- limitations of fixed corpora and unconstrained semantic retrieval;
- the relevance of crop, geography, climate or hardiness, season, and publication time to agricultural recommendations;
- precision/recall tradeoffs or brittleness in metadata filtering; and
- latency, cost, variability, and provenance concerns in live web augmentation.

Use primary papers and authoritative agricultural sources where possible, and add each selected source and claim mapping to `notes/citation_notes.md`. Avoid universal statements such as “the image is rarely the whole problem” or “hard filtering alone is brittle” unless the citations support that breadth; otherwise narrow them to the MIRAGE task setting or present them as design motivation.

### 7. Clarify what metadata the system actually uses

The prose repeatedly invokes “geographic context,” “region,” and “county-level” relevance, while the retriever does not apply county or state equality filters. It converts county-state metadata to a USDA hardiness zone, falling back to a state-modal zone, and filters on that derived zone. This distinction matters because hardiness-zone agreement is not equivalent to local regulatory, pest-pressure, or extension-jurisdiction relevance.

Revise the architecture summary to name **derived plant-hardiness zone** as the retrieval filter and reserve broader geographic language for motivation. Also qualify month-year metadata: live search results with no usable publication date are assigned the retrieval month, an unresolved provenance issue (`notes/unresolved_questions.md`, question 19). The Introduction need not explain that fallback, but it should avoid implying that every temporal value is a verified publication date.

## Optional Improvements

### Sharpen the problem and novelty transition

The first four paragraphs develop two gaps—metadata mismatch and corpus insufficiency—but take almost half the section before naming the proposed system. They can be compressed by combining the discussion of brittle filters with the adaptive-acquisition motivation. Use the saved space to state the research question explicitly: whether structured retrieval scopes and confidence-triggered online acquisition can be varied within a fixed multimodal QA pipeline. This would connect the motivation more directly to the ablation design without anticipating outcomes.

### Avoid treating one baseline as “conventional RAG”

“A conventional RAG pipeline” currently means a fixed corpus plus unconstrained semantic retrieval. That is one baseline implemented here, not a safe characterization of the whole RAG literature. Call it “a static semantic-retrieval baseline” or support the broader taxonomy with citations.

### Make the title constraint intelligible

The system summary lists hardiness zone, month-year, and title constraints without explaining where a query-side title value comes from or when it is available. A reader may interpret “title” as a document-ranking feature rather than an exact-match payload filter supplied in the retrieval call. Add a short qualifier (“when supplied”) or defer this detail to Methodology and describe the Introduction-level method as evaluating eligible metadata scopes.

### Reduce repeated summary language

The final paragraph repeats claims already made in the two system paragraphs and contribution list. It can be reduced to a short paper roadmap. The sentence “We defer all empirical claims to the Results section” is editorial process language; omit it once all result-dependent claims have been removed.

### Keep benchmark scope precise

The MIRAGE sentence is accurate about one to three images, expert answers, categories, and geographic fields, but some geographic labels are blank or outside the 50 U.S. states. Use “include geographic metadata when available.” Do not state the final sample count, benchmark subset, or coverage until the duplicate-ID policy and selected evaluation set are resolved.

## Revision Acceptance Criteria

The Introduction is ready for a second review when it:

1. describes unverified experiments as planned rather than completed;
2. marks or resolves the system name;
3. makes contribution language consistent with the completed Related Work review;
4. narrows the logging claim to persisted fields;
5. distinguishes the deterministic confidence score from prompt-directed control flow;
6. uses hardiness-zone terminology precisely and avoids assuming verified publication dates;
7. has citation-note entries for all external claims; and
8. contains no empirical outcome language or unsupported assertion that the ablation variables were held fixed in executed runs.
