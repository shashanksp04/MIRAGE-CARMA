from __future__ import annotations

from rag_agent.tools.confidence_evaluator import K, MIN_RESULTS, RELEVANT_CHUNK_THRESHOLD
from rag_agent.utils.rag_state import RetrievalResult


class DualCollectionRetriever:
    """One retrieval interface for optional curated base plus active runtime."""

    def __init__(self, base_store, runtime_store, content_utils):
        self.base_store = base_store
        self.runtime_store = runtime_store
        self.content_utils = content_utils

    @staticmethod
    def _dedupe(results):
        selected = {}
        for result in results:
            metadata = result.get("metadata", {})
            key = metadata.get("content_hash") or metadata.get("chunk_id") or result.get("text")
            previous = selected.get(key)
            if previous is None or (result.get("retrieval_source") == "base" and previous.get("retrieval_source") != "base"):
                selected[key] = result
        # Similarity is canonical here: higher cosine score is better.
        return sorted(selected.values(), key=lambda r: r.get("similarity", -1.0), reverse=True)

    def retrieve_with_priority_filters(self, *, query, location=None, month_year=None,
                                       title=None, k=K, min_results=MIN_RESULTS,
                                       use_progressive_filtering=True,
                                       query_embedding=None):
        if query_embedding is None:
            _, query_embedding = self.content_utils.embed_query(query)
        stores = [("runtime", self.runtime_store)]
        if self.base_store is not None:
            stores.insert(0, ("base", self.base_store))
        evaluations = []
        for source, store in stores:
            retrieval = self.content_utils.retrieve_with_priority_filters(
                query=query, store=store, location=location, month_year=month_year,
                title=title, k=k, min_results=min_results,
                use_progressive_filtering=use_progressive_filtering,
                query_embedding=query_embedding,
            )
            results = retrieval.results
            for result in retrieval.relevant_results:
                result["retrieval_source"] = source
            for result in results:
                result.setdefault("retrieval_source", source)
            evaluations.append((retrieval, source))
        merged = self._dedupe([r for retrieval, _ in evaluations for r in retrieval.results])[:k]
        if not merged:
            return RetrievalResult(
                query=query,
                used_filter=None,
                strategy="no_results",
                strategy_diagnostics=[
                    diagnostic
                    for retrieval, _ in evaluations
                    for diagnostic in retrieval.strategy_diagnostics
                ],
                query_embedding=query_embedding,
            )
        # Keep the existing strategy naming while confidence sees the merged evidence.
        selected = max(evaluations, key=lambda e: len(e[0].relevant_results))[0]
        relevant = [
            result for result in merged
            if float(result.get("similarity", 0.0)) >= RELEVANT_CHUNK_THRESHOLD
        ]
        return RetrievalResult(
            query=query,
            used_filter=selected.used_filter,
            strategy=selected.strategy,
            results=merged,
            relevant_results=relevant,
            strategy_diagnostics=[
                diagnostic
                for retrieval, _ in evaluations
                for diagnostic in retrieval.strategy_diagnostics
            ],
            query_embedding=query_embedding,
        )


class CrossCollectionDeduplicator:
    def __init__(self, base_store, runtime_store):
        self.base_store = base_store
        self.runtime_store = runtime_store

    def find_duplicate(self, content_hash):
        if self.base_store is not None and self.base_store.content_hash_exists(content_hash):
            return "base"
        if self.runtime_store.content_hash_exists(content_hash):
            return "runtime"
        return None
