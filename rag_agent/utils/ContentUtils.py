from typing import Any, List, Dict, Optional, Tuple, TYPE_CHECKING
import re
import hashlib
import statistics
from transformers import AutoTokenizer
from rag_agent.utils.metadata import extract_hardiness_zone_for_location
from rag_agent.utils.qdrant_store import chroma_where_to_qdrant_filter
from rag_agent.tools.confidence_evaluator import (
    K,
    MIN_RESULTS,
    RELEVANT_CHUNK_THRESHOLD,
)
from rag_agent.utils.rag_state import RetrievalResult

if TYPE_CHECKING:
    from rag_agent.utils.qdrant_store import QdrantStore


class ContentUtils:
    """
    Utility class for content processing tasks such as
    hashing, chunking, and deduplication checks.
    """

    def __init__(
        self,
        embed_model: str = "BAAI/bge-base-en-v1.5",
        chunk_config: Dict | None = None,
        embedding_fn=None,
    ):
        self.embed_model = embed_model
        self.tokenizer = AutoTokenizer.from_pretrained(embed_model)
        self.embedding_fn = embedding_fn

        self.chunk_config = {
            "pdf": {
                "max_tokens": 480,   # 🔥 below 512
                "overlap": 80,
            },
            "web": {
                "chunk_if_over": 512,  # 🔥 match model limit
                "max_tokens": 480,     # 🔥 SAFE RANGE
                "overlap": 80,
            },
        }

    # -------------------------
    # Hashing
    # -------------------------

    @staticmethod
    def compute_content_hash(text: str) -> str:
        """Computes a normalized SHA-256 hash for text content."""
        normalized = " ".join(text.lower().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    # -------------------------
    # Deduplication
    # -------------------------

    @staticmethod
    def content_hash_exists(store: "QdrantStore", content_hash: str) -> bool:
        """Checks whether a content hash already exists in the collection."""
        return store.content_hash_exists(content_hash)

    # -------------------------
    # Chunking
    # -------------------------

    def chunk_by_tokens(
        self,
        text: str,
        *,
        max_tokens: int,
        overlap: int,
    ) -> List[str]:

        # 🔥 enforce global safety
        max_tokens = min(max_tokens, 512)

        tokens = self.tokenizer.encode(
            text,
            add_special_tokens=False,
            truncation=False  # we want full text BEFORE chunking
        )

        chunks: List[str] = []
        start = 0
        total_tokens = len(tokens)

        while start < total_tokens:
            end = min(start + max_tokens, total_tokens)

            chunk_tokens = tokens[start:end]

            # 🔥 final safety (guarantee <=512)
            chunk_tokens = chunk_tokens[:512]

            chunk_text = self.tokenizer.decode(
                chunk_tokens,
                skip_special_tokens=True
            )

            chunks.append(chunk_text)

            if end == total_tokens:
                break

            start = max(end - overlap, 0)

        return chunks

    def normalize_query(self, query: str) -> str:
        return self.tokenizer.decode(
            self.tokenizer.encode(
                query,
                truncation=True,
                max_length=512,
                add_special_tokens=False,
            ),
            skip_special_tokens=True,
        )

    def embed_query(self, query: str) -> tuple[str, List[float]]:
        normalized_query = self.normalize_query(query)
        if self.embedding_fn is None:
            raise RuntimeError("embedding_fn is required for Qdrant retrieval")
        return normalized_query, self.embedding_fn.embed_one(normalized_query)

    @staticmethod
    def _canonicalize_similarity(result: Dict[str, Any]) -> Dict[str, Any]:
        """Return a retrieval result with the canonical raw cosine score.

        Older Qdrant adapters exposed ``distance`` (where cosine distance is
        ``1 - cosine_similarity``), while the current retrieval code uses the
        higher-is-better ``similarity`` name.  Normalize at this boundary so
        stale workers or persisted compatibility code cannot break retrieval.
        """
        if "similarity" in result:
            result["similarity"] = float(result["similarity"])
            return result
        if "score" in result:
            # Some adapters expose Qdrant's raw cosine score as ``score``.
            result["similarity"] = float(result["score"])
            return result
        if "distance" in result:
            # Legacy adapter format: distance = 1 - cosine similarity.
            result["similarity"] = 1.0 - float(result["distance"])
            return result
        raise KeyError(
            "Retrieval result has no similarity-compatible field; "
            f"available keys={sorted(result.keys())}"
        )
        
    def retrieve_with_priority_filters(
        self,
        *,
        query: str,
        store: "QdrantStore",
        location: Optional[str] = None,
        month_year: Optional[str] = None,
        title: Optional[str] = None,
        k: int = K,
        min_results: int = MIN_RESULTS,
        use_progressive_filtering: bool = True,
        query_embedding: Optional[List[float]] = None,
    ) -> RetrievalResult:
        """
        Performs semantic retrieval with optional progressive metadata filtering.

        Args:
            query: Query text to retrieve against.
            collection: QdrantStore handle for vector search.
            location: Optional location used to derive hardiness zone.
            month_year: Optional month/year metadata filter.
            title: Optional title metadata filter.
            k: Number of retrieval results.
            min_results: Minimum number of chunks required for a strategy to qualify.
            use_progressive_filtering: When True, evaluate all progressive metadata
                strategies plus semantic fallback. When False, use semantic-only retrieval.

        Returns:
            Structured retrieval state containing raw candidates, relevant results,
            the selected strategy, and per-strategy diagnostics.
        """

        def _clean(value: Optional[str], *, upper: bool = False) -> Optional[str]:
            """Normalize incoming metadata values and treat NULL-like strings as missing."""
            if value is None:
                return None
            if not isinstance(value, str):
                value = str(value)

            v = value.strip()
            if not v:
                return None

            # Treat these as missing
            if v.upper() in {"NULL", "NONE", "N/A", "NA", "UNKNOWN"}:
                return None

            return v.upper() if upper else v

        def _eq(field: str, val: str) -> Dict:
            """Single equality clause in Chroma where syntax."""
            return {field: {"$eq": val}}

        def _make_where(**kwargs: Optional[str]) -> Optional[Dict]:
            """
            Build a valid Chroma where filter:
            - None if no filters
            - single clause dict if exactly one
            - {"$and": [...]} if multiple
            """
            clauses = []
            for field, val in kwargs.items():
                if val is not None:
                    clauses.append(_eq(field, val))

            if not clauses:
                return None
            if len(clauses) == 1:
                return clauses[0]
            return {"$and": clauses}

        # Clean inputs (and treat "NULL" as None)
        # Note: `location` is only used to derive `hardiness_zone` for metadata filtering.
        location = _clean(location, upper=True)
        month_year = _clean(month_year, upper=False)
        title = _clean(title, upper=False)
        hardiness_zone = _clean(
            extract_hardiness_zone_for_location(location or ""),
            upper=False,
        )

        filter_attempts: List[Tuple[str, Optional[Dict]]] = []

        if use_progressive_filtering:
            # Most specific -> least specific -> semantic only
            if hardiness_zone and month_year and title:
                filter_attempts.append((
                    "hardiness_zone+month_year+title",
                    _make_where(
                        hardiness_zone=hardiness_zone,
                        month_year=month_year,
                        title=title,
                    ),
                ))

            if hardiness_zone and title:
                filter_attempts.append((
                    "hardiness_zone+title",
                    _make_where(hardiness_zone=hardiness_zone, title=title),
                ))

            if title:
                filter_attempts.append(("title", _make_where(title=title)))

            if month_year:
                filter_attempts.append(("month_year", _make_where(month_year=month_year)))

            if hardiness_zone and month_year:
                filter_attempts.append((
                    "hardiness_zone+month_year",
                    _make_where(hardiness_zone=hardiness_zone, month_year=month_year),
                ))

            if hardiness_zone:
                filter_attempts.append(("hardiness_zone", _make_where(hardiness_zone=hardiness_zone)))

            filter_attempts.append(("semantic_only", None))
        else:
            filter_attempts.append(("semantic_only", None))

        k = int(k)
        min_results = int(min_results)


        def _format_results(
            docs: List[str],
            metadatas: List[Dict[str, Any]],
            similarities: List[float],
        ) -> List[Dict[str, Any]]:
            return [
                {"text": doc, "metadata": metadata, "similarity": similarity}
                for doc, metadata, similarity in zip(docs, metadatas, similarities)
            ]

        strategy_evaluations: List[Dict[str, Any]] = []

        query = self.normalize_query(query)
        if self.embedding_fn is None:
            raise RuntimeError("embedding_fn is required for Qdrant retrieval")
        if query_embedding is None:
            query_embedding = self.embedding_fn.embed_one(query)

        for strategy_name, where_filter in filter_attempts:
            qdrant_filter = (
                chroma_where_to_qdrant_filter(where_filter) if where_filter else None
            )
            formatted = store.search(
                query_vector=query_embedding,
                limit=k,
                qdrant_filter=qdrant_filter,
            )
            formatted = [self._canonicalize_similarity(result) for result in formatted]

            docs = [r["text"] for r in formatted]
            metadatas = [r["metadata"] for r in formatted]
            similarities = [float(r["similarity"]) for r in formatted]
            # Keep raw cosine similarity as the canonical per-hit value, while
            # preserving the empirically preferred nonlinear strategy score.
            strategy_scores = [1.0 / (2.0 - similarity) for similarity in similarities]

            relevant_indices = [
                index
                for index, similarity in enumerate(similarities)
                if similarity >= RELEVANT_CHUNK_THRESHOLD
            ]
            relevant_results = [formatted[index] for index in relevant_indices]
            top_similarity = max(similarities) if similarities else None
            relevant_similarities = [similarities[index] for index in relevant_indices]
            similarity_score = (
                sum(relevant_similarities) / len(relevant_similarities)
                if relevant_similarities
                else 0.0
            )
            if len(relevant_similarities) > 1:
                variance = statistics.pvariance(relevant_similarities)
                consistency_factor = max(0.0, 1.0 - variance * 5)
            else:
                variance = 0.0
                consistency_factor = 0.0
            consistency_score = similarity_score * consistency_factor

            doc_count = len(docs)
            normalized_score = (
                sum(strategy_scores[index] for index in relevant_indices)
                / len(relevant_indices)
                if relevant_indices
                else 0.0
            )

            strategy_evaluations.append(
                {
                    "strategy_name": strategy_name,
                    "where_filter": where_filter,
                    "doc_count": doc_count,
                    "docs": docs,
                    "metadatas": metadatas,
                    "similarities": similarities,
                    "formatted_results": formatted,
                    "relevant_results": relevant_results,
                    "relevant_similarities": relevant_similarities,
                    "relevant_count": len(relevant_results),
                    "top_similarity": top_similarity,
                    "similarity_score": similarity_score,
                    "variance": variance,
                    "consistency_factor": consistency_factor,
                    "consistency_score": consistency_score,
                    "normalized_score": normalized_score,
                }
            )

        valid_strategies = [
            s for s in strategy_evaluations
            if s["relevant_count"] >= min_results
        ]

        for s in strategy_evaluations:
            if s["doc_count"] == 0:
                rejection_reason = "no_results"
            elif s["relevant_count"] < min_results:
                rejection_reason = "insufficient_relevant_results"
            else:
                rejection_reason = "valid_retrieval"
            print(
                f"Strategy evaluation: name={s.get('strategy_name')} "
                f"score={float(s.get('normalized_score', 0.0)):.4f} "
                f"returned_count={int(s.get('doc_count', 0))} "
                f"relevant_count={int(s.get('relevant_count', 0))} "
                f"raw_similarities={s.get('similarities', [])} "
                f"relevant_similarities={s.get('relevant_similarities', [])} "
                f"top_similarity={s.get('top_similarity')} "
                f"similarity_score={s.get('similarity_score', 0.0):.4f} "
                f"variance={s.get('variance', 0.0):.6f} "
                f"consistency_factor={s.get('consistency_factor', 0.0):.4f} "
                f"consistency_score={s.get('consistency_score', 0.0):.4f} "
                f"eligible={s['relevant_count'] >= min_results} "
                f"reason={rejection_reason}"
            )

        if valid_strategies:
            best_strategy = max(valid_strategies, key=lambda s: s["normalized_score"])
            return RetrievalResult(
                query=query,
                used_filter=best_strategy["where_filter"],
                strategy=best_strategy["strategy_name"],
                results=best_strategy["formatted_results"],
                relevant_results=best_strategy["relevant_results"],
                strategy_diagnostics=strategy_evaluations,
                query_embedding=query_embedding,
            )

        return RetrievalResult(
            query=query,
            used_filter=None,
            strategy="no_results",
            results=[],
            relevant_results=[],
            strategy_diagnostics=strategy_evaluations,
            query_embedding=query_embedding,
        )
