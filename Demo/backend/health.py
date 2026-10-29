"""Read-only readiness checks; model inference remains a cluster smoke test."""
import importlib.util
import json
import os

import httpx

from .configurations import get_preset, Preset


class Health:
    def __init__(self, settings, database):
        self.settings, self.database = settings, database

    def check(self, preset_id):
        preset = preset_id if isinstance(preset_id, Preset) else get_preset(preset_id)
        checks = {}
        for name, url, model in (("rag", self.settings.rag_url, self.settings.rag_model),
                                 ("generation", self.settings.generation_url, self.settings.generation_model)):
            try:
                response = httpx.get(url.rstrip("/") + "/models", timeout=5,
                                     headers={"Authorization": "Bearer token-abc123"})
                response.raise_for_status()
                available = [item["id"] for item in response.json()["data"]]
                checks[name] = {"ready": model in available, "model": model,
                                "message": "Model listed" if model in available else "Configured model is not listed"}
            except Exception:
                checks[name] = {"ready": False, "model": model, "message": "Model endpoint unavailable; check URL and server"}
        database = self.database.status()
        for role in ("base", "runtime"):
            checks[role] = {**database[role], "required": role == "runtime" or preset.db_on,
                           "ready": database[role]["reachable"] and database[role]["compatible"]}
        try:
            dictionary = json.loads(self.settings.crop_dictionary.read_text())
            ready = isinstance(dictionary, dict) and bool(dictionary)
        except (OSError, ValueError):
            ready = False
        checks["crop_dictionary"] = {"required": preset.crop_dict_on, "ready": ready,
                                     "message": "Available" if ready else "Configure DEMO_CROP_DICTIONARY with valid JSON"}
        missing = []
        for module in ("google.adk", "openai", "qdrant_client", "sentence_transformers", "transformers", "PIL"):
            try:
                if importlib.util.find_spec(module) is None:
                    missing.append(module)
            except ModuleNotFoundError:
                missing.append(module)
        checks["dependencies"] = {"ready": not missing, "missing": missing}
        checks["asset_storage"] = {"ready": self.settings.data_dir.is_dir() and
                                   os.access(self.settings.data_dir, os.W_OK),
                                   "message": "Demo input image storage must be writable"}
        checks["web_search"] = {"required": preset.web_search_on, "ready": bool(os.getenv("YOU_API_KEY")),
                                 "message": "Configured" if os.getenv("YOU_API_KEY") else "Set YOU_API_KEY for web-enabled presets"}
        # Verify the configured embedding is locally loadable; this does not
        # instantiate a second model or download weights during every health call.
        try:
            from huggingface_hub import try_to_load_from_cache
            cached = try_to_load_from_cache(self.settings.embedding_model, "config.json")
            embedding_ready = isinstance(cached, str)
        except ImportError:
            embedding_ready = False
        checks["embedding"] = {"ready": embedding_ready, "model": self.settings.embedding_model,
            "message": "Cached model configuration found" if embedding_ready else
                       "Cache the configured embedding model in the mirage environment before serving"}
        return {"api_version": 1, "preset_id": preset.id, "config": preset.snapshot(),
                "ready": all(item["ready"] for item in checks.values() if item.get("required", True)),
                "checks": checks}
