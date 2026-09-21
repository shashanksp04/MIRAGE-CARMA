#!/usr/bin/env python3
"""Focused tests for raw-similarity confidence evaluation."""

from __future__ import annotations

import unittest

from rag_agent.tools.confidence_evaluator import evaluate_confidence

try:
    from rag_agent.utils.ContentUtils import ContentUtils
    CONTENT_UTILS_IMPORT_ERROR = None
except ModuleNotFoundError as exc:
    ContentUtils = None
    CONTENT_UTILS_IMPORT_ERROR = exc


def _results(similarities):
    return [
        {"text": f"chunk-{index}", "metadata": {}, "similarity": similarity}
        for index, similarity in enumerate(similarities)
    ]


class ConfidenceEvaluationTests(unittest.TestCase):
    def test_no_results_is_low(self):
        result = evaluate_confidence([], "no_results")
        self.assertEqual(result["confidence_level"], "low")
        self.assertEqual(result["diagnostics"]["reason"], "no_results")

    def test_hard_relevance_floor_rejects_weak_neighbors(self):
        result = evaluate_confidence(
            _results([0.58, 0.57, 0.56, 0.54, 0.52]),
            "semantic_only",
        )
        self.assertEqual(result["confidence_level"], "low")
        self.assertEqual(
            result["diagnostics"]["reason"],
            "below_hard_relevance_floor",
        )

    def test_insufficient_relevant_results_is_low(self):
        result = evaluate_confidence(
            _results([0.70, 0.64, 0.55, 0.50, 0.49]),
            "semantic_only",
        )
        self.assertEqual(result["confidence_level"], "low")
        self.assertEqual(
            result["diagnostics"]["reason"],
            "insufficient_relevant_results",
        )
        self.assertEqual(result["diagnostics"]["relevant_count"], 1)

    def test_scores_use_relevant_chunks_only(self):
        result = evaluate_confidence(
            _results([0.83, 0.79, 0.67, 0.54, 0.49]),
            "semantic_only",
        )
        diagnostics = result["diagnostics"]
        self.assertEqual(diagnostics["relevant_similarities"], [0.83, 0.79, 0.67])
        self.assertAlmostEqual(diagnostics["similarity_score"], (0.83 + 0.79 + 0.67) / 3)
        self.assertAlmostEqual(diagnostics["coverage_score"], 0.6)

    def test_consistency_is_scaled_by_similarity(self):
        result = evaluate_confidence(
            _results([0.67, 0.66, 0.66]),
            "semantic_only",
        )
        diagnostics = result["diagnostics"]
        self.assertLess(diagnostics["consistency_score"], 1.0)
        self.assertAlmostEqual(
            diagnostics["consistency_score"],
            diagnostics["similarity_score"] * diagnostics["consistency_factor"],
        )

    def test_single_relevant_chunk_has_no_consistency_contribution(self):
        result = evaluate_confidence(
            _results([0.70, 0.64, 0.55]),
            "semantic_only",
            min_results=1,
        )
        self.assertEqual(result["diagnostics"]["consistency_score"], 0.0)

    def test_medium_example(self):
        result = evaluate_confidence(_results([0.72, 0.70]), "hardiness_zone")
        self.assertEqual(result["confidence_level"], "medium")
        self.assertAlmostEqual(result["confidence_score"], 0.668, places=3)

    def test_high_example(self):
        result = evaluate_confidence(
            _results([0.88, 0.87, 0.84, 0.82, 0.81]),
            "hardiness_zone",
        )
        self.assertEqual(result["confidence_level"], "high")
        self.assertGreaterEqual(result["confidence_score"], 0.78)


@unittest.skipIf(
    CONTENT_UTILS_IMPORT_ERROR is not None,
    f"ContentUtils dependencies unavailable: {CONTENT_UTILS_IMPORT_ERROR}",
)
class ProgressiveEligibilityTests(unittest.TestCase):
    class _Tokenizer:
        @staticmethod
        def encode(text, **kwargs):
            return [1]

        @staticmethod
        def decode(tokens, **kwargs):
            return "query"

    class _Embedding:
        @staticmethod
        def embed_one(query):
            return [1.0]

    class _Store:
        def __init__(self, results):
            self.results = results

        def search(self, **kwargs):
            return self.results

    def _content_utils(self, results):
        content_utils = ContentUtils.__new__(ContentUtils)
        content_utils.tokenizer = self._Tokenizer()
        content_utils.embedding_fn = self._Embedding()
        return content_utils, self._Store(results)

    def test_retrieval_rejects_five_irrelevant_neighbors(self):
        content_utils, store = self._content_utils(
            _results([0.58, 0.57, 0.56, 0.54, 0.52])
        )
        retrieval = content_utils.retrieve_with_priority_filters(
            query="Noble Fir propagation",
            store=store,
            use_progressive_filtering=False,
        )
        self.assertIsNone(retrieval.used_filter)
        self.assertEqual(retrieval.strategy, "no_results")
        self.assertEqual(retrieval.relevant_results, [])

    def test_retrieval_returns_only_relevant_chunks(self):
        content_utils, store = self._content_utils(
            _results([0.83, 0.79, 0.54, 0.52, 0.49])
        )
        retrieval = content_utils.retrieve_with_priority_filters(
            query="Noble Fir propagation",
            store=store,
            use_progressive_filtering=False,
        )
        self.assertIsNone(retrieval.used_filter)
        self.assertEqual(retrieval.strategy, "semantic_only")
        self.assertEqual(
            [item["similarity"] for item in retrieval.relevant_results],
            [0.83, 0.79],
        )


if __name__ == "__main__":
    unittest.main()
