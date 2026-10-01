import io
import json
import os
import tempfile

import pytest
from PIL import Image

TEST_DIR = tempfile.TemporaryDirectory()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DIR.name}/test.db"

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, insert, select
from backend import main
from backend.detector import Tuning, _zone_for_box, prepare_image
from backend.security import hash_password
from backend.storage import engine, events, metadata, scans, settings, tasks, users

LAYOUT = {"zones": [
    {"id": "left", "name": "Left", "bbox": [0, 0, 50, 100], "expected_count": 4, "critical_threshold": 25, "low_threshold": 75},
    {"id": "right", "name": "Right", "bbox": [50, 0, 100, 100], "expected_count": 4, "critical_threshold": 25, "low_threshold": 75}]}


def raw_image(color="white"):
    out = io.BytesIO()
    Image.new("RGB", (120, 80), color).save(out, "PNG")
    return out.getvalue()


def boxes(left=2, right=0, unknown=0):
    return [{"id": str(i), "label": "item", "confidence": .8, "bbox": [1, 1, 5, 5], "zone_id": zone}
            for i, zone in enumerate(["left"]*left+["right"]*right+["unknown"]*unknown)]


@pytest.fixture
def client(monkeypatch):
    with TestClient(main.app) as client:
        with engine.begin() as conn:
            for table in reversed(metadata.sorted_tables):
                conn.execute(delete(table))
            conn.execute(insert(settings).values(key="planogram", value=json.dumps(LAYOUT)))
        monkeypatch.setattr(main, "infer", lambda *a: (boxes(), False, "model-test"))
        main.LOGIN_ATTEMPTS.clear()
        yield client


def upload(client, color="white", **data):
    return client.post("/api/analyze", files={"file": ("shelf.png", raw_image(color), "image/png")}, data=data)


def test_overstock_cannot_hide_empty_neighbor():
    a = main.analyze_detections(boxes(10, 0, 3), LAYOUT)
    assert a["occupancy"] == 50
    assert a["missing_items"] == 4
    assert a["detected_items"] == 13 and a["unassigned_items"] == 3
    assert a["trend"] == [100, 0] and a["status"] == "Critical"


def test_boundary_and_overlap_assignment():
    assert _zone_for_box([49, 0, 51, 2], LAYOUT["zones"]) == "left"
    assert _zone_for_box([101, 0, 105, 2], LAYOUT["zones"]) == "unknown"
    assert _zone_for_box([0, 0, 2, 2], [{**LAYOUT["zones"][0], "id": "small", "bbox": [0,0,5,5]}, *LAYOUT["zones"]]) == "small"


def test_scan_detail_dedup_and_tasks(client):
    first = upload(client).json()
    second = upload(client).json()
    assert first["id"] == second["id"] and second["duplicate"]
    assert len(client.get("/api/history").json()["history"]) == 1
    assert client.get(f"/api/scans/{first['id']}").json()["trend"] == [50, 0]
    assert client.get(first["image"]).headers["content-type"] == "image/jpeg"
    assert len(client.get("/api/tasks").json()["tasks"]) == 2


def test_task_lifecycle_auto_resolution_and_audit(client, monkeypatch):
    upload(client)
    task = client.get("/api/tasks").json()["tasks"][0]
    patch = {"state": "in_progress", "assignee": "Operator", "note": "Picking stock"}
    assert client.patch(f"/api/tasks/{task['id']}", json=patch).status_code == 200
    assert client.patch(f"/api/tasks/{task['id']}", json={**patch,"state":"resolved","note":""}).status_code == 422
    monkeypatch.setattr(main, "infer", lambda *a: (boxes(4,4), False, "model-test"))
    assert upload(client, "red").status_code == 200
    assert all(t["state"] == "resolved" for t in client.get("/api/tasks").json()["tasks"])
    assert any("healthy follow-up" in e["message"] for e in client.get("/api/events").json()["events"])


def test_live_alert_confirmation(client):
    assert upload(client, camera="browser").status_code == 200
    assert client.get("/api/tasks").json()["tasks"] == []
    assert upload(client, "red", camera="browser").status_code == 200
    assert len(client.get("/api/tasks").json()["tasks"]) == 2


def test_tuning_change_resets_live_confirmation(client):
    upload(client, camera="browser")
    upload(client, "red", camera="browser", tuning='{"confidence":0.5}')
    assert client.get("/api/tasks").json()["tasks"] == []


