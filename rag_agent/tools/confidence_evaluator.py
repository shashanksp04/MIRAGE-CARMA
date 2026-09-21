from __future__ import annotations

import statistics
from typing import Any, Dict, Optional, Sequence
from rag_agent.utils.rag_state import RetrievalResult


# Retrieval and confidence calibration constants.
K = 5
MIN_RESULTS = 2
HARD_RELEVANCE_FLOOR = 0.60
RELEVANT_CHUNK_THRESHOLD = 0.65

SIMILARITY_WEIGHT = 0.70
COVERAGE_WEIGHT = 0.15
CONSISTENCY_WEIGHT = 0.10
SCOPE_WEIGHT = 0.05

HIGH_CONFIDENCE_THRESHOLD = 0.78
MEDIUM_CONFIDENCE_THRESHOLD = 0.60

SCOPE_SCORES = {
    "hardiness_zone_month_title": 1.00,
    "hardiness_zone_month": 0.90,
    "hardiness_zone_title": 0.85,
    "hardiness_zone": 0.80,
    "month": 0.75,
    "title": 0.70,
    "semantic_only": 0.40,
    "no_results": 0.00,
}

_STRATEGY_SCOPE_KEYS = {
    "hardiness_zone+month_year+title": "hardiness_zone_month_title",
    "hardiness_zone+month_year": "hardiness_zone_month",
    "hardiness_zone+title": "hardiness_zone_title",
    "hardiness_zone": "hardiness_zone",
    "month_year": "month",
    "title": "title",
    "semantic_only": "semantic_only",
    "no_results": "no_results",
}


def _scope_score(strategy_name: str) -> float:
    normalized_name = _STRATEGY_SCOPE_KEYS.get(strategy_name, strategy_name)
    return float(SCOPE_SCORES.get(normalized_name, 0.0))


def _low_confidence(
    *,
    reason: str,
    strategy_name: str,
    top_similarity: Optional[float] = None,
    similarities: Optional[Sequence[float]] = None,
    relevant_similarities: Optional[Sequence[float]] = None,
) -> Dict[str, Any]:
    raw_similarities = list(similarities or [])
    relevant = list(relevant_similarities or [])
    diagnostics: Dict[str, Any] = {
        "reason": reason,
        "strategy_used": strategy_name,
        "returned_count": len(raw_similarities),
        "num_chunks": len(raw_similarities),
        "relevant_count": len(relevant),
        "raw_similarities": raw_similarities,
        "relevant_similarities": relevant,
        "top_similarity": top_similarity,
        "scope_score": _scope_score(strategy_name),
    }
    return {
        "confidence": "low",
        "confidence_level": "low",
        "score": 0.0,
        "confidence_score": 0.0,
        "diagnostics": diagnostics,
    }


def evaluate_confidence(
    results: Sequence[Dict[str, Any]] | RetrievalResult,
    strategy_name: Optional[str] = None,
    *,
    k: int = K,
    min_results: int = MIN_RESULTS,
    hard_relevance_floor: float = HARD_RELEVANCE_FLOOR,
    relevant_chunk_threshold: float = RELEVANT_CHUNK_THRESHOLD,
) -> Dict[str, Any]:
    """Evaluate confidence using raw Qdrant cosine similarities."""
    if isinstance(results, RetrievalResult):
        retrieval = results
        strategy_name = retrieval.strategy
        results = retrieval.results
    strategy_name = strategy_name or "no_results"
    if not results:
        return _low_confidence(reason="no_results", strategy_name=strategy_name)

    similarities = [float(result["similarity"]) for result in results]
    top_similarity = max(similarities)

    if top_similarity < hard_relevance_floor:
        return _low_confidence(
            reason="below_hard_relevance_floor",
            strategy_name=strategy_name,
            top_similarity=top_similarity,
            similarities=similarities,
        )

    relevant_results = [
        result
        for result in results
        if float(result["similarity"]) >= relevant_chunk_threshold
    ]
    relevant_similarities = [
        float(result["similarity"]) for result in relevant_results
    ]

    if len(relevant_results) < min_results:
        return _low_confidence(
            reason="insufficient_relevant_results",
            strategy_name=strategy_name,
            top_similarity=top_similarity,
            similarities=similarities,
            relevant_similarities=relevant_similarities,
        )

    similarity_score = sum(relevant_similarities) / len(relevant_similarities)
    coverage_score = min(len(relevant_results) / k, 1.0)

    if len(relevant_similarities) > 1:
        variance = statistics.pvariance(relevant_similarities)
        consistency_factor = max(0.0, 1.0 - variance * 5)
    else:
        variance = 0.0
        consistency_factor = 0.0
    consistency_score = similarity_score * consistency_factor
    scope_score = _scope_score(strategy_name)

    confidence_score = round(
        SIMILARITY_WEIGHT * similarity_score
        + COVERAGE_WEIGHT * coverage_score
        + CONSISTENCY_WEIGHT * consistency_score
        + SCOPE_WEIGHT * scope_score,
        3,
    )

    if confidence_score >= HIGH_CONFIDENCE_THRESHOLD:
        confidence = "high"
    elif confidence_score >= MEDIUM_CONFIDENCE_THRESHOLD:
        confidence = "medium"
    else:
        confidence = "low"

    diagnostics = {
        "reason": "valid_retrieval",
        "strategy_used": strategy_name,
        "returned_count": len(results),
        "num_chunks": len(results),
        "relevant_count": len(relevant_results),
        "raw_similarities": similarities,
        "relevant_similarities": relevant_similarities,
        "top_similarity": top_similarity,
        "similarity_score": similarity_score,
        "coverage_score": coverage_score,
        "variance": variance,
        "consistency_factor": consistency_factor,
        "consistency_score": consistency_score,
        "scope_score": scope_score,
        "confidence_score": confidence_score,
        "confidence": confidence,
    }
    return {
        "confidence": confidence,
        "confidence_level": confidence,
        "score": confidence_score,
        "confidence_score": confidence_score,
        "diagnostics": diagnostics,
    }


class ConfidenceEvaluator:
    """Agent tool for evaluating retrieval confidence."""

    def __init__(self, store=None, content_utils=None):
        self.store = store
        self.content_utils = content_utils

    def evaluate_retrieval_confidence(
        self,
        *,
        query: Optional[str] = None,
        retrieval_result: Optional[RetrievalResult] = None,
        location: Optional[str] = None,
        month_year: Optional[str] = None,
        title: Optional[str] = None,
        k: int = K,
        use_progressive_filtering: bool = True,
    ) -> dict:
        """Evaluate an existing retrieval result without performing I/O."""
        if retrieval_result is None:
            return {
                "status": "success",
                "confidence_score": 0.0,
                "confidence_level": "low",
                "diagnostics": {
                    "reason": "retrieval_state_missing",
                    "strategy_used": "no_results",
                    "returned_count": 0,
                    "num_chunks": 0,
                    "relevant_count": 0,
                },
            }

        evaluation = evaluate_confidence(
            retrieval_result,
            k=k,
            min_results=MIN_RESULTS,
        )
        evaluation["status"] = "success"
        evaluation["diagnostics"]["used_filter"] = retrieval_result.used_filter
        return evaluation
