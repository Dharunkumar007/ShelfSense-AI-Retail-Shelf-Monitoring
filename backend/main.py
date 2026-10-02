from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import secrets
import threading
import time
from collections import Counter, OrderedDict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse
from urllib.request import urlopen

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, func, insert, select, update
from starlette.concurrency import run_in_threadpool

from backend.detector import Tuning, infer, prepare_image, yolo_model_available
from backend.security import current_user, hash_password, require, verify_password
from backend.storage import engine, events, init_db, metadata, scans, sessions, settings, tasks, telemetry, users

ROOT = Path(__file__).resolve().parents[1]
MAX_UPLOAD = 12 * 1024 * 1024
SCAN_LOCK = threading.Lock()
LOGIN_LOCK = threading.Lock()
LOGIN_ATTEMPTS: OrderedDict = OrderedDict()


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="ShelfSense AI", version="2.0.0", lifespan=lifespan)


@app.middleware("http")
async def protect_origin(request, call_next):
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0].strip()
    if request.method in ("GET", "HEAD") and (os.environ.get("FORCE_HTTPS") == "1" or os.environ.get("VERCEL")) and forwarded_proto != "https":
        target = request.url.replace(scheme="https")
        return RedirectResponse(str(target), status_code=308)
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        trusted_origin = os.environ.get("SHELFSENSE_ORIGIN", "")
        if origin and origin != trusted_origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Cross-origin writes are not allowed."}, status_code=403)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    elif request.url.path in ("/", "/sw.js") or request.url.path.endswith(".html"):
        response.headers["Cache-Control"] = "no-store"
    elif request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=(), payment=(), usb=()"
    response.headers["Content-Security-Policy"] = ("default-src 'self'; script-src 'self' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; "
        "font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'")
    if forwarded_proto == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def load_planogram():
    with engine.connect() as conn:
        saved = conn.scalar(select(settings.c.value).where(settings.c.key == "planogram"))
    return json.loads(saved) if saved else json.loads((ROOT / "sample_data/planogram.json").read_text())


def baseline_id(planogram):
    return hashlib.sha256(json.dumps(planogram, sort_keys=True).encode()).hexdigest()


def analyze_detections(detections, planogram=None):
    planogram = planogram or load_planogram()
    counts = Counter(item["zone_id"] for item in detections)
    zones, alerts = [], []
    expected_total = matched = filled = 0
    for zone in planogram["zones"]:
        detected, expected = counts[zone["id"]], zone["expected_count"]
        occupancy = round(min(detected, expected) / expected * 100, 1)
        status = "Critical" if occupancy <= zone["critical_threshold"] else "Low Stock" if occupancy <= zone["low_threshold"] else "Full Stock"
        missing = max(0, expected - detected)
        zones.append({**zone, "detected_count": detected, "missing_count": missing, "occupancy": occupancy, "status": status})
        if status != "Full Stock":
            alerts.append({"zone_id": zone["id"], "zone_name": zone["name"], "status": status, "missing": missing})
        expected_total += expected
        matched += detected
        filled += min(detected, expected)
    occupancy = round(filled / expected_total * 100, 1) if expected_total else 0
    return {"occupancy": occupancy, "status": "Critical" if any(z["status"] == "Critical" for z in zones) else "Low" if alerts else "Healthy",
        "expected_items": expected_total, "detected_items": len(detections), "matched_items": matched,
        "unassigned_items": len(detections) - matched, "missing_items": expected_total - filled,
        "zones": zones, "alerts": sorted(alerts, key=lambda a: (a["status"] != "Critical", -a["missing"])),
        "detections": detections, "trend": [z["occupancy"] for z in zones], "trend_labels": [z["id"] for z in zones]}


def add_event(conn, task_id, actor, message):
    conn.execute(insert(events).values(task_id=task_id, actor=actor, message=message, created_at=int(time.time())))


