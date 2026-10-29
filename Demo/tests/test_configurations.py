"""Phase 4 configuration contracts; no model inference is simulated as live validation."""
import asyncio
from dataclasses import FrozenInstanceError, replace
from itertools import product
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from Demo.backend.configurations import (
    FEATURES, WORKFLOW_FEATURES, Settings, get_preset, presets,
    resolve_configuration, validate_snapshot, workflow_profiles,
)
from Demo.backend.demo_runner import DemoRunner, Pipeline
from Demo.backend.schemas import Query
from Demo.tests.test_batch_baseline import agent_class
from Demo.tests.test_runner import FakeDatabase, FakePipeline
from Demo.tests.test_api import api, wait_done


def initialize_flags(agent):
    for name in ("use_progressive_filtering", "use_confidence_eval", "use_web_search",
                 "use_domain_filter", "use_ingestion_loop"):
        setattr(agent, name, True)


def test_every_feature_combination_is_either_explicitly_supported_or_rejected():
    supported = {tuple(profile[key] for key in WORKFLOW_FEATURES) for profile in workflow_profiles()}
    accepted = 0
    for values in product((False, True), repeat=len(FEATURES)):
        overrides = dict(zip(FEATURES, values))
        if values[2:] not in supported:
            with pytest.raises(ValueError, match="Unsupported workflow"):
                Query(question="q", overrides=overrides)
            continue
        accepted += 1
        config = Query(question="q", overrides=overrides).configuration()
        assert all(getattr(config, key) == overrides[key] for key in FEATURES)
        cls = agent_class()
        agent = cls.__new__(cls)
        initialize_flags(agent)
        agent.ablation_id = config.instruction_preset_id
        agent.ablation_settings = agent._extract_ablation_settings(agent.ablation_id)
        agent._apply_ablation_settings()
        agent.tools_list = agent._build_tools_list()
        instruction = agent._get_agent_instruction()
        assert agent.applied_instruction_key == config.instruction_preset_id
        assert "fallback" not in agent.applied_instruction_key
        names = {tool.__name__ for tool in agent.tools_list}
        for name, flag in (("_tracked_evaluate_confidence", "confidence_on"),
                           ("_tracked_web_search", "web_search_on"),
                           ("_tracked_extract_keywords", "web_search_on"),
                           ("_tracked_add_web_content", "ingestion_loop_on"),
                           ("_tracked_add_pdf_content", "ingestion_loop_on")):
            assert (name in names) == overrides[flag]
            # Existing templates describe web ingestion; PDF ingestion shares its flag.
            if name != "_tracked_add_pdf_content":
                assert (name in instruction) == overrides[flag]
        assert agent.use_progressive_filtering == config.progressive_filtering_on
        assert agent.use_domain_filter == config.domain_filter_on
    assert accepted == 20


@pytest.mark.parametrize("overrides", [{"web_search_on": "false"}, {"db_on": 0},
    {"db_on": None}, {"visual_extraction": False}, {"ingestion_loop_on": False}])
def test_invalid_or_unsupported_overrides_are_rejected(overrides):
    with pytest.raises(ValueError):
        Query(question="q", overrides=overrides)


def test_frozen_configuration_and_authoritative_drift_detection():
    query = Query(question="q", overrides={"db_on": False})
    config = query.configuration()
    with pytest.raises(FrozenInstanceError):
        config.db_on = True
    with pytest.raises(ValueError):
        query.overrides.db_on = True
    config.snapshot()["overrides"]["db_on"] = True
    assert not config.db_on
    validate_snapshot(config)
    original = presets()
    changed = replace(original[config.instruction_preset_id], name="Edited template configuration")
    with patch("Demo.backend.configurations.get_preset", side_effect=lambda key: changed if key == changed.id else original[key]):
        with pytest.raises(ValueError, match="changed after submission"):
            validate_snapshot(config)


def test_all_presets_runner_smoke_and_switching_preserves_runtime():
    db = FakeDatabase()
    runner = DemoRunner(Settings(), db, FakePipeline)
    FakePipeline.status = "success"
    for index, preset in enumerate(presets().values()):
        db.points = index + 5
        result = asyncio.run(runner.run(Query(question="Synthetic smoke", preset_id=preset.id)))
        assert result["status"] == "completed"
        assert result["runtime_before"] == result["runtime_after"] == index + 5
        assert result["config"] == preset.snapshot()
        assert db.enabled[-1] == preset.db_on
        assert ("enrich" in FakePipeline.instances[-1].calls) == preset.crop_dict_on


def test_pipeline_initialization_uses_resolved_template_and_explicit_base(monkeypatch):
    cls = agent_class()
    captured = {}
    class Agent(cls):
        def __init__(self, **kwargs):
            initialize_flags(self)
            captured.update(kwargs)
            self.ablation_id = kwargs["ablation_id"]
            self.ablation_settings = self._extract_ablation_settings(self.ablation_id)
            self._apply_ablation_settings()
            self.tools_list = self._build_tools_list()
        def main(self):
            self._get_agent_instruction()
            return object()
    monkeypatch.setitem(sys.modules, "rag_agent.main", SimpleNamespace(MainAgent=Agent))
    monkeypatch.setitem(sys.modules, "rag_agent.crop_query_enrichment", SimpleNamespace(CropQueryEnricher=lambda *a, **k: None))
    monkeypatch.setitem(sys.modules, "Inference.visual_attribute_extractor", SimpleNamespace(VisualAttributeExtractor=lambda *a, **k: None))
    config = resolve_configuration(overrides={"db_on": False, "crop_dict_on": False,
        "web_search_on": False, "domain_filter_on": False, "ingestion_loop_on": False})
    pipeline = Pipeline(Settings(), config)
    pipeline.initialize()
    assert captured["ablation_id"] == "ablation_5_uncertainty_aware_rag"
    assert not captured["use_base_collection"]
    assert pipeline.agent.applied_instruction_key == captured["ablation_id"]
    assert len(pipeline.agent.tools_list) == 2


def test_resolve_readiness_submission_and_record_share_effective_configuration(api):
    client, app = api
    payload = {"question": "Synthetic custom smoke", "overrides": {"db_on": False, "crop_dict_on": False}}
    config = client.post("/api/configurations/resolve", json=payload).json()["config"]
    checked = []
    app.state.health.check = lambda preset: checked.append(preset.snapshot()) or {"ready": True, "checks": {}}
    assert client.post("/api/health", json=payload).status_code == 200
    response = client.post("/api/runs", json=payload)
    assert response.status_code == 202
    record = wait_done(client, response.json()["run_id"])
    assert record["metadata"]["config"] == record["result"]["config"] == config
    assert checked == [config, config]
    assert client.post("/api/configurations/resolve", json={"question": "q", "overrides": {"confidence_on": False}}).status_code == 422
