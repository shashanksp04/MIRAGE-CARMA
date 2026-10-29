import json
import threading

from Demo.backend.schemas import Query
from Demo.tests.test_api import api, ApiPipeline, wait_done


def test_ui_assets_catalog_and_activity_are_served_from_the_same_backend(api):
    client, app = api
    response = client.get("/")
    assert response.status_code == 200
    assert "Follow the evidence." in response.text
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/assets/styles.css").headers["content-type"].startswith("text/css")
    assert client.get("/assets/../../backend/app.py").status_code == 404
    catalog = client.get("/api/examples").json()
    assert len(catalog["examples"]) == 3
    for example in catalog["examples"]:
        assert example["validated"] is False
        Query.model_validate(example["input"])
    assert client.get("/api/activity").json() == {"busy": False, "active_run_id": None}
    ApiPipeline.gate, ApiPipeline.entered = threading.Event(), threading.Event()
    run_id = client.post("/api/runs", json={"question": "Question"}).json()["run_id"]
    assert ApiPipeline.entered.wait(1)
    assert client.get("/api/activity").json() == {"busy": True, "active_run_id": run_id}
    ApiPipeline.gate.set()
    wait_done(client, run_id)
    assert client.get("/api/activity").json()["busy"] is False


def test_only_owned_normalized_images_can_be_previewed(api, tmp_path):
    client, app = api
    run_id = client.post("/api/runs", json={"question": "Question"}).json()["run_id"]
    wait_done(client, run_id)
    store = app.state.store
    with store.connect() as database:
        row = database.execute("SELECT metadata FROM runs WHERE id=?", (run_id,)).fetchone()
        metadata = json.loads(row[0])
        metadata["image_count"] = 1
        database.execute("UPDATE runs SET metadata=? WHERE id=?", (json.dumps(metadata), run_id))
    directory = app.state.manager.settings.data_dir / "runs" / run_id
    directory.mkdir(parents=True)
    outside = tmp_path / "private.jpg"
    outside.write_bytes(b"private data")
    (directory / "image-0.jpg").symlink_to(outside)
    assert client.get(f"/api/runs/{run_id}/images/0").status_code == 404
    assert client.get(f"/api/runs/{run_id}/images/-1").status_code == 404
    assert client.get(f"/api/runs/{run_id}/images/1").status_code == 404