def sync_tasks(conn, analysis, scan_id, camera, baseline, actor, confirmed=None):
    existing = conn.execute(select(tasks).where(tasks.c.camera == camera, tasks.c.state != "resolved")).mappings().all()
    active = {t["zone_id"]: t for t in existing if t["baseline"] == baseline}
    for old in existing:
        if old["baseline"] != baseline:
            conn.execute(update(tasks).where(tasks.c.id == old["id"]).values(state="resolved", updated_at=int(time.time())))
            add_event(conn, old["id"], actor, "Closed after layout change; not a confirmed restock.")
    for zone in analysis["zones"]:
        if confirmed is not None and zone["id"] not in confirmed:
            continue
        old = active.get(zone["id"])
        if zone["status"] == "Full Stock":
            if old:
                conn.execute(update(tasks).where(tasks.c.id == old["id"]).values(state="resolved", updated_at=int(time.time()), scan_id=scan_id))
                add_event(conn, old["id"], actor, "Resolved by a healthy follow-up scan.")
            continue
        values = dict(severity=zone["status"], missing=zone["missing_count"], scan_id=scan_id, updated_at=int(time.time()))
        if old:
            conn.execute(update(tasks).where(tasks.c.id == old["id"]).values(**values))
            if old["severity"] != zone["status"]:
                add_event(conn, old["id"], actor, f"Severity changed to {zone['status']}.")
        else:
            saved = conn.execute(insert(tasks).values(**values, camera=camera, zone_id=zone["id"], zone_name=zone["name"],
                state="open", assignee="", baseline=baseline, created_at=int(time.time())))
            add_event(conn, saved.inserted_primary_key[0], actor, "Restock requested by scan.")


def process_scan(raw, source, camera, tuning, actor):
    # Reject excess work instead of queueing decoded images in memory.
    if not SCAN_LOCK.acquire(blocking=False):
        raise HTTPException(429, "Another scan is running. Retry shortly.")
    try:
        start = time.perf_counter()
        image, jpeg, quality = prepare_image(raw)
        layout = load_planogram()
        baseline = baseline_id(layout)
        detections, cached, model_version = infer(image, layout["zones"], tuning)
        result = analyze_detections(detections, layout)
        result.update(quality=quality, tuning=tuning.model_dump(), camera=camera, baseline=baseline,
            model_version=model_version, mode="YOLO detection", cached=cached,
            inference_ms=round((time.perf_counter() - start) * 1000), source=source)
        if result["unassigned_items"]:
            quality["warnings"].append(f"{result['unassigned_items']} detections fall outside the configured zones.")
        if len(detections) >= tuning.max_detections:
            quality["warnings"].append("Detection limit reached. Increase the limit and rescan.")
        fingerprint = hashlib.sha256(raw + camera.encode() + baseline.encode() + tuning.model_dump_json().encode() + model_version.encode()).hexdigest()
        now = int(time.time())
        with engine.begin() as conn:
            duplicate = conn.execute(select(scans.c.id, scans.c.created_at).where(scans.c.fingerprint == fingerprint)).first()
            if duplicate:
                scan_id, created_at = duplicate
            else:
                created_at = now
                saved = conn.execute(insert(scans).values(created_at=now, camera=camera, baseline=baseline, source=source,
                    occupancy=result["occupancy"], status=result["status"], alerts=len(result["alerts"]),
                    result=json.dumps(result), image=jpeg, fingerprint=fingerprint))
                scan_id = saved.inserted_primary_key[0]
                confirmed = None
                if camera != "upload":
                    previous = conn.execute(select(scans.c.result).where(scans.c.camera == camera,
                        scans.c.baseline == baseline, scans.c.id < scan_id,
                        scans.c.created_at >= now-120).order_by(scans.c.id.desc()).limit(1)).scalar()
                    prior = json.loads(previous) if previous else {}
                    prior_status = {z["id"]: z["status"] for z in prior.get("zones", [])}
                    confirmed = {z["id"] for z in result["zones"] if prior_status.get(z["id"]) == z["status"]}
                    if prior.get("tuning") != result["tuning"] or prior.get("model_version") != model_version:
                        confirmed = set()
                    result["task_confirmation"] = "Two matching camera observations within 120 seconds"
                sync_tasks(conn, result, scan_id, camera, baseline, actor, confirmed)
        return {**result, "id": scan_id, "created_at": created_at, "image": f"/api/scans/{scan_id}/image", "duplicate": bool(duplicate)}
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(503, str(exc)) from exc
    finally:
        SCAN_LOCK.release()


@app.get("/")
def index():
    return FileResponse(ROOT / "static/index.html")


@app.get("/sw.js")
def service_worker():
    return FileResponse(ROOT / "static/sw.js", media_type="application/javascript")


@app.get("/robots.txt")
def robots(request: Request):
    origin = os.environ.get("SHELFSENSE_ORIGIN", str(request.base_url).rstrip("/"))
    return PlainTextResponse(f"User-agent: *\nAllow: /\nDisallow: /api/\nSitemap: {origin}/sitemap.xml\n")


