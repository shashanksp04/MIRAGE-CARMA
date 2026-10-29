"""Conference backend and demo UI. Run with one uvicorn worker."""
import asyncio
from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
import shutil
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .assets import MAX_IMAGES, save_image
from .configurations import DEFAULT_PRESET, Settings, get_preset, presets, FEATURES, workflow_profiles
from .database_manager import DatabaseManager
from .demo_runner import DemoRunner
from .event_stream import sse
from .health import Health
from .locking import BusyError, RunLock
from .run_manager import RunManager
from .run_store import RunStore, TERMINAL
from .schemas import ReplayRequest, ClearRequest, Query


class BodyLimitMiddleware:
    """Limit streamed bodies too, before multipart parsing creates spool files."""
    def __init__(self, app, max_bytes):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        received = 0
        async def limited_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > self.max_bytes:
                raise HTTPException(413, "Request body exceeds image upload limit")
            return message
        await self.app(scope, limited_receive, send)


def create_app(settings=None, *, database=None, runner=None, health=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        # One API process per data directory; RunLock also excludes live CLI work.
        server_lock = RunLock(settings.data_dir)
        server_lock.path = settings.data_dir / "server.lock"
        server_lock.acquire()
        handler = None
        manager = None
        db = None
        try:
            handler = RotatingFileHandler(settings.data_dir / "diagnostics.log", maxBytes=2_000_000, backupCount=3)
            logging.getLogger("Demo").addHandler(handler)
            db = database or DatabaseManager(settings)
            store = RunStore(settings)
            manager = RunManager(settings, store, runner or DemoRunner(settings, db))
            # Protect startup schema/index creation and interrupted-run recovery.
            try:
                with manager.lock:
                    store.recover_interrupted()
                    try:
                        db.ensure_runtime(use_base=False)
                    except Exception:
                        logging.getLogger(__name__).exception("Runtime initialization unavailable; health will report failure")
            except BusyError:
                pass  # A CLI query owns the collection; API remains read-only/busy.
            app.state.store, app.state.manager = store, manager
            app.state.database = db
            app.state.health = health or Health(settings, db)
            yield
        finally:
            if manager:
                await asyncio.to_thread(manager.close)
            if db is not None and hasattr(db, "close"):
                db.close()
            if handler:
                logging.getLogger("Demo").removeHandler(handler)
                handler.close()
            server_lock.release()

    app = FastAPI(title="MIRAGE-CARMA Demo API", version="1.0", lifespan=lifespan)
    app.add_middleware(BodyLimitMiddleware, max_bytes=MAX_IMAGES * settings.max_image_bytes + 64 * 1024)
    frontend = Path(__file__).resolve().parents[1] / "frontend"
    app.mount("/assets", StaticFiles(directory=frontend), name="frontend")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(frontend / "index.html", headers={"Cache-Control": "no-cache"})

    @app.exception_handler(BusyError)
    async def busy_handler(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    def get_run(run_id):
        try:
            return app.state.store.get(run_id)
        except KeyError:
            raise HTTPException(404, "Run not found or expired by retention") from None

    @app.post("/api/replays", status_code=201)
    def create_replay(body: ReplayRequest):
        from .replay_manager import recording
        try:
            run = recording(app.state.store, body.run_id)
        except KeyError:
            raise HTTPException(404, "Recording not found or expired") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        return {"replay_id": body.run_id, "source_run_id": body.run_id, "mode": "replay",
                "events_truncated": run["events_truncated"],
                "events_url": f"/api/replays/{body.run_id}/events",
                "provenance": {"recorded_at": run["created_at"],
                    "source_mode": run["metadata"].get("mode", "unknown")},
                "pacing": "250 ms per recorded event at 1x; original timestamps preserved"}

    @app.get("/api/replays/{replay_id}/events")
    async def replay_events(replay_id: str, request: Request, after: int = 0, speed: float = 1):
        from .replay_manager import recording, events
        get_run(replay_id)
        try:
            run = recording(app.state.store, replay_id)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        cursor = request.headers.get("last-event-id")
        if cursor:
            if ":" in cursor:
                owner, cursor = cursor.rsplit(":", 1)
                if owner != replay_id:
                    raise HTTPException(422, "Last-Event-ID belongs to another recording")
            try:
                after = int(cursor)
            except ValueError:
                raise HTTPException(422, "Invalid replay event cursor") from None
        if not .25 <= speed <= 8 or after < 0 or after > run["last_sequence"]:
            raise HTTPException(422, "Invalid replay speed or sequence cursor")
        return StreamingResponse(events(app.state.store, replay_id, request, after, speed),
            media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @app.get("/api/examples")
    def example_catalog():
        return json.loads((Path(__file__).resolve().parents[1] / "examples/catalog.json").read_text())

    @app.get("/api/activity")
    def activity():
        try:
            with app.state.manager.lock:
                busy = False
        except BusyError:
            busy = True
        active = next((run["run_id"] for run in app.state.store.recent(settings.max_runs)
                       if run["status"] == "running"), None) if busy else None
        return {"busy": busy, "active_run_id": active}

    @app.get("/api/runs/{run_id}/images/{image_index}")
    def run_image(run_id: str, image_index: int):
        run = get_run(run_id)
        if not 0 <= image_index < run["metadata"].get("image_count", 0):
            raise HTTPException(404, "Image not found")
        root = (settings.data_dir / "runs").resolve()
        directory = (root / run_id).resolve()
        image = (directory / f"image-{image_index}.jpg").resolve()
        if directory.parent != root or image.parent != directory or not image.is_file():
            raise HTTPException(404, "Image not found")
        return FileResponse(image, media_type="image/jpeg",
                            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    @app.get("/api/configurations")
    def configurations():
        return {"api_version": 1, "default": DEFAULT_PRESET, "presets": [p.snapshot() for p in presets().values()],
                "custom_overrides_supported": True, "override_fields": FEATURES,
                "workflow_profiles": workflow_profiles(), "visual_extraction": "always_on_for_identification_images",
                "runtime_note": "Accumulated runtime evidence is shared; runs are not controlled ablation comparisons."}

    @app.get("/api/health")
    def readiness(preset_id: str = DEFAULT_PRESET):
        try:
            return app.state.health.check(preset_id)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.post("/api/configurations/resolve")
    def resolve_configuration(query: Query):
        return {"config": query.configuration().snapshot()}

    @app.post("/api/health")
    def configured_readiness(query: Query):
        return app.state.health.check(query.configuration())

    @app.get("/api/database/status")
    def database_status():
        return app.state.database.status()

    @app.post("/api/database/runtime/clear")
    def clear_runtime(body: ClearRequest):
        with app.state.manager.lock:
            try:
                return app.state.database.clear(body.collection, body.confirmation)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            except Exception:
                logging.getLogger(__name__).exception("Runtime clear failed")
                raise HTTPException(503, "Runtime clear failed; check Qdrant readiness") from None

    @app.post("/api/runs", status_code=202)
    async def submit(request: Request):
        manager = app.state.manager
        manager.lock.acquire()
        handed_off = False
        run_id = str(uuid.uuid4())
        directory = settings.data_dir / "runs" / run_id
        form = None
        try:
            content_type = request.headers.get("content-type", "").split(";")[0]
            uploads = []
            if content_type == "application/json":
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 32 * 1024:
                        raise HTTPException(413, "Query JSON exceeds 32 KiB")
                query = Query.model_validate_json(bytes(body))
            elif content_type == "multipart/form-data":
                form = await request.form(max_files=MAX_IMAGES, max_fields=1, max_part_size=32 * 1024)
                if set(form.keys()) - {"request", "images"} or len(form.getlist("request")) != 1:
                    raise HTTPException(422, "Supply one request JSON field and up to three images fields")
                query = Query.model_validate_json(form["request"])
                uploads = form.getlist("images")
            else:
                raise HTTPException(415, "Use application/json or multipart/form-data")
            if len(uploads) > MAX_IMAGES:
                raise HTTPException(422, "At most three images are supported")
            images = []
            for index, upload in enumerate(uploads):
                if not hasattr(upload, "read"):
                    raise HTTPException(422, "images fields must contain files")
                data = await upload.read(settings.max_image_bytes + 1)
                images.append(await asyncio.to_thread(save_image, data, upload.filename or "",
                    upload.content_type, directory / f"image-{index}.jpg", settings.max_image_bytes))
            readiness = await asyncio.to_thread(app.state.health.check, query.configuration())
            if not readiness["ready"]:
                raise HTTPException(503, {"message": "Demo services are not ready", "readiness": readiness})
            preset = query.configuration()
            manager.start_reserved(run_id, query, tuple(images), preset)
            handed_off = True
            return {"run_id": run_id, "status": "running", "events_url": f"/api/runs/{run_id}/events"}
        except ValidationError as exc:
            raise HTTPException(422, [{"loc": error["loc"], "msg": error["msg"]}
                                      for error in exc.errors()]) from None
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, str(exc)) from None
        finally:
            if form is not None:
                await form.close()
            if not handed_off:
                shutil.rmtree(directory, ignore_errors=True)
                manager.lock.release()

    @app.get("/api/runs")
    def recent_runs(limit: int = 20, offset: int = 0):
        if not 1 <= limit <= 100 or offset < 0:
            raise HTTPException(422, "Use limit 1–100 and a nonnegative offset")
        return {"runs": app.state.store.recent(limit, offset)}

    @app.get("/api/runs/{run_id}")
    def run_status(run_id: str):
        return get_run(run_id)

    @app.get("/api/runs/{run_id}/events")
    async def events(run_id: str, request: Request, after: int = 0):
        run = get_run(run_id)
        cursor = request.headers.get("last-event-id")
        if cursor:
            if ":" in cursor:
                cursor_run, cursor = cursor.rsplit(":", 1)
                if cursor_run != run_id:
                    raise HTTPException(422, "Last-Event-ID belongs to another run")
            try:
                after = int(cursor)
            except ValueError:
                raise HTTPException(422, "Last-Event-ID must contain an event sequence") from None
        if after < 0 or after > run["last_sequence"]:
            raise HTTPException(422, "Event cursor is outside the recorded sequence")

        async def stream():
            sequence = after
            idle = 0
            while not await request.is_disconnected():
                try:
                    current = await asyncio.to_thread(app.state.store.get, run_id)
                except KeyError:
                    yield "event: history_expired\ndata: {}\n\n"
                    return
                batch = await asyncio.to_thread(app.state.store.events, run_id, sequence)
                for event in batch:
                    sequence = event["sequence"]
                    yield sse(event)
                if current["status"] in TERMINAL and sequence >= current["last_sequence"]:
                    return
                if not batch:
                    idle += 1
                    if idle % 40 == 0:
                        yield ": keep-alive\n\n"
                    await asyncio.sleep(.25)
        return StreamingResponse(stream(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    return app
