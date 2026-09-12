# Citation Notes

## Sources cited in the Introduction

### `dongre2025mirage`

- Vardhan Dongre, Chi Gui, Shubham Garg, Hooshang Nayyeri, Gokhan Tur, Dilek Hakkani-Tür, and Vikram S. Adve. “MIRAGE: A Benchmark for Multimodal Information-Seeking and Reasoning in Agricultural Expert-Guided Conversations.” *Advances in Neural Information Processing Systems* 38, Datasets and Benchmarks Track, 2025, pp. 25023--25099.
- Primary source: https://papers.neurips.cc/paper_files/paper/2025/hash/1fdee6bdc130776e489719d25d422073-Abstract-Datasets_and_Benchmarks_Track.html
- DOI: https://doi.org/10.52202/085713-0744
- Stable preprint: https://arxiv.org/abs/2506.20100
- Manuscript use: supports the characterization of MIRAGE as a multimodal agricultural expert-consultation benchmark combining natural questions, expert-authored responses, and image context. Repository inspection separately supports the exact fields and one-to-three-image count of the checked-in benchmark copy.

### `liu2023llava`

- Haotian Liu, Chunyuan Li, Qingyang Wu, and Yong Jae Lee. “Visual Instruction Tuning.” NeurIPS 2023. arXiv:2304.08485.
- Primary source: https://arxiv.org/abs/2304.08485
- Manuscript use: supports the statement that a multimodal language model can connect a vision encoder and a language model for general-purpose visual and language instruction following. It is not evidence about the subject model used in the MetaMIRAGE++ experiments.

### `lewis2020rag`

- Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal, Heinrich Küttler, Mike Lewis, Wen-tau Yih, Tim Rocktäschel, Sebastian Riedel, and Douwe Kiela. “Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.” NeurIPS 2020. arXiv:2005.11401.
- Primary source: https://papers.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html
- Manuscript use: supports the description of RAG as combining parametric generation with explicit non-parametric memory and the motivation that provenance and knowledge updating are difficult for purely parametric models.

### `usda2023phzm`

- U.S. Department of Agriculture, Agricultural Research Service. “2023 USDA Plant Hardiness Zone Map.” 2023.
- Authoritative source: https://planthardiness.ars.usda.gov/
- Manuscript use: supports the limited interpretation of a plant-hardiness zone as a location-based proxy derived from average annual extreme minimum winter temperature. It does not support treating hardiness zones as complete geographic, regulatory, pest-pressure, or extension-jurisdiction equivalence.

### `asai2024selfrag`

- Akari Asai, Zeqiu Wu, Yizhong Wang, Avirup Sil, and Hannaneh Hajishirzi. “Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection.” ICLR 2024. arXiv:2310.11511.
- Primary source: https://openreview.net/forum?id=hSyW5go0v8
- Manuscript use: supports the broader adaptive-retrieval premise that indiscriminately retrieving a fixed number of passages can be unhelpful and that retrieval can instead be invoked or assessed adaptively. MetaMIRAGE++ uses a different mechanism: a fixed retrieval heuristic and a prompt-directed tool policy.

## Sources cited in Related Work

### `gauba2025agmmu`

- Aruna Gauba, Irene Pi, Yunze Man, Ziqi Pang, Vikram S. Adve, and Yu-Xiong Wang. “AgMMU: A Comprehensive Agricultural Multimodal Understanding and Reasoning Benchmark.” arXiv:2504.10568, 2025.
- Primary source: https://arxiv.org/abs/2504.10568
- Stable identifier: https://doi.org/10.48550/arXiv.2504.10568
- Claim mapping: supports that AgMMU is derived from authentic grower--Cooperative Extension dialogues; contains paired multiple-choice and open-ended evaluation questions; and releases AgBase, a multimodal fact corpus covering agricultural identification, symptoms, disease categorization, and management. Dataset counts differ across released versions, so the manuscript does not state a count.

### `alayrac2022flamingo`

