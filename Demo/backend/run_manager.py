import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

from .event_stream import EventSink
from .locking import RunLock

LOG = logging.getLogger(__name__)


class RunManager:
    def __init__(self, settings, store, runner):
        self.settings, self.store, self.runner = settings, store, runner
        self.lock = RunLock(settings.data_dir)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="demo-query")

    def start_reserved(self, run_id, query, images, preset):
        """API already holds the lock while validating inputs and readiness."""
        self.store.create(run_id, {"input": query.model_dump(), "config": preset.snapshot(),
                                  "mode": "live", "image_count": len(images),
                                  "runtime_collection": self.settings.runtime_collection,
                                  "models": {"rag": self.settings.rag_model,
                                             "generation": self.settings.generation_model}})
        return self.executor.submit(self._execute, run_id, query, images, preset)

    def _execute(self, run_id, query, images, preset):
        sink = EventSink(run_id, self.store)
        try:
            result = asyncio.run(self.runner.run(query, images, run_id=run_id, preset=preset, sink=sink))
            self.store.finish(run_id, result)
        except BaseException as exc:
            LOG.exception("Demo worker failed for run %s", run_id)
            result = {"status": "failed", "answer": None, "error": {
                "code": type(exc).__name__, "message": "Run worker failed; check server diagnostics"}}
            try:
                sink.emit("run_failed", "run", result["error"], "failed")
                self.store.finish(run_id, result)
            except Exception:
                LOG.exception("Unable to persist worker failure")
        finally:
            self.lock.release()

    def close(self):
        # Do not release the lock while a non-cancellable synchronous tool is
        # still writing. Server shutdown waits for the one active query.
        self.executor.shutdown(wait=True)
