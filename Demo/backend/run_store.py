"""Small durable run index and ordered append-only event records."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3

from .event_stream import Event, bounded

TERMINAL = {"completed", "insufficient_evidence", "failed"}


class RunStore:
    def __init__(self, settings):
        self.settings = settings
        self.path = settings.data_dir / "runs.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                PRAGMA journal_size_limit=8388608;
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, created TEXT NOT NULL, status TEXT NOT NULL,
                    metadata TEXT NOT NULL, result TEXT, truncated INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS events (
                    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                    sequence INTEGER NOT NULL, event TEXT NOT NULL,
                    PRIMARY KEY(run_id, sequence));
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def create(self, run_id, metadata):
        with self.connect() as db:
            db.execute("INSERT INTO runs(id,created,status,metadata) VALUES (?,?,?,?)",
                       (run_id, datetime.now(timezone.utc).isoformat(), "running", json.dumps(bounded(metadata))))
        self.prune()

    def append(self, run_id, fields):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status,truncated FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            if row["status"] in TERMINAL:
                raise ValueError("Cannot append to a terminal run")
            sequence = db.execute("SELECT COALESCE(MAX(sequence),0)+1 FROM events WHERE run_id=?", (run_id,)).fetchone()[0]
            terminal = fields["type"] in {"run_completed", "run_failed"}
            if sequence >= self.settings.max_events - 1 and not terminal:
                if row["truncated"]:
                    return None
                fields = {**fields, "type": "recording_limit_reached", "stage": "run",
                          "status": "completed", "payload": {"message": "Further stage events omitted by retention limit"}}
                db.execute("UPDATE runs SET truncated=1 WHERE id=?", (run_id,))
            if sequence > self.settings.max_events:
                return None
            event = Event(run_id=run_id, sequence=sequence, **fields).model_dump()
            db.execute("INSERT INTO events VALUES(?,?,?)", (run_id, sequence, json.dumps(event)))
            return event

    def finish(self, run_id, result):
        if result["status"] not in TERMINAL:
            raise ValueError("Invalid terminal outcome")
        # The result must retain its top-level status even if evidence is large.
        result = bounded(result, limit=240000)
        with self.connect() as db:
            db.execute("UPDATE runs SET status=?,result=? WHERE id=?",
                       (result["status"], json.dumps(result), run_id))

    def get(self, run_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            last = db.execute("SELECT COALESCE(MAX(sequence),0) FROM events WHERE run_id=?", (run_id,)).fetchone()[0]
        return {"run_id": row["id"], "created_at": row["created"], "status": row["status"],
                "metadata": json.loads(row["metadata"]), "result": json.loads(row["result"]) if row["result"] else None,
                "last_sequence": last, "events_truncated": bool(row["truncated"])}

    def events(self, run_id, after=0, limit=100):
        with self.connect() as db:
            rows = db.execute("SELECT event FROM events WHERE run_id=? AND sequence>? ORDER BY sequence LIMIT ?",
                              (run_id, after, limit)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def recent(self, limit=20, offset=0):
        with self.connect() as db:
            rows = db.execute("SELECT id,created,status,metadata FROM runs ORDER BY created DESC LIMIT ? OFFSET ?",
                              (limit, offset)).fetchall()
        return [{"run_id": row["id"], "created_at": row["created"], "status": row["status"],
                 "metadata": json.loads(row["metadata"])} for row in rows]

    def prune(self):
        with self.connect() as db:
            rows = db.execute("SELECT id FROM runs ORDER BY created DESC LIMIT -1 OFFSET ?",
                              (self.settings.max_runs,)).fetchall()
            removed = []
            for row in rows:
                cursor = db.execute("DELETE FROM runs WHERE id=? AND status!='running'", (row[0],))
                if cursor.rowcount:
                    removed.append(row[0])
        for run_id in removed:
            shutil.rmtree(self.settings.data_dir / "runs" / run_id, ignore_errors=True)

    def recover_interrupted(self):
        """Call only after owning the process/run lock, never while a CLI runs."""
        with self.connect() as db:
            ids = [row[0] for row in db.execute("SELECT id FROM runs WHERE status='running'")]
        for run_id in ids:
            fields = {"timestamp": datetime.now(timezone.utc).isoformat(), "type": "run_failed",
                      "stage": "run", "iteration": 0, "status": "failed", "visibility": "primary",
                      "payload": {"code": "process_interrupted"}}
            self.append(run_id, fields)
            self.finish(run_id, {"status": "failed", "answer": None,
                                "error": {"code": "process_interrupted", "message": "Backend stopped during this run"}})