- Jean-Baptiste Alayrac, Jeff Donahue, Pauline Luc, Antoine Miech, Iain Barr, Yana Hasson, Karel Lenc, Arthur Mensch, Katie Millican, Malcolm Reynolds, Roman Ring, Eliza Rutherford, Serkan Cabi, Tengda Han, Zhitao Gong, Sina Samangooei, Marianne Monteiro, Jacob Menick, Sebastian Borgeaud, Andrew Brock, Aida Nematzadeh, Sahand Sharifzadeh, Mikolaj Binkowski, Ricardo Barreira, Oriol Vinyals, Andrew Zisserman, and Karen Simonyan. “Flamingo: a Visual Language Model for Few-Shot Learning.” *Advances in Neural Information Processing Systems* 35, 2022. arXiv:2204.14198.
- Primary source: https://arxiv.org/abs/2204.14198
- Stable identifier: https://doi.org/10.48550/arXiv.2204.14198
- Claim mapping: supports the description of Flamingo as bridging pretrained vision and language models through cross-attention and accepting interleaved text with multiple images or video.

### `li2023blip2`

- Junnan Li, Dongxu Li, Silvio Savarese, and Steven Hoi. “BLIP-2: Bootstrapping Language-Image Pre-training with Frozen Image Encoders and Large Language Models.” In *Proceedings of the 40th International Conference on Machine Learning*, PMLR 202, 2023, pp. 19730--19742. arXiv:2301.12597.
- Primary source: https://proceedings.mlr.press/v202/li23q.html
- Stable preprint: https://arxiv.org/abs/2301.12597
- Claim mapping: supports the description of BLIP-2's lightweight Querying Transformer between a frozen image encoder and a frozen language model.

### `marino2019okvqa`

- Kenneth Marino, Mohammad Rastegari, Ali Farhadi, and Roozbeh Mottaghi. “OK-VQA: A Visual Question Answering Benchmark Requiring External Knowledge.” In *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition*, 2019, pp. 3195--3204.
- Primary source: https://openaccess.thecvf.com/content_CVPR_2019/html/Marino_OK-VQA_A_Visual_Question_Answering_Benchmark_Requiring_External_Knowledge_CVPR_2019_paper.html
- Claim mapping: supports that OK-VQA was designed so that image content is insufficient and outside knowledge is required to answer its visual questions.

### `lin2022retrieval`

- Weizhe Lin and Bill Byrne. “Retrieval Augmented Visual Question Answering with Outside Knowledge.” In *Proceedings of the 2022 Conference on Empirical Methods in Natural Language Processing*, 2022, pp. 11238--11254.
- Primary source: https://aclanthology.org/2022.emnlp-main.772/
- DOI: https://doi.org/10.18653/v1/2022.emnlp-main.772
- Claim mapping: supports the characterization of knowledge-intensive VQA systems that retrieve external passages and the specific example of jointly training differentiable dense passage retrieval with answer generation.

### `wu2022enfore`

- Jialin Wu and Raymond Mooney. “Entity-Focused Dense Passage Retrieval for Outside-Knowledge Visual Question Answering.” In *Proceedings of the 2022 Conference on Empirical Methods in Natural Language Processing*, 2022, pp. 8061--8072.
- Primary source: https://aclanthology.org/2022.emnlp-main.551/
- DOI: https://doi.org/10.18653/v1/2022.emnlp-main.551
- Claim mapping: supports the established two-stage outside-knowledge VQA pattern of retrieving text before answer prediction and EnFoRe's use of question-relevant entities to retrieve more specific knowledge.

### `chen2022murag`

- Wenhu Chen, Hexiang Hu, Xi Chen, Pat Verga, and William Cohen. “MuRAG: Multimodal Retrieval-Augmented Generator for Open Question Answering over Images and Text.” In *Proceedings of the 2022 Conference on Empirical Methods in Natural Language Processing*, 2022, pp. 5558--5570.
- Primary source: https://aclanthology.org/2022.emnlp-main.375/
- DOI: https://doi.org/10.18653/v1/2022.emnlp-main.375
- Claim mapping: supports the distinction between text-only retrieval and a learned retriever over external multimodal memory containing both images and text.

### `karpukhin2020dpr`

