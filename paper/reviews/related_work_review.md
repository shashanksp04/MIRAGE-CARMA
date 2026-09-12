# Related Work Review

## Overall assessment

The section has a sound organizing logic and generally represents the cited foundational papers fairly. Its descriptions of Flamingo, BLIP-2, LLaVA, OK-VQA, retrieval-augmented VQA, DPR, FLARE, Adaptive-RAG, Self-RAG, CRAG, and WebGPT agree with the cited primary sources. The distinctions between a fixed routing heuristic and learned or token-level adaptive mechanisms are especially careful.

The section is not yet publication-ready, however. Its final positioning claim is based on an incomplete set of close comparators as of September 2026, and two descriptions of MetaMIRAGE++'s metadata path conflict with the Methodology and repository evidence. The ending also presents a controlled study more definitively than the Experimental Setup can currently support.

## Blocking revisions

### 1. The novelty positioning omits direct 2026 comparators

The statement that prior work only “separately establishes” agricultural multimodal evaluation, metadata-filtered retrieval, and adaptive evidence acquisition is no longer defensible without discussing work that combines several of these elements.

- Sahay, Tekumalla, and Saladi, “MIRAGE: Metadata-guided Image Retrieval and Answer Generation for E-commerce Troubleshooting,” EACL 2026 Industry Track, uses structured metadata as a primary mechanism for multimodal retrieval and RAG. It differs in domain, retrieves and links visual content, and uses a schema of product attributes, context, and visual aspects, but it is a direct metadata-guided multimodal RAG comparator. It also creates a serious name-collision risk. Primary record: https://aclanthology.org/2026.eacl-industry.56/; DOI: `10.18653/v1/2026.eacl-industry.56`.
- Liu et al., “TARAG: A time-aware retrieval-augmented generation framework for supporting precision crop pest and disease management through large language models,” *Computers and Electronics in Agriculture* 248 (2026), 111786, is a direct agricultural and temporal-RAG comparator. It builds a time-annotated agricultural knowledge base and combines hybrid retrieval with time-sensitive reranking. MetaMIRAGE++ uses an exact `month_year` payload constraint rather than phenology/life-stage modeling, but that difference must be articulated rather than leaving TARAG absent. Primary publisher record: https://www.sciencedirect.com/science/article/pii/S0168169926003819.
- Liu et al., “An Intelligent Multi-modal Q&A System for Agriculture Combining APGM, PBTCS, and RAG,” *Smart Agricultural Technology* 13 (2026), 101829, combines an agricultural multimodal question-answering model, a domain knowledge base, RAG, and a complexity-based model-routing strategy. Its fruit-tree scope, trained multimodal architecture, and resource-routing objective differ from this work, but it invalidates any implication that agricultural multimodal RAG itself is unstudied. Primary publisher record: https://www.sciencedirect.com/science/article/pii/S2772375526000535; DOI: `10.1016/j.atech.2026.101829`.

Acceptance criterion: add a concise comparison to at least these three direct systems, or state and justify a literature cutoff that predates them. Rewrite the final positioning paragraph so the contribution rests on the specific implemented combination—eligible exact agricultural metadata scopes, a deterministic evidence-quality routing score, isolated run-time ingestion, and MIRAGE evaluation—rather than on an unqualified claim that the surrounding strands have appeared only separately. Do not claim uniqueness unless a broader, documented search supports it.

### 2. The knowledge-intensive visual QA coverage omits the nearest two-stage retrieval work

The subsection moves from OK-VQA directly to one end-to-end differentiable retriever-generator. That makes MetaMIRAGE++'s “modular inference design” appear less connected to prior work than it is. Wu and Mooney's EnFoRe uses the established two-stage outside-knowledge VQA pattern—retrieve external textual knowledge, then answer with a VQA model—and specifically targets overly general retrieval through question-relevant entities. MuRAG is also needed to define the retrieval-modality boundary: it retrieves from a multimodal memory, whereas MetaMIRAGE++ retrieves text passages and supplies user images only to the downstream generator.

Acceptance criterion: cite and compare (i) Wu and Mooney, “Entity-Focused Dense Passage Retrieval for Outside-Knowledge Visual Question Answering,” EMNLP 2022, https://aclanthology.org/2022.emnlp-main.551/, and (ii) Chen et al., “MuRAG: Multimodal Retrieval-Augmented Generator for Open Question Answering over Images and Text,” EMNLP 2022, https://aclanthology.org/2022.emnlp-main.375/. State explicitly that MetaMIRAGE++ uses a text-only retriever/controller and does not retrieve images. This comparison should replace any implication that modular retrieval before VQA is itself novel.

