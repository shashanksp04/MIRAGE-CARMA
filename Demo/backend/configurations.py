"""Separate demo configuration; research presets remain authoritative."""
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRESET = "ablation_8_full_domain_filtered"


@dataclass(frozen=True)
class Preset:
    id: str
    name: str
    db_on: bool
    crop_dict_on: bool
    progressive_filtering_on: bool
    confidence_on: bool
    web_search_on: bool
    domain_filter_on: bool
    ingestion_loop_on: bool

    def snapshot(self):
        return asdict(self)


def presets():
    raw = json.loads((ROOT / "rag_agent/ablation_configs.json").read_text())
    templates = set(re.findall(r"<!--\s*instruction:([a-z0-9_]+)\s*-->",
                              (ROOT / "rag_agent/model_instructions.md").read_text()))
    result = {}
    for key, fields in raw.items():
        if key not in templates:
            raise ValueError(f"Preset {key} has no matching instruction template")
        preset = Preset(id=key, **fields)
        if any(type(getattr(preset, field)) is not bool for field in fields if field != "name"):
            raise ValueError(f"Invalid feature flags in {key}")
        result[key] = preset
    return result


def get_preset(key=DEFAULT_PRESET):
    try:
        return presets()[key]
    except KeyError:
        raise ValueError("Unknown preset; use an ID from /api/configurations") from None


FEATURES = ("db_on", "crop_dict_on", "progressive_filtering_on", "confidence_on",
            "web_search_on", "domain_filter_on", "ingestion_loop_on")
WORKFLOW_FEATURES = FEATURES[2:]


@dataclass(frozen=True)
class CustomPreset(Preset):
    instruction_preset_id: str
    source_snapshot: tuple
    template_snapshot: tuple
    overrides: tuple

    def snapshot(self):
        return {key: getattr(self, key) for key in ("id", "name", *FEATURES)} | {
            "instruction_preset_id": self.instruction_preset_id,
            "overrides": dict(self.overrides), "custom": True}


def workflow_profiles():
    """Only workflows with an authoritative instruction/tool combination."""
    profiles = {}
    for preset in presets().values():
        signature = tuple(getattr(preset, key) for key in WORKFLOW_FEATURES)
        profiles.setdefault(signature, {"id": preset.id, "name": preset.name,
            **{key: getattr(preset, key) for key in WORKFLOW_FEATURES}})
    return list(profiles.values())


def resolve_configuration(preset_id=DEFAULT_PRESET, overrides=None):
    source = get_preset(preset_id)
    overrides = dict(overrides or {})
    if set(overrides) - set(FEATURES) or any(type(v) is not bool for v in overrides.values()):
        raise ValueError("Overrides must contain only supported boolean feature flags")
    if not overrides:
        return source
    flags = {key: overrides.get(key, getattr(source, key)) for key in FEATURES}
    matches = [p for p in presets().values() if all(
        getattr(p, key) == flags[key] for key in WORKFLOW_FEATURES)]
    if not matches:
        raise ValueError("Unsupported workflow: choose a supported workflow profile. Web search and ingestion "
                         "require confidence and progressive retrieval; domain filtering requires web search.")
    template = next((p for p in matches if p.id == source.id), matches[0])
    return CustomPreset(id=source.id, name="Custom configuration", **flags,
        instruction_preset_id=template.id, source_snapshot=tuple(source.snapshot().items()),
        template_snapshot=tuple(template.snapshot().items()), overrides=tuple(sorted(overrides.items())))


def validate_snapshot(preset):
    """Reject edits to authoritative presets after a run was submitted."""
    if isinstance(preset, CustomPreset):
        if (tuple(get_preset(preset.id).snapshot().items()) != preset.source_snapshot or
                tuple(get_preset(preset.instruction_preset_id).snapshot().items()) != preset.template_snapshot):
            raise ValueError("Preset changed after submission; submit a new run")
    elif get_preset(preset.id) != preset:
        raise ValueError("Preset changed after submission; submit a new run")


@dataclass(frozen=True)
class Settings:
    rag_url: str = "http://127.0.0.1:11434/v1"
    generation_url: str = "http://127.0.0.1:11437/v1"
    rag_model: str = "meta-llama/Llama-3.2-11B-Vision-Instruct"
    generation_model: str = "meta-llama/Llama-3.2-11B-Vision-Instruct"
    qdrant_url: str = "http://127.0.0.1:6333"
    runtime_collection: str = "mirage_demo_runtime"
    crop_dictionary: Path = ROOT / "Inference/CropDatabase.json"
    data_dir: Path = ROOT / "Demo/data"
    device: str = "cpu"
    timeout_seconds: float = 600
    max_runs: int = 100
    max_events: int = 2000
    max_image_bytes: int = 10 * 1024 * 1024
    base_collection: str = "mirage_base"
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    vector_size: int = 768

    def __post_init__(self):
        if not re.fullmatch(r"mirage_demo_runtime(?:_[A-Za-z0-9_-]{1,48})?", self.runtime_collection):
            raise ValueError("Runtime collection must be mirage_demo_runtime or a suffixed demo collection")
        if self.base_collection != "mirage_base":
            raise ValueError("Demo base collection must be mirage_base")
        for url in (self.rag_url, self.generation_url, self.qdrant_url):
            parsed = urlparse(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
                raise ValueError("Service endpoints must be HTTP(S) URLs without embedded credentials")
        if self.rag_url.rstrip("/") == self.generation_url.rstrip("/"):
            raise ValueError("Use distinct RAG and generation endpoints")
        if self.timeout_seconds <= 0 or self.max_runs < 1 or self.max_events < 20:
            raise ValueError("Invalid timeout or retention bounds")

    @classmethod
    def from_env(cls):
        values = {}
        for name in ("rag_url", "generation_url", "rag_model", "generation_model",
                     "qdrant_url", "runtime_collection", "device"):
            value = os.getenv("DEMO_" + name.upper())
            if value:
                values[name] = value
        if "qdrant_url" not in values and os.getenv("QDRANT_URL"):
            values["qdrant_url"] = os.environ["QDRANT_URL"]
        for name in ("crop_dictionary", "data_dir"):
            if os.getenv("DEMO_" + name.upper()):
                values[name] = Path(os.environ["DEMO_" + name.upper()]).resolve()
        for name, convert in (("timeout_seconds", float), ("max_runs", int), ("max_events", int)):
            if os.getenv("DEMO_" + name.upper()):
                values[name] = convert(os.environ["DEMO_" + name.upper()])
        return cls(**values)