- Vladimir Karpukhin, Barlas Oğuz, Sewon Min, Patrick Lewis, Ledell Wu, Sergey Edunov, Danqi Chen, and Wen-tau Yih. “Dense Passage Retrieval for Open-Domain Question Answering.” In *Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing*, 2020, pp. 6769--6781.
- Primary source: https://aclanthology.org/2020.emnlp-main.550/
- DOI: https://doi.org/10.18653/v1/2020.emnlp-main.550
- Claim mapping: supports the standard dense-retrieval formulation in which separately encoded questions and passages are compared in a shared vector space.

### `luan2021sparse`

- Yi Luan, Jacob Eisenstein, Kristina Toutanova, and Michael Collins. “Sparse, Dense, and Attentional Representations for Text Retrieval.” *Transactions of the Association for Computational Linguistics* 9 (2021): 329--345.
- Primary source: https://aclanthology.org/2021.tacl-1.20/
- DOI: https://doi.org/10.1162/tacl_a_00369
- Claim mapping: supports the distinction between sparse, dense, and attentional relevance representations, limitations of fixed-dimensional dense encodings, and the motivation for combining complementary retrieval signals. It is not evidence that MetaMIRAGE++ implements lexical retrieval; the manuscript explicitly distinguishes its exact-filter-plus-dense design from a sparse--dense hybrid.

### `poliakov2025multimetarag`

- Mykhailo Poliakov and Nadiya Shvai. “Multi-Meta-RAG: Improving RAG for Multi-Hop Queries Using Database Filtering with LLM-Extracted Metadata.” In *Information and Communication Technologies in Education, Research, and Industrial Applications: 19th International Conference, ICTERI 2024, Proceedings*, Communications in Computer and Information Science 2359, Springer, 2025, pp. 334--342. arXiv:2406.13213.
- Primary source: https://link.springer.com/chapter/10.1007/978-3-031-81372-6_25
- Stable preprint: https://arxiv.org/abs/2406.13213
- Published DOI: https://doi.org/10.1007/978-3-031-81372-6_25
- Claim mapping: supports metadata-based database filtering as a retrieval mechanism for RAG. Its metadata is LLM-extracted and its task is multi-hop QA; these differences are preserved in the manuscript.

### `jiang2023flare`

- Zhengbao Jiang, Frank Xu, Luyu Gao, Zhiqing Sun, Qian Liu, Jane Dwivedi-Yu, Yiming Yang, Jamie Callan, and Graham Neubig. “Active Retrieval Augmented Generation.” In *Proceedings of the 2023 Conference on Empirical Methods in Natural Language Processing*, 2023, pp. 7969--7992. arXiv:2305.06983.
- Primary source: https://aclanthology.org/2023.emnlp-main.495/
- DOI: https://doi.org/10.18653/v1/2023.emnlp-main.495
- Stable preprint: https://arxiv.org/abs/2305.06983
- Claim mapping: supports the description of FLARE as iteratively retrieving from predictions of upcoming sentences when those predictions contain low-confidence tokens.

### `jeong2024adaptiverag`

- Soyeong Jeong, Jinheon Baek, Sukmin Cho, Sung Ju Hwang, and Jong Park. “Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity.” In *Proceedings of the 2024 Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies (Volume 1: Long Papers)*, 2024, pp. 7036--7050. arXiv:2403.14403.
- Primary source: https://aclanthology.org/2024.naacl-long.389/
- Stable preprint: https://arxiv.org/abs/2403.14403
- DOI: https://doi.org/10.18653/v1/2024.naacl-long.389
- Claim mapping: supports routing among no-retrieval, single-step retrieval, and iterative retrieval using a smaller model trained to classify question complexity.

### `yan2024crag`

- Shi-Qi Yan, Jia-Chen Gu, Yun Zhu, and Zhen-Hua Ling. “Corrective Retrieval Augmented Generation.” arXiv:2401.15884, 2024.
- Primary source: https://arxiv.org/abs/2401.15884
- Stable identifier: https://doi.org/10.48550/arXiv.2401.15884
- Claim mapping: supports retrieval-quality evaluation, confidence-conditioned corrective actions, and the use of web search to extend evidence beyond a static corpus. MetaMIRAGE++'s heuristic is not represented as CRAG's learned evaluator.