@app.get("/sitemap.xml")
def sitemap(request: Request):
    origin = os.environ.get("SHELFSENSE_ORIGIN", str(request.base_url).rstrip("/"))
    pages = ["/", "/static/privacy.html", "/static/terms.html"]
    urls = "".join(f"<url><loc>{origin}{page}</loc></url>" for page in pages)
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>', media_type="application/xml")


@app.get("/api/health")
def health():
    return {"status": "ok", "model_available": yolo_model_available(), "storage": engine.dialect.name}


@app.get("/api/me")
def me(user=Depends(current_user)):
    return user


class Login(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)
    website: str = Field(default="", max_length=0)


@app.post("/api/login")
def login(data: Login, request: Request, response: Response):
    ip, now = request.client.host, int(time.time())
    with LOGIN_LOCK:
        attempts = [t for t in LOGIN_ATTEMPTS.pop(ip, []) if t > now - 300]
        LOGIN_ATTEMPTS[ip] = attempts
        while len(LOGIN_ATTEMPTS) > 1000:
            LOGIN_ATTEMPTS.popitem(last=False)
        if len(attempts) >= 10:
            raise HTTPException(429, "Too many attempts. Wait five minutes.")
        attempts.append(now)
    with engine.begin() as conn:
        user = conn.execute(select(users).where(users.c.username == data.username)).mappings().first()
        if not user or not verify_password(data.password, user["password"]):
            raise HTTPException(401, "Incorrect username or password.")
        token = secrets.token_urlsafe(32)
        conn.execute(delete(sessions).where(sessions.c.expires < now))
        conn.execute(insert(sessions).values(token=hashlib.sha256(token.encode()).hexdigest(), user_id=user["id"], expires=now+28800))
    secure_cookie = os.environ.get("COOKIE_SECURE") == "1" or request.headers.get("x-forwarded-proto") == "https" or request.url.scheme == "https"
    response.set_cookie("shelfsense_session", token, httponly=True, samesite="strict", max_age=28800,
                        secure=secure_cookie, path="/")
    return {"username": user["username"], "role": user["role"]}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get("shelfsense_session", "")
    with engine.begin() as conn:
        conn.execute(delete(sessions).where(sessions.c.token == hashlib.sha256(token.encode()).hexdigest()))
    response.delete_cookie("shelfsense_session")
    return {"ok": True}


class NewUser(Login):
    password: str = Field(min_length=12, max_length=256)
    role: Literal["admin", "manager", "staff", "viewer"] = "staff"


class TelemetryEvent(BaseModel):
    event: Literal["page_view", "scan_complete", "report_export"]
    page: Literal["dashboard", "monitor", "analysis", "alerts", "inventory", "reports", "admin", "system"]


@app.post("/api/telemetry", status_code=204)
def record_telemetry(data: TelemetryEvent, user=Depends(current_user)):
    with engine.begin() as conn:
        conn.execute(insert(telemetry).values(created_at=int(time.time()), event=data.event, page=data.page))
    return Response(status_code=204)


@app.get("/api/telemetry/summary")
def telemetry_summary(user=Depends(require("admin", "manager"))):
    cutoff = int(time.time()) - 30 * 86400
    with engine.connect() as conn:
        rows = conn.execute(select(telemetry.c.event, telemetry.c.page, func.count().label("count"))
            .where(telemetry.c.created_at >= cutoff).group_by(telemetry.c.event, telemetry.c.page)).mappings()
        return {"days": 30, "events": [dict(row) for row in rows]}


@app.post("/api/users")
def create_user(data: NewUser, user=Depends(require("admin"))):
    from sqlalchemy.exc import IntegrityError
    try:
        with engine.begin() as conn:
            conn.execute(insert(users).values(username=data.username, password=hash_password(data.password), role=data.role))
    except IntegrityError as exc:
        raise HTTPException(409, "Username already exists.") from exc
    return {"ok": True}


@app.get("/api/users")
def list_users(user=Depends(require("admin", "manager"))):
    with engine.connect() as conn:
        return {"users": [dict(r) for r in conn.execute(select(users.c.username, users.c.role)).mappings()]}


@app.get("/api/planogram")
def planogram(user=Depends(current_user)):
    return load_planogram()


