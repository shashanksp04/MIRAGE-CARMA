"""One-query orchestration, independent of Inference/generate.py startup."""
import argparse
import asyncio
from contextlib import redirect_stdout
import json
import logging
import mimetypes
import os
from pathlib import Path
import sys
import uuid

from .configurations import Settings, get_preset, validate_snapshot
from .database_manager import DatabaseManager
from .locking import RunLock
from .schemas import Query

LOG = logging.getLogger(__name__)
INSUFFICIENT_MESSAGE = (
    "The system could not find enough reliable information to answer confidently. "
    "Try adding a clearer image, more symptoms, or more precise location."
)


class Pipeline:
    """Lazy real inference adapter. No heavyweight imports at API import time."""
    def __init__(self, settings, preset):
        self.settings, self.preset = settings, preset
        self.agent = None

    def initialize(self):
        from rag_agent.main import MainAgent
        from rag_agent.crop_query_enrichment import CropQueryEnricher
        from Inference.visual_attribute_extractor import VisualAttributeExtractor
        s = self.settings
        dictionary = None
        if self.preset.crop_dict_on:
            dictionary = json.loads(s.crop_dictionary.read_text())
            if not isinstance(dictionary, dict) or not dictionary:
                raise ValueError("Crop dictionary must be a nonempty JSON object")
        self.enricher = CropQueryEnricher(s.rag_url, s.rag_model, dictionary,
            enabled=self.preset.crop_dict_on, timeout_seconds=min(s.timeout_seconds, 120))
        self.visual = VisualAttributeExtractor(s.rag_url, s.rag_model,
                                             min(s.timeout_seconds, 45))
        validate_snapshot(self.preset)
        instruction_id = getattr(self.preset, "instruction_preset_id", self.preset.id)
        self.agent = MainAgent(test_model=s.rag_model, embed_model_name=s.embedding_model,
            device=s.device, api_base=s.rag_url, ablation_id=instruction_id,
            qdrant_url=s.qdrant_url, base_collection=s.base_collection,
            use_base_collection=self.preset.db_on, runtime_collection=s.runtime_collection)
        if self.agent.ablation_settings != {key: value for key, value in get_preset(instruction_id).snapshot().items() if key != "id"}:
            raise ValueError("Preset changed after submission; submit a new run")
        # Existing main() sets these globals. Contain that legacy side effect in
        # this dedicated demo process; all clients use explicit endpoint settings.
        old = {key: os.environ.get(key) for key in ("OPENAI_API_BASE", "OPENAI_API_KEY")}
        try:
            self.runner = self.agent.main()
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def enrich(self, query):
        return self.enricher.enrich(query)

    def extract(self, images, query):
        return self.visual.extract(images, query).to_dict()

    async def rag(self, query, location, run_id):
        self.agent.begin_request()
        self.agent.current_location = location or None
        events = await asyncio.wait_for(self.runner.run_debug(query, session_id=run_id),
                                        timeout=self.settings.timeout_seconds)
        texts = []
        for event in events or []:
            if getattr(event, "author", None) == "Rag_Agent":
                for part in getattr(getattr(event, "content", None), "parts", []) or []:
                    if getattr(part, "text", None):
                        texts.append(part.text)
        return self.agent.finalize_rag_result(agent_message=texts[-1] if texts else None).to_dict()

    def generate(self, query, images):
        from chat_models.Client import Client
        client = Client(model_name=self.settings.generation_model,
            openai_api_base=self.settings.generation_url, messages=[], max_retries=0,
            timeout=self.settings.timeout_seconds)
        try:
            return client.chat(prompt=query, images=list(images))
        finally:
            client.client.close()

    def close(self):
        if self.agent is not None:
            self.agent.client.close()
        if hasattr(self, "visual"):
            self.visual.client.close()