### 3. Metadata provenance is misstated

At line 19, “a month--year value, and a query-supplied title” reads as though these fields come from benchmark inputs or are deterministically passed by the driver. The Methodology states that the benchmark's asked-time field is not serialized independently and that `month_year` and `title` filters exist only when the tool-using controller supplies those arguments. Repository facts support the Methodology. The same “query-supplied title” language appears in the Introduction and should be revised consistently by the owning agents.

Acceptance criterion: describe hardiness zone as deterministically derived from available location metadata, while describing `month_year` and `title` as optional controller-supplied retrieval arguments inferred from the text/tool call. Do not imply that the MIRAGE asked-time field feeds `month_year` in the current implementation. If the intended experiment adds deterministic plumbing for those fields, verify that code first and update the evidence notes.

### 4. “Semantic-only fallback” conflicts with the actual selection procedure

At line 19, semantic-only retrieval is called a fallback. With progressive retrieval enabled, semantic-only is evaluated alongside every eligible filtered strategy, and the highest-scoring nonempty strategy is selected; it is not attempted only after filtered retrieval fails. This distinction is already explicit in the terminology notes.

Acceptance criterion: call semantic-only retrieval an always-eligible candidate strategy or scope. Reserve “fallback” for the no-evidence/error behavior if that is what is meant.

### 5. The ending overstates the experimental status

The claims that MetaMIRAGE++ “studies” the intersection in a “single ablation-ready inference architecture” and contributes a “controlled study” exceed what the Experimental Setup establishes. The repository verifies seven named RAG configurations plus a direct-generation path, not the requested nine-condition matrix. Two declared switches are not wired through the configuration reader, the checked-in launcher does not pass its selected ablation ID, and final run manifests and manipulation checks are absent. A codebase that exposes candidate configurations is not yet evidence of an executed controlled study.

Acceptance criterion: frame the section as positioning an implemented architecture and a planned controlled evaluation until run artifacts exist. Use “supports controlled comparisons” only if the launch bindings and traces are verified. After experiments, restore stronger language only if the authoritative matrix, manifests, manipulation checks, and paired cohort demonstrate the claimed controls.

### 6. Resolve the system name before using it as settled terminology

The Introduction marks “MetaMIRAGE++” as requiring verification, but Related Work treats the name as final. The EACL 2026 metadata-guided multimodal RAG paper named MIRAGE makes this more than a cosmetic issue: readers and search indexes can easily conflate the systems, while the agricultural benchmark is also named MIRAGE.

Acceptance criterion: obtain the authors' final naming decision, remove the verification marker consistently across manuscript files, and include one unambiguous sentence distinguishing the proposed system from both the agricultural MIRAGE benchmark and Sahay et al.'s e-commerce MIRAGE system. If “MetaMIRAGE++” remains, cite the benchmark on first use and avoid using bare “MIRAGE” for the proposed method.

### 7. Correct and upgrade the bibliographic records

- The `gauba2025agmmu` note gives the title as “AgMMU: A Comprehensive Agricultural Multimodal Understanding Benchmark.” The current primary source title is “AgMMU: A Comprehensive Agricultural Multimodal Understanding **and Reasoning** Benchmark.” The manuscript's substantive description is otherwise supported, including the Cooperative Extension provenance and the MCQ/OEQ and AgBase-200K claims.
- `dongre2025mirage` is recorded primarily as an arXiv item “accepted to” NeurIPS. A final proceedings record now exists in *Advances in Neural Information Processing Systems* 38, Datasets and Benchmarks Track, with DOI `10.52202/085713-0744`: https://papers.neurips.cc/paper_files/paper/2025/hash/1fdee6bdc130776e489719d25d422073-Abstract-Datasets_and_Benchmarks_Track.html. The adjacent manuscript claims about single-turn identification, causal explanation, recommendations, and multi-turn decision-making are supported by that record.
- The published Multi-Meta-RAG chapter should include its complete venue details: ICTERI 2024 proceedings, *Communications in Computer and Information Science* 2359, Springer, published 2025, pages 334--342, DOI `10.1007/978-3-031-81372-6_25`. The current note has the book series but omits volume, conference identity, and pages.

