import asyncio
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from Demo.backend.configurations import Settings, get_preset
from Demo.backend.demo_runner import DemoRunner
from Demo.backend.locking import RunLock, BusyError
from Demo.backend.schemas import Query


class FakeDatabase:
    """Explicit unit-test fixture; never used in live backend."""
    def __init__(self):
        self.points = 0
        self.enabled = []

    def ensure_runtime(self, use_base=True):
        self.enabled.append(use_base)

    def count(self):
        return self.points


class FakePipeline:
    status = "success"
    instances = []

    def __init__(self, settings, preset):
        self.settings, self.preset = settings, preset
        self.calls = []
        self.__class__.instances.append(self)

    def initialize(self):
        pass

    def enrich(self, query):
        self.calls.append("enrich")
        return query + " corn"

    def extract(self, images, query):
        self.calls.append("extract")
        return {"status": "success", "attributes": "yellow spots"}

    async def rag(self, query, location, run_id):
        self.query = query
        return {"status": self.status, "evidence": [{"text": "actual fixture evidence", "metadata": {"url": "https://example.edu"}}]}

    def generate(self, query, images):
        self.calls.append("generate")
        self.generation_query, self.images = query, images
        return "fixture answer"

    def close(self):
        pass


class RunnerTests(unittest.TestCase):
    def setUp(self):
        FakePipeline.status = "success"
        FakePipeline.instances.clear()
        self.db = FakeDatabase()
        self.runner = DemoRunner(Settings(), self.db, FakePipeline)

    def test_images_only_enrich_retrieval_final_generation_sees_actual_images(self):
        result = asyncio.run(self.runner.run(Query(question="Identify", task_type="identification"), ["image.jpg"]))
        pipeline = FakePipeline.instances[-1]
        self.assertEqual(result["status"], "completed")
        self.assertIn("yellow spots", pipeline.query)
        self.assertNotIn("yellow spots", pipeline.generation_query)
        self.assertIn("actual fixture evidence", pipeline.generation_query)
        self.assertEqual(pipeline.images, ["image.jpg"])
        self.assertTrue(pipeline.preset.crop_dict_on)
        self.assertEqual(self.db.enabled, [True])

    def test_insufficient_and_invalid_results_never_generate(self):
        for status, outcome in (("insufficient_evidence", "insufficient_evidence"), ("invalid_output", "failed")):
            FakePipeline.status = status
            result = asyncio.run(self.runner.run(Query(question="Question")))
            self.assertEqual(result["status"], outcome)
            self.assertIsNone(result["answer"])
            self.assertNotIn("generate", FakePipeline.instances[-1].calls)

    def test_management_does_not_extract_and_no_crop_preset_is_honored(self):
        request = Query(question="How to manage?", preset_id="ablation_9_full_no_db_no_crop_dict")
        asyncio.run(self.runner.run(request))
        self.assertEqual(self.db.enabled, [False])
        self.assertEqual(FakePipeline.instances[-1].calls, ["generate"])

    def test_consecutive_queries_do_not_clear_runtime(self):
        first = asyncio.run(self.runner.run(Query(question="Question one")))
        self.db.points = 4
        second = asyncio.run(self.runner.run(Query(question="Question two")))
        self.assertEqual(first["runtime_after"], 0)
        self.assertEqual(second["runtime_before"], 4)
        self.assertEqual(second["runtime_after"], 4)

    def test_configuration_is_immutable_and_collection_allowlist_enforced(self):
        with self.assertRaises(Exception):
            get_preset().db_on = False
        for name in ("mirage_base", "mirage_runtime_batch_20260101_000000", "other"):
            with self.assertRaises(ValueError):
                replace(Settings(), runtime_collection=name)

    def test_lock_excludes_other_process_handles_and_releases(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = RunLock(Path(tmp)), RunLock(Path(tmp))
            with first:
                with self.assertRaises(BusyError):
                    second.acquire()
            with second:
                pass
