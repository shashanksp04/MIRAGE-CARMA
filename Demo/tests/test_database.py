from dataclasses import replace
from contextlib import closing
import warnings

import pytest
from qdrant_client import QdrantClient, models

from Demo.backend.configurations import Settings
from Demo.backend.database_manager import DatabaseManager


@pytest.fixture
def db():
    with closing(QdrantClient(":memory:")) as client:
        client.create_collection("mirage_base", vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE))
        client.create_collection("mirage_runtime_batch_20260101_000000", vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE))
        manager = DatabaseManager(Settings(), client)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            manager.ensure_runtime()
        yield manager


def put(db, name, point_id=1):
    db.client.upsert(name, [models.PointStruct(id=point_id, vector=[1.] * 768,
                                             payload={"text": "test evidence"})])


def test_persistence_and_clear_do_not_touch_base_or_batch(db):
    for name in ("mirage_base", "mirage_demo_runtime", "mirage_runtime_batch_20260101_000000"):
        put(db, name)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        db.ensure_runtime()
    assert db.count() == 1
    assert db.status()["base"]["read_only"]
    assert db.clear("mirage_demo_runtime", "CLEAR mirage_demo_runtime")["points"] == 0
    assert db.client.count("mirage_base").count == 1
    assert db.client.count("mirage_runtime_batch_20260101_000000").count == 1


def test_clear_rejects_other_names_and_incorrect_confirmation(db):
    put(db, "mirage_demo_runtime")
    for name, token in (("mirage_base", "CLEAR mirage_base"), ("mirage_demo_runtime", "yes")):
        with pytest.raises(ValueError):
            db.clear(name, token)
    assert db.count() == 1


def test_schema_mismatch_is_not_recreated(db):
    db.client.delete_collection("mirage_demo_runtime")
    db.client.create_collection("mirage_demo_runtime", vectors_config=models.VectorParams(size=8, distance=models.Distance.COSINE))
    with pytest.raises(ValueError, match="768"):
        db.ensure_runtime()
    assert db.client.get_collection("mirage_demo_runtime").config.params.vectors.size == 8


def test_alias_cannot_redirect_clear_to_base(db):
    db.client.delete_collection("mirage_demo_runtime")
    db.client.update_collection_aliases([models.CreateAliasOperation(create_alias=models.CreateAlias(
        collection_name="mirage_base", alias_name="mirage_demo_runtime"))])
    put(db, "mirage_base")
    with pytest.raises(ValueError, match="aliases"):
        db.clear("mirage_demo_runtime", "CLEAR mirage_demo_runtime")
    assert db.client.count("mirage_base").count == 1