Acceptance criterion: update `citation_notes.md` and the eventual BibTeX from the final primary records, keeping citation-key years internally consistent with the selected publication form.

## Optional improvements

### Broaden agricultural benchmark context without turning it into a catalog

“Recent agricultural benchmarks increasingly” infers a field-level trend from two examples. Either narrow the sentence to AgMMU and MIRAGE or add one brief contrast with AgriBench (arXiv:2412.00465), whose MM-LUCAS data emphasize European land-use/land-cover imagery and metadata rather than expert consultation. AgroBench (arXiv:2507.20519) may also be relevant after its scope and archival status are checked. These sources help show why MIRAGE is the appropriate evaluation target, but neither needs a long description.

### Tighten the dense-retrieval limitation claim

The sentence “That flexibility can also reduce precision when a corpus is large or when relevance depends on an exact field” combines two claims. Luan et al. support capacity limits of fixed-dimensional dense encodings for precise retrieval of long documents and the value of sparse-dense hybrids; Multi-Meta-RAG supports exact metadata filtering when source attributes matter. Split the sentence or attach each citation to the claim it actually supports. Avoid suggesting that DPR generally loses precision merely because a corpus is large.

### Attribute the web-reproducibility observation

The claim that search results and page contents can change is reasonable, but neither WebGPT nor CRAG is cited specifically as an empirical reproducibility study. Present it as a property of this live-search protocol and cross-reference the Experimental Setup/Limitations, or add a source that directly studies web-agent reproducibility. Do not make WebGPT or CRAG appear to have established that result if their cited passages do not.

### Reduce manuscript-internal implementation detail in Related Work

The clauses about observed tool calls, prompt enforcement, shared run collections, and cross-item order effects are accurate and scientifically material, but they partly duplicate Methodology and Experimental Setup. Keep the one-sentence distinctions needed for fair positioning; move detailed execution caveats to those sections. The Related Work section will read more clearly if each paragraph follows the pattern “prior mechanism, relevant difference, consequence for the study.”

### Use one stable term for the routing signal

The draft alternates among “confidence mechanism,” “confidence estimate,” “confidence heuristic,” and “retrieval similarity.” The terminology note correctly defines **confidence evaluation** as a deterministic score over mean similarity, coverage, consistency, and scope. Prefer “retrieval-confidence heuristic” or “confidence evaluation” for MetaMIRAGE++, and reserve “model uncertainty” or “correctness probability” for methods that actually estimate those quantities.

## Verified claim audit

| Draft claim | Review finding |
|---|---|
| AgMMU derives from real user/expert Extension conversations and provides MCQ/OEQ evaluation plus an agricultural development corpus | Supported by arXiv:2504.10568; correct the source title and use “AgBase-200K knowledge/development set” for precision. |
| MIRAGE contains underspecified, contextual single-turn and multi-turn agricultural consultation tasks | Supported by the NeurIPS 2025 proceedings record. |
| Flamingo, BLIP-2, and LLaVA connect visual and language components through the described mechanisms | Supported by their primary papers. |
| OK-VQA requires outside knowledge; Lin and Byrne jointly train differentiable retrieval and generation | Supported, but the subsection needs EnFoRe and MuRAG for fair architectural coverage. |
| DPR uses dual encoders/shared dense space; Luan et al. compare sparse, dense, and attentional retrieval and explore hybrids | Supported. The exact-field motivation should also point to metadata-filtering work. |
| Multi-Meta-RAG uses LLM-extracted metadata as database filters for multi-hop questions | Supported by arXiv:2406.13213 and the published ICTERI chapter. |
| FLARE, Adaptive-RAG, Self-RAG, and CRAG adapt retrieval at different stages | Supported; the draft distinguishes their mechanisms fairly. |
| CRAG uses retrieval-quality evaluation and web search as a corrective source | Supported by arXiv:2401.15884. |
| WebGPT searches/navigates the web and collects references | Supported by arXiv:2112.09332. |
| MetaMIRAGE++ enumerates eligible metadata scopes and uses an uncalibrated deterministic routing heuristic | Supported by repository evidence, subject to the controller-supplied `title`/`month_year` correction above. |
| MetaMIRAGE++ has completed a controlled ablation study | Not supported by the current repository or manuscript evidence. |
