from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import patch

from Demo.backend.configurations import Settings, resolve_configuration
from Demo.backend.health import Health
from Demo.tests.test_api import ApiDatabase


def test_readiness_checks_actual_models_dictionary_and_preset_requirements(tmp_path, monkeypatch):
    settings = replace(Settings(), crop_dictionary=tmp_path / "crop.json")
    db = ApiDatabase()
    health = Health(settings, db)
    monkeypatch.delenv("YOU_API_KEY", raising=False)
    response = SimpleNamespace(raise_for_status=lambda: None,
        json=lambda: {"data": [{"id": settings.rag_model}]})
    with patch("Demo.backend.health.httpx.get", return_value=response):
        result = health.check("ablation_8_full_domain_filtered")
        assert result["checks"]["rag"]["ready"]
        assert not result["checks"]["crop_dictionary"]["ready"]
        assert not result["checks"]["web_search"]["ready"]
        assert not result["ready"]
        settings.crop_dictionary.write_text(json.dumps({"ILLINOIS": ["corn"]}))
        result = health.check("ablation_2_static_rag")
        assert result["checks"]["crop_dictionary"]["ready"]
        assert not result["checks"]["web_search"]["required"]
        custom = resolve_configuration(overrides={"db_on": False, "crop_dict_on": False,
            "web_search_on": False, "domain_filter_on": False, "ingestion_loop_on": False})
        result = health.check(custom)
        for name in ("base", "crop_dictionary", "web_search"):
            assert not result["checks"][name]["required"]
        assert result["config"] == custom.snapshot()
    with patch("Demo.backend.health.httpx.get", side_effect=OSError("private credentials")):
        result = health.check("ablation_2_static_rag")
        assert not result["checks"]["rag"]["ready"]
        assert "private credentials" not in json.dumps(result)
