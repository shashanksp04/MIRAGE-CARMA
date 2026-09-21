# Terminology

- **MIRAGE:** the agricultural benchmark and source task on which this project builds. Use this name for the benchmark, not for the proposed system.
- **MIRAGE-CARMA:** the proposed metadata-aware, adaptive retrieval-augmented generation system. Use this form consistently in manuscript prose unless project ownership specifies a different final name.
- **curated base collection:** the preloaded, read-only Qdrant collection used during inference (`mirage_base` in the implementation).
- **runtime collection:** the mutable, run-scoped Qdrant collection that receives dynamically acquired web and PDF evidence.
- **progressive metadata retrieval:** evaluation of multiple eligible metadata-filter combinations plus semantic-only retrieval, followed by selection based on retrieval score. Avoid wording that implies the first nonempty filter is accepted.
- **query enrichment:** constrained insertion of crop names from a state-specific crop dictionary. Do not describe it as general query rewriting.
- **confidence evaluation:** a deterministic score computed from retrieval similarity, result coverage, score consistency, and metadata scope. Avoid describing it as calibrated probability or model uncertainty.
- **web augmentation:** search, acquisition, ingestion, and subsequent retrieval over newly added external evidence.
- **preload:** offline construction of the curated base collection; distinguish it from runtime augmentation.
- **ablation condition:** a controlled system configuration. Reserve *component* for an individual mechanism toggled within a condition.
- **behavioral logging:** per-example operational fields and runtime traces that record retrieval status, endpoint, attempts, and whether web search occurred. Do not imply that all internal tool calls are persisted in the output JSONL.