class DemoRunner:
    def __init__(self, settings, database=None, pipeline_factory=Pipeline):
        self.settings = settings
        self.database = database or DatabaseManager(settings)
        self.pipeline_factory = pipeline_factory

    async def run(self, request: Query, images=(), *, run_id=None, preset=None, sink=None):
        from rag_agent.utils.observation import observe
        with observe(sink):
            return await self._run(request, images, run_id=run_id, preset=preset, sink=sink)

    async def _run(self, request, images, *, run_id, preset, sink):
        """Caller holds RunLock for the complete run, including database access."""
        if len(images) > 3:
            raise ValueError("At most three input images are supported")
        run_id = run_id or str(uuid.uuid4())
        preset = preset or request.configuration()
        if preset.snapshot() != request.configuration().snapshot():
            raise ValueError("Preset snapshot does not match request")
        result = {"run_id": run_id, "mode": "live", "status": "failed",
            "input": request.model_dump(), "config": preset.snapshot(),
            "models": {"rag": self.settings.rag_model, "generation": self.settings.generation_model},
            "runtime_collection": self.settings.runtime_collection,
            "runtime_before": None, "runtime_after": None, "runtime_delta": None,
            "answer": None, "sources": [], "original_query": request.question}
        pipeline = None
        stage = "initialization"
        def emit(kind, stage, payload=None, status="completed"):
            if sink is not None:
                sink.emit(kind, stage, payload, status)
        emit("run_started", "run", {"config": preset.snapshot(), "models": result["models"],
             "mode": "live", "runtime_collection": self.settings.runtime_collection}, "running")
        emit("query_received", "query", request.model_dump())
        try:
            self.database.ensure_runtime(preset.db_on)
            result["runtime_before"] = self.database.count()
            emit("runtime_count_updated", "database", {"before": result["runtime_before"],
                 "collection": self.settings.runtime_collection})
            pipeline = self.pipeline_factory(self.settings, preset)
            pipeline.initialize()
            original = request.prompt()
            stage = "visual_attributes"
            visual = {"status": "skipped", "attributes": "", "reason": "not_applicable"}
            if request.task_type == "identification" and images:
                emit("visual_attributes_started", stage, {"image_count": len(images)}, "running")
                visual = pipeline.extract(images, original)
                emit("visual_attributes_completed" if visual["status"] == "success" else
                     "visual_attributes_skipped", stage,
                     {key: value for key, value in visual.items() if key != "error"},
                     "completed" if visual["status"] == "success" else "skipped")
            elif request.task_type == "identification":
                visual["reason"] = "no_images"
            if not (request.task_type == "identification" and images):
                emit("visual_attributes_skipped", stage, visual, "skipped")
            result["visual_attributes"] = visual
            stage = "query_enrichment"
            if preset.crop_dict_on:
                emit("query_enrichment_started", stage, {"query": original}, "running")
                enriched = pipeline.enrich(original)
                emit("query_enrichment_completed", stage, {"query": enriched, "changed": enriched != original})
            else:
                enriched = original
                emit("query_enrichment_skipped", stage, {"reason": "disabled"}, "skipped")
            result["contextual_query"] = original
            result["enriched_query"] = enriched
            attributes = visual.get("attributes", "")
            # Identical retrieval-only annotation to the existing batch helper.
            retrieval_query = enriched if not attributes else (
                f"{enriched}\n\n[Visual observations for evidence retrieval only; "
                f"not verified identification]\n{attributes}\n[/Visual observations]")
            result["retrieval_query"] = retrieval_query
            emit("query_prepared", "query", {"contextual_query": original,
                 "enriched_query": enriched, "retrieval_query": retrieval_query})
            stage = "rag"
            rag = await pipeline.rag(retrieval_query, request.location, run_id)
            result["rag"] = rag
            if rag["status"] == "insufficient_evidence":
                result.update(status="insufficient_evidence", message=INSUFFICIENT_MESSAGE)
                emit("insufficient_evidence", "rag", {"message": INSUFFICIENT_MESSAGE})
                emit("generation_skipped", "generation", {"reason": "insufficient_evidence"}, "skipped")
            elif rag["status"] != "success":
                result.update(error={"stage": stage, "code": rag["status"],
                                     "message": "Retrieval did not produce a valid result; check server diagnostics."})
                emit("generation_skipped", "generation", {"reason": rag["status"]}, "skipped")
            else:
                stage = "generation"
                evidence = rag.get("evidence") or []
                context = "\n\n".join(str(chunk.get("text", "")).strip() for chunk in evidence if chunk.get("text"))
                if not context:
                    raise ValueError("Successful RAG result contained no evidence text")
                emit("generation_started", stage, {"model": self.settings.generation_model,
                     "image_count": len(images), "evidence_count": len(evidence)}, "running")
                answer = pipeline.generate(enriched + "\n\nadditional context:\n\n" + context, images)
                if not isinstance(answer, str) or not answer.strip():
                    raise ValueError("Generation returned an empty answer")
                result.update(status="completed", answer=answer, sources=evidence)
                emit("generation_completed", stage, {"answer": answer, "sources": evidence})
        except Exception as exc:
            LOG.exception("Demo run %s failed at %s", run_id, stage)
            result.update(status="failed", error={"stage": stage, "code": type(exc).__name__,
                "message": f"The {stage} stage failed. Check service readiness and server diagnostics, then retry."})
            emit("stage_failed", stage, result["error"], "failed")
        finally:
            try:
                if result["runtime_before"] is not None:
                    result["runtime_after"] = self.database.count()
                    result["runtime_delta"] = result["runtime_after"] - result["runtime_before"]
                    emit("runtime_count_updated", "database", {"collection": self.settings.runtime_collection,
                         "before": result["runtime_before"], "after": result["runtime_after"], "delta": result["runtime_delta"]})
            except Exception:
                LOG.exception("Final demo runtime count unavailable for %s", run_id)
                result["runtime_count_error"] = "Final count unavailable"
            if pipeline is not None:
                try:
                    pipeline.close()
                except Exception:
                    LOG.exception("Pipeline cleanup failed")
        if sink is not None:
            result["tool_activity"] = {stage_name: {"enabled": enabled,
                "invoked": stage_name in sink.invoked} for stage_name, enabled in {
                    "retrieval": True, "confidence": preset.confidence_on,
                    "web_search": preset.web_search_on, "ingestion": preset.ingestion_loop_on,
                    "keyword_extraction": preset.web_search_on}.items()}
            if "web_search" not in sink.invoked:
                emit("augmentation_skipped", "web_search", {
                    "reason": "not_invoked" if preset.web_search_on else "disabled"}, "skipped")
        emit("run_failed" if result["status"] == "failed" else "run_completed", "run",
             {"outcome": result["status"], "tool_activity": result.get("tool_activity", {}),
              "error": result.get("error")}, "failed" if result["status"] == "failed" else "completed")
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--question", required=True)
    run.add_argument("--task-type", choices=["management", "identification"], default="management")
    run.add_argument("--state", default="")
    run.add_argument("--county", default="")
    run.add_argument("--month-year")
    run.add_argument("--preset", default="ablation_8_full_domain_filtered")
    run.add_argument("--overrides", default="{}", help="JSON boolean feature overrides; see README")
    run.add_argument("--image", action="append", default=[])
    run.add_argument("--output", type=Path, required=True)
    sub.add_parser("status")
    sub.add_parser("init")
    clear = sub.add_parser("clear")
    clear.add_argument("--confirm", required=True, help="CLEAR <configured demo collection>")
    args = parser.parse_args()
    settings = Settings.from_env()
    database = DatabaseManager(settings)
    with RunLock(settings.data_dir), redirect_stdout(sys.stderr):
        if args.command == "status":
            output = database.status()
        elif args.command == "init":
            database.ensure_runtime()
            output = database.status()
        elif args.command == "clear":
            output = database.clear(settings.runtime_collection, args.confirm)
        else:
            from .assets import save_image, MAX_IMAGES
            if len(args.image) > MAX_IMAGES:
                parser.error("At most three images are supported")
            request = Query(question=args.question, task_type=args.task_type, state=args.state,
                county=args.county, month_year=args.month_year, preset_id=args.preset, overrides=json.loads(args.overrides))
            run_id = str(uuid.uuid4())
            images = []
            for index, path in enumerate(args.image):
                source = Path(path)
                with source.open("rb") as handle:
                    data = handle.read(settings.max_image_bytes + 1)
                images.append(save_image(data, source.name, mimetypes.guess_type(source.name)[0],
                    settings.data_dir / "runs" / run_id / f"image-{index}.jpg", settings.max_image_bytes))
            from .run_store import RunStore
            from .event_stream import EventSink
            store = RunStore(settings)
            store.recover_interrupted()
            preset = request.configuration()
            store.create(run_id, {"input": request.model_dump(), "config": preset.snapshot(),
                                 "mode": "live", "image_count": len(images)})
            output = asyncio.run(DemoRunner(settings, database).run(request, images, run_id=run_id,
                preset=preset, sink=EventSink(run_id, store)))
            store.finish(run_id, output)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(json.dumps(output, indent=2, ensure_ascii=False))
    if output.get("status") == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