def test_invalid_images_and_settings(client):
    r = client.post("/api/analyze", files={"file":("bad.png",b"not image","image/png")})
    assert r.status_code == 422
    assert upload(client,tuning='{"confidence":9}').status_code == 422
    assert client.post("/api/analyze").status_code == 422
    assert client.get("/api/history?limit=1000").status_code == 422


def test_oversized_upload(client):
    r = client.post("/api/analyze", files={"file":("big.jpg",b"0"*(main.MAX_UPLOAD+1),"image/jpeg")})
    assert r.status_code == 413


def test_busy_scan_and_missing_model(client, monkeypatch):
    main.SCAN_LOCK.acquire()
    try:
        assert upload(client).status_code == 429
    finally:
        main.SCAN_LOCK.release()
    def missing(*args):
        raise FileNotFoundError("Missing model")
    monkeypatch.setattr(main,"infer",missing)
    assert upload(client).status_code == 503
    assert not main.SCAN_LOCK.locked()


def test_history_filters_pagination_and_analytics(client):
    upload(client)
    upload(client,"red")
    upload(client,"blue",camera="browser")
    data = client.get("/api/history?camera=upload&limit=1").json()
    assert len(data["history"]) == 1 and data["next"]
    assert len(client.get(f"/api/history?camera=upload&before={data['next']}").json()["history"]) == 1
    assert client.get("/api/history?search=absent").json()["history"] == []
    assert client.get("/api/analytics?camera=upload").json()["summary"]["count"] == 2


def test_layout_validation_saved_and_audited(client):
    bad = {"zones": [{**LAYOUT["zones"][0], "bbox":[50,0,0,100]}]}
    assert client.put("/api/planogram",json=bad).status_code == 422
    bad = {"zones": [LAYOUT["zones"][0], LAYOUT["zones"][0]]}
    assert client.put("/api/planogram",json=bad).status_code == 422
    good = {"zones": [{**LAYOUT["zones"][0], "expected_count": 15}]}
    assert client.put("/api/planogram",json=good).status_code == 200
    assert client.get("/api/planogram").json()["zones"][0]["expected_count"] == 15
    assert client.get("/api/events").json()["events"]


def test_roles_sessions_logout_and_no_default_password(client):
    with engine.begin() as conn:
        conn.execute(insert(users).values(username="viewer",password=hash_password("strong-password-123"),role="viewer"))
    assert client.get("/api/history").status_code == 401
    assert client.post("/api/login",json={"username":"viewer","password":"incorrect"}).status_code == 401
    r = client.post("/api/login",json={"username":"viewer","password":"strong-password-123"})
    assert r.status_code == 200 and "HttpOnly" in r.headers["set-cookie"]
    assert client.get("/api/history").status_code == 200
    assert upload(client).status_code == 403
    assert client.put("/api/planogram",json=LAYOUT).status_code == 403
    assert client.get("/api/reports.csv").status_code == 403
    client.post("/api/logout")
    assert client.get("/api/history").status_code == 401


def test_csrf_and_local_bootstrap_boundary(client):
    assert client.post("/api/logout",headers={"Origin":"https://untrusted.example"}).status_code == 403
    assert client.get("/api/me",headers={"Host":"public.example"}).status_code == 503
    assert client.get("/api/health").headers["cache-control"] == "no-store"


def test_csv_injection_and_invalid_camera(client):
    client.post("/api/analyze",files={"file":("=SUM(1).png",raw_image(),"image/png")})
    assert "'=SUM(1).png" in client.get("/api/reports.csv").text
    assert client.post("/api/cameras/unknown/scan",json={}).status_code == 404


def test_image_resize_and_quality():
    image,jpeg,quality = prepare_image(raw_image())
    assert image.shape == (80,120,3) and jpeg.startswith(b"\xff\xd8")
    assert quality["warnings"]


def test_removed_calibration_endpoint(client):
    assert client.post("/api/calibrate").status_code == 404


def test_frontend_cache_headers_and_versioned_assets(client):
    root = client.get("/")
    assert root.headers["cache-control"] == "no-store"
    assert 'styles.css?v=20261001-6' in root.text
    assert 'app.js?v=20261001-6' in root.text
    assert client.get("/sw.js").headers["cache-control"] == "no-store"
    assert "must-revalidate" in client.get("/static/styles.css?v=20261001-6").headers["cache-control"]