class Zone(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    expected_count: int = Field(ge=1, le=10000)
    critical_threshold: float = Field(ge=0, le=100)
    low_threshold: float = Field(ge=0, le=100)
    bbox: list[float] = Field(min_length=4, max_length=4)
    sku: str = Field(default="", max_length=80)
    product: str = Field(default="Shelf item", max_length=160)

    @model_validator(mode="after")
    def validate_zone(self):
        a, b, c, d = self.bbox
        if not (0 <= a < c <= 100 and 0 <= b < d <= 100):
            raise ValueError("Zone bounds must stay within 0-100 with positive width and height.")
        if self.critical_threshold >= self.low_threshold:
            raise ValueError("Critical threshold must be lower than low-stock threshold.")
        return self


class Planogram(BaseModel):
    zones: list[Zone] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({z.id for z in self.zones}) != len(self.zones):
            raise ValueError("Zone IDs must be unique.")
        return self


@app.put("/api/planogram")
def save_planogram(data: Planogram, user=Depends(require("admin"))):
    with engine.begin() as conn:
        conn.execute(delete(settings).where(settings.c.key == "planogram"))
        conn.execute(insert(settings).values(key="planogram", value=data.model_dump_json()))
        add_event(conn, None, user["username"], "Updated inventory layout and thresholds.")
    return data.model_dump()


@app.post("/api/admin/reset")
def reset_data(user=Depends(require("admin"))):
    try:
        metadata.drop_all(bind=engine)
        metadata.create_all(bind=engine)
        return {"status": "success", "message": "Database and planogram wiped."}
    except Exception as exc:
        raise HTTPException(500, "Workspace reset failed.") from exc


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...), camera: str = Form("upload", max_length=80),
                  tuning: str = Form("{}", max_length=2000), user=Depends(require("admin", "manager", "staff"))):
    raw = await file.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "Image exceeds the 12 MB upload limit.")
    try:
        config = Tuning.model_validate_json(tuning)
    except ValueError as exc:
        raise HTTPException(422, "Invalid detection settings.") from exc
    return await run_in_threadpool(process_scan, raw, (file.filename or "capture")[:240], camera, config, user["username"])


def scan_filters(camera, days, status, search):
    conditions = [scans.c.created_at >= int(time.time()) - days*86400]
    if camera:
        conditions.append(scans.c.camera == camera)
    if status:
        conditions.append(scans.c.status == status)
    if search:
        conditions.append(scans.c.source.contains(search, autoescape=True))
    return conditions


@app.get("/api/history")
def history(camera: str = "", days: int = Query(30, ge=1, le=365), status: str = "", search: str = Query("", max_length=120),
            limit: int = Query(25, ge=1, le=100), before: int | None = None, user=Depends(current_user)):
    conditions = scan_filters(camera, days, status, search)
    if before:
        conditions.append(scans.c.id < before)
    with engine.connect() as conn:
        rows = conn.execute(select(scans.c.id, scans.c.created_at, scans.c.source, scans.c.camera, scans.c.baseline,
            scans.c.occupancy, scans.c.status, scans.c.alerts).where(*conditions).order_by(scans.c.id.desc()).limit(limit+1)).mappings().all()
    return {"history": [dict(r) for r in rows[:limit]], "next": rows[limit-1]["id"] if len(rows) > limit else None}


@app.get("/api/scans/{scan_id}")
def scan_detail(scan_id: int, user=Depends(current_user)):
    with engine.connect() as conn:
        row = conn.execute(select(scans.c.result, scans.c.created_at).where(scans.c.id == scan_id)).first()
    if not row:
        raise HTTPException(404, "Scan not found.")
    return {**json.loads(row.result), "id": scan_id, "created_at": row.created_at, "image": f"/api/scans/{scan_id}/image"}


@app.get("/api/scans/{scan_id}/image")
def scan_image(scan_id: int, user=Depends(current_user)):
    with engine.connect() as conn:
        image = conn.scalar(select(scans.c.image).where(scans.c.id == scan_id))
    if image is None:
        raise HTTPException(404, "Image not found.")
    return Response(image, media_type="image/jpeg")


@app.get("/api/analytics")
def analytics(camera: str = "upload", days: int = Query(7, ge=1, le=365), user=Depends(current_user)):
    conditions = scan_filters(camera, days, "", "")
    with engine.connect() as conn:
        aggregate = conn.execute(select(func.count(scans.c.id).label("count"), func.avg(scans.c.occupancy).label("average"),
            func.sum(scans.c.alerts).label("alerts")).where(*conditions)).mappings().one()
        points = conn.execute(select(scans.c.id, scans.c.created_at, scans.c.occupancy, scans.c.baseline, scans.c.status)
            .where(*conditions).order_by(scans.c.id.desc()).limit(100)).mappings().all()
        summary = conn.execute(select(tasks.c.state, func.count().label("count")).where(tasks.c.camera == camera).group_by(tasks.c.state)).mappings().all()
    return {"summary": dict(aggregate), "points": [dict(p) for p in reversed(points)], "tasks": [dict(t) for t in summary]}


