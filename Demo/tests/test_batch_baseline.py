import ast
import json
import re
import unittest
from pathlib import Path
from urllib.parse import urlparse

from Demo.tests.source_loader import ROOT, definitions
from rag_agent.tools.confidence_evaluator import MIN_RESULTS
from rag_agent.utils.observation import observe_tool, emit, observing
from rag_agent.utils.rag_state import (
    RAGRequestState, RAGResult, RetrievalResult, RAG_SUCCESS,
    RAG_INSUFFICIENT_EVIDENCE, RAG_INVALID_OUTPUT,
)


def agent_class():
    return definitions("rag_agent/main.py", {"MainAgent"}, {
        "Path": Path, "json": json, "re": re,
        "MIN_RESULTS": MIN_RESULTS, "RAGResult": RAGResult,
        "RAG_SUCCESS": RAG_SUCCESS, "RAG_INVALID_OUTPUT": RAG_INVALID_OUTPUT,
        "RAG_INSUFFICIENT_EVIDENCE": RAG_INSUFFICIENT_EVIDENCE,
        "observe_tool": observe_tool,
        "emit": emit, "observing": observing,
    })["MainAgent"]


class BatchBaselineTests(unittest.TestCase):
    def test_existing_call_signatures_remain_compatible(self):
        baseline = json.loads((Path(__file__).with_name("batch_signatures.json")).read_text())
        for path, signatures in baseline.items():
            tree = ast.parse((ROOT / path).read_text())
            actual = {}
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    actual[node.name] = node.args
                if isinstance(node, ast.ClassDef):
                    for method in node.body:
                        if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            actual[node.name + "." + method.name] = method.args
            for name, signature in signatures.items():
                with self.subTest(path=path, name=name):
                    args = actual[name]
                    # Optional observer parameters may be added at the end.
                    old = ast.parse(f"def f({signature}): pass").body[0].args
                    self.assertEqual([a.arg for a in args.args[:len(old.args)]],
                                     [a.arg for a in old.args])
                    self.assertEqual(ast.unparse(args), signature)

    def test_endpoint_split_and_task_type(self):
        scope = definitions("Inference/generate.py", {
            "_build_endpoints", "_split_endpoints", "_question_type", "build_retrieval_query"
        }, {"urlparse": urlparse})
        rag, gen = scope["_split_endpoints"]("http://gpu:11434/v1", 4, 3, 1)
        self.assertEqual(rag, [f"http://gpu:{p}/v1" for p in (11434,11435,11436)])
        self.assertEqual(gen, ["http://gpu:11437/v1"])
        self.assertEqual(scope["_question_type"]({"task_type": "id"}), "identification")
        self.assertEqual(scope["_question_type"]({"question": "identify this"}), "unknown")
        self.assertEqual(scope["build_retrieval_query"]("query", ""), "query")

    def test_real_presets_match_templates_and_tools(self):
        cls = agent_class()
        agent = cls.__new__(cls)
        for name in ("use_progressive_filtering", "use_confidence_eval", "use_web_search",
                     "use_domain_filter", "use_ingestion_loop"):
            setattr(agent, name, True)
        configs = agent._load_ablation_configs()
        self.assertEqual(len(configs), 8)
        for key, flags in configs.items():
            agent.ablation_id, agent.ablation_settings = key, flags
            agent._apply_ablation_settings()
            tools = agent._build_tools_list()
            expected = 1 + flags["confidence_on"] + 2 * flags["web_search_on"] + 2 * flags["ingestion_loop_on"]
            self.assertEqual(len(tools), expected)
            self.assertTrue(agent._get_agent_instruction())
            self.assertEqual(agent.applied_instruction_key, key)

    def test_structured_outcomes_ignore_agent_prose(self):
        cls = agent_class()
        agent = cls.__new__(cls)
        agent.use_confidence_eval = True
        agent.request_state = RAGRequestState()
        self.assertEqual(agent.finalize_rag_result().status, RAG_INVALID_OUTPUT)
        evidence = [{"text": "a", "similarity": .8}, {"text": "b", "similarity": .8}]
        agent.request_state.latest_retrieval = RetrievalResult("q", None, "semantic_only", evidence, evidence)
        agent.request_state.latest_confidence = {"confidence_level": "high", "confidence_score": .8}
        self.assertEqual(agent.finalize_rag_result(agent_message="no evidence").status, RAG_SUCCESS)
        agent.request_state.latest_confidence["confidence_level"] = "low"
        self.assertEqual(agent.finalize_rag_result(agent_message="confident answer").status,
                         RAG_INSUFFICIENT_EVIDENCE)