### `nakano2021webgpt`

- Reiichiro Nakano, Jacob Hilton, Suchir Balaji, Jeff Wu, Long Ouyang, Christina Kim, Christopher Hesse, Shantanu Jain, Vineet Kosaraju, William Saunders, Xu Jiang, Karl Cobbe, Tyna Eloundou, Gretchen Krueger, Kevin Button, Matthew Knight, Benjamin Chess, and John Schulman. “WebGPT: Browser-assisted question-answering with human feedback.” arXiv:2112.09332, 2021.
- Primary source: https://arxiv.org/abs/2112.09332
- Stable identifier: https://doi.org/10.48550/arXiv.2112.09332
- Claim mapping: supports browser-assisted question answering in which a model searches and navigates the web and gathers references for its answer. It does not support the implementation-specific claims about MetaMIRAGE++ runtime ingestion.

### `sahay2026ecommercemirage`

- Rishav Sahay, Lavanya Sita Tekumalla, and Anoop Saladi. “MIRAGE: Metadata-guided Image Retrieval and Answer Generation for E-commerce Troubleshooting.” In *Proceedings of the 19th Conference of the European Chapter of the Association for Computational Linguistics (Volume 5: Industry Track)*, 2026, pp. 764--776.
- Primary source: https://aclanthology.org/2026.eacl-industry.56/
- DOI: https://doi.org/10.18653/v1/2026.eacl-industry.56
- Claim mapping: supports the comparison to a metadata-first multimodal RAG system that represents troubleshooting text and images in a shared product-attribute, context, and visual-aspect schema for image--text linking and answer generation. This work is unrelated to the agricultural MIRAGE benchmark and creates a system-name collision that the manuscript now states explicitly.

### `liu2026tarag`

- Lei Liu, Shunbao Li, Jun Qi, Zhipeng Yuan, and Po Yang. “TARAG: A time-aware retrieval-augmented generation framework for supporting precision crop pest and disease management through large language models.” *Computers and Electronics in Agriculture* 248 (2026): 111786.
- Primary publisher record: https://www.sciencedirect.com/science/article/pii/S0168169926003819
- DOI: https://doi.org/10.1016/j.compag.2026.111786
- Author-accepted manuscript: https://eprints.whiterose.ac.uk/id/eprint/240241/
- Claim mapping: supports comparison to agricultural RAG with a time-annotated knowledge base, hybrid sparse/dense retrieval, time-sensitive reranking, and temporal representations tied to crop phenology and pest or disease life stages. The present system's exact `month_year` field is substantially narrower.

### `liu2026agriqa`

- Baihan Liu, Yi Zhang, Yongshun Liu, Xiaoling Deng, Jiajun Qing, Bo Han, Xiangbao Meng, Yubin Lan, and Haofeng Qiu. “An intelligent multi-modal Q&A system for agriculture combining APGM, PBTCS, and RAG.” *Smart Agricultural Technology* 13 (2026): 101829.
- Primary publisher record: https://www.sciencedirect.com/science/article/pii/S2772375526000535
- DOI: https://doi.org/10.1016/j.atech.2026.101829
- Claim mapping: supports the comparison to an agricultural multimodal QA system that combines a trained lightweight multimodal prompt-generation model, a fruit-tree domain knowledge base with RAG, and complexity-based routing among language models of different scales.

## Cross-file citation-key notes

- `dongre2025mirage`, `liu2023llava`, `lewis2020rag`, and `asai2024selfrag` are defined in the Introduction notes above and are reused in Related Work.
- All implementation-specific comparisons in Related Work were checked against `paper/03_methodology.md`; literature citations support neighboring research designs, while repository evidence supports statements about the proposed system.
- `MetaMIRAGE++` remains a provisional name. The manuscript distinguishes it from the agricultural MIRAGE benchmark and Sahay et al.'s unrelated e-commerce system named MIRAGE; final naming still requires an author decision recorded in `paper/notes/unresolved_questions.md`.