@app.get("/api/tasks")
def task_list(camera: str = "", state: str = "", severity: str = "", user=Depends(current_user)):
    conditions = []
    if camera:
        conditions.append(tasks.c.camera == camera)
    if state:
        conditions.append(tasks.c.state == state)
    if severity:
        conditions.append(tasks.c.severity == severity)
    with engine.connect() as conn:
        rows = conn.execute(select(tasks).where(*conditions).order_by(tasks.c.updated_at.desc(), tasks.c.id.desc()).limit(200)).mappings()
        return {"tasks": [dict(r) for r in rows]}


class TaskUpdate(BaseModel):
    state: Literal["open", "acknowledged", "in_progress", "resolved"]
    assignee: str = Field(default="", max_length=80)
    note: str = Field(default="", max_length=500)


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: int, data: TaskUpdate, user=Depends(require("admin", "manager", "staff"))):
    with engine.begin() as conn:
        old = conn.execute(select(tasks).where(tasks.c.id == task_id)).mappings().first()
        if not old:
            raise HTTPException(404, "Task not found.")
        if data.state == "resolved" and not data.note.strip():
            raise HTTPException(422, "Add a completion note or verify with a fresh scan.")
        if user["role"] == "staff" and data.assignee not in ("", user["username"]):
            raise HTTPException(403, "Staff can assign tasks only to themselves.")
        conn.execute(update(tasks).where(tasks.c.id == task_id).values(state=data.state, assignee=data.assignee, updated_at=int(time.time())))
        add_event(conn, task_id, user["username"], f"{old['state']} -> {data.state}; assigned: {data.assignee or 'unassigned'}. {data.note}")
    return {"ok": True}


@app.get("/api/events")
def event_list(user=Depends(current_user)):
    with engine.connect() as conn:
        return {"events": [dict(r) for r in conn.execute(select(events).order_by(events.c.id.desc()).limit(100)).mappings()]}


@app.get("/api/reports.csv")
def export(camera: str = "", days: int = Query(30, ge=1, le=365), user=Depends(require("admin", "manager"))):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Scan", "Timestamp (UTC epoch)", "Source", "Camera", "Occupancy %", "Status", "Alerts"])
    with engine.connect() as conn:
        rows = conn.execute(select(scans.c.id, scans.c.created_at, scans.c.source, scans.c.camera, scans.c.occupancy,
            scans.c.status, scans.c.alerts).where(*scan_filters(camera, days, "", "")).order_by(scans.c.id.desc()).limit(10000))
        for row in rows:
            writer.writerow(["'"+v if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r")) else v for v in row])
    return Response(buffer.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=shelfsense-report.csv"})


def configured_cameras():
    return json.loads(os.environ.get("SHELFSENSE_CAMERAS", "{}"))


@app.get("/api/cameras")
def cameras(user=Depends(current_user)):
    with engine.connect() as conn:
        seen = list(conn.execute(select(scans.c.camera).distinct().limit(100)).scalars())
    return {"configured": list(configured_cameras()), "sources": sorted(set(seen + ["upload", "browser"] + list(configured_cameras())))}


@app.post("/api/cameras/{camera}/scan")
def camera_scan(camera: str, tuning: Tuning, user=Depends(require("admin", "manager", "staff"))):
    url = configured_cameras().get(camera)
    if not url or urlparse(url).scheme not in ("http", "https"):
        raise HTTPException(404, "Configure an HTTP JPEG snapshot camera on the server first.")
    try:
        with urlopen(url, timeout=5) as response:
            raw = response.read(MAX_UPLOAD+1)
        if len(raw) > MAX_UPLOAD:
            raise ValueError("Camera frame too large")
    except Exception as exc:
        raise HTTPException(502, "Camera snapshot unavailable. Check its connection.") from exc
    return process_scan(raw, camera, camera, tuning, user["username"])


app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.exception_handler(404)
async def custom_not_found(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Not found."}, status_code=404)
    return FileResponse(ROOT / "static/404.html", status_code=404)
