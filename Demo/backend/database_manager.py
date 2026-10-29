"""Demo-only Qdrant lifecycle; never use the batch manager's cleanup."""
from datetime import datetime, timezone
import os

from .configurations import Settings


class DatabaseManager:
    def __init__(self, settings: Settings, client=None):
        self.settings = settings
        self._client = client

    @property
    def client(self):
        if self._client is None:
            from qdrant_client import QdrantClient
            self._client = QdrantClient(url=self.settings.qdrant_url,
                api_key=os.getenv("QDRANT_API_KEY") or None, timeout=10,
                check_compatibility=False)
        return self._client

    def verify(self, name):
        if any(alias.alias_name == name for alias in self.client.get_aliases().aliases):
            raise ValueError("Demo collection roles must name physical collections, not aliases")
        info = self.client.get_collection(name)
        vectors = info.config.params.vectors
        if isinstance(vectors, dict) or vectors.size != self.settings.vector_size or str(vectors.distance).lower() != "cosine":
            raise ValueError(f"Collection {name} must use unnamed 768-dimensional cosine vectors")
        return info

    def ensure_runtime(self, use_base=True):
        from qdrant_client.http.models import Distance, VectorParams
        if use_base:
            self.verify(self.settings.base_collection)
        name = self.settings.runtime_collection
        names = {c.name for c in self.client.get_collections().collections}
        if name not in names:
            self.client.create_collection(collection_name=name, vectors_config=VectorParams(
                size=self.settings.vector_size, distance=Distance.COSINE))
        info = self.verify(name)
        from rag_agent.utils.qdrant_store import PAYLOAD_INDEX_FIELDS
        for field in PAYLOAD_INDEX_FIELDS:
            if field not in (info.payload_schema or {}):
                self.client.create_payload_index(collection_name=name, field_name=field, field_schema="keyword")
        return name

    def count(self):
        return self.client.count(collection_name=self.settings.runtime_collection, exact=True).count

    def close(self):
        if self._client is not None:
            self._client.close()

    def status(self):
        statuses = {}
        for role, name in (("base", self.settings.base_collection), ("runtime", self.settings.runtime_collection)):
            item = {"name": name, "read_only": role == "base", "reachable": False,
                    "compatible": False, "points": None, "checked_at": datetime.now(timezone.utc).isoformat()}
            try:
                self.client.get_collection(name)
                item["reachable"] = True
                self.verify(name)
                item["compatible"] = True
                item["points"] = self.client.count(collection_name=name, exact=True).count
            except Exception as exc:
                # No raw URLs, credentials, or tracebacks in public status.
                item["error"] = "Collection unavailable or incompatible; check server configuration"
                item["error_type"] = type(exc).__name__
            statuses[role] = item
        return statuses

    def clear(self, collection, confirmation):
        name = self.settings.runtime_collection
        if collection != name or confirmation != f"CLEAR {name}":
            raise ValueError("Confirmation must match the configured demo runtime collection")
        # Settings enforces the demo-only name allowlist. Caller must hold RunLock.
        from qdrant_client.http.models import Filter, FilterSelector
        self.verify(name)
        self.client.delete(collection_name=name, points_selector=FilterSelector(filter=Filter()), wait=True)
        self.verify(name)
        return {"collection": name, "points": self.count()}
