from __future__ import annotations

import base64
import json
import os
import random
import sqlite3
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.detector import MODEL_PATH, detect_products, yolo_model_available


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "sample_data"
DB_PATH = Path("/tmp/shelfsense.db") if os.environ.get("VERCEL") else ROOT / "shelfsense.db"
PLANOGRAM_PATH = DATA_DIR / "planogram.json"

app = FastAPI(title="ShelfSense AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at INTEGER NOT NULL,
                source TEXT NOT NULL,
                occupancy REAL NOT NULL,
                status TEXT NOT NULL,
                alerts INTEGER NOT NULL
            )
            """
        )


def load_planogram() -> dict[str, Any]:
    with PLANOGRAM_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def generate_mock_detections(seed_value: int) -> list[dict[str, Any]]:
    rng = random.Random(seed_value)
    detections: list[dict[str, Any]] = []
    products = ["Product", "Stock Item", "Inventory"]

    for zone_index, zone in enumerate(load_planogram()["zones"]):
        expected = zone["expected_count"]
        present = max(0, expected - rng.randint(0, 4))
        x1, y1, x2, y2 = zone["bbox"]
        zone_width = x2 - x1
        zone_height = y2 - y1

        for item_index in range(present):
            col = item_index % max(1, expected)
            box_width = max(6, zone_width / max(expected, 1) * 0.72)
            left = x1 + (col + 0.14) * zone_width / max(expected, 1)
            top = y1 + rng.uniform(0.08, 0.22) * zone_height
            detections.append(
                {
                    "id": f"d{zone_index}-{item_index}",
                    "label": products[zone_index % len(products)],
                    "confidence": round(rng.uniform(0.72, 0.96), 2),
                    "bbox": [
                        round(left, 2),
                        round(top, 2),
                        round(min(left + box_width, x2 - 1), 2),
                        round(min(top + zone_height * 0.62, y2 - 1), 2),
                    ],
                    "zone_id": zone["id"],
                }
            )

    return detections


def analyze_detections(detections: list[dict[str, Any]]) -> dict[str, Any]:
    planogram = load_planogram()
    zones = []
    alerts = []
    total_expected = 0
    total_detected = 0

    for zone in planogram["zones"]:
        detected = sum(1 for item in detections if item["zone_id"] == zone["id"])
        expected = zone["expected_count"]
        total_expected += expected
        total_detected += detected
        occupancy = min(100.0, round((detected / expected) * 100, 1) if expected else 100)
        status = "Full Stock"

        if occupancy <= zone["critical_threshold"]:
            status = "Critical"
        elif occupancy <= zone["low_threshold"]:
            status = "Low Stock"

        zone_result = {
            **zone,
            "detected_count": detected,
            "missing_count": max(0, expected - detected),
            "occupancy": occupancy,
            "status": status,
        }
        zones.append(zone_result)

        if status != "Full Stock":
            alerts.append(
                {
                    "zone_id": zone["id"],
                    "zone_name": zone["name"],
                    "product": "Shelf Item",
                    "status": status,
                }
            )

    occupancy = min(100.0, round((total_detected / total_expected) * 100, 1) if total_expected else 0) 
    status = "Healthy"
    if occupancy < 50:
        status = "Critical"
    elif occupancy < 75:
        status = "Low"

    return {
        "occupancy": occupancy,
        "status": status,
        "expected_items": total_expected,
        "detected_items": total_detected,
        "zones": zones,
        "alerts": alerts,
        "detections": detections,
        "trend": [88, 82, 79, 84, 73, occupancy],
    }


def record_scan(source: str, analysis: dict[str, Any]) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO scans (created_at, source, occupancy, status, alerts) VALUES (?, ?, ?, ?, ?)",
            (int(time.time()), source, analysis["occupancy"], analysis["status"], len(analysis["alerts"])),
        )


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ShelfSense AI"}


@app.get("/api/planogram")
def planogram() -> dict[str, Any]:
    return load_planogram()


@app.get("/api/history")
def history() -> dict[str, Any]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, created_at, source, occupancy, status, alerts FROM scans ORDER BY id DESC LIMIT 10"
        ).fetchall()

    return {
        "history": [
            {
                "id": row[0],
                "created_at": row[1],
                "source": row[2],
                "occupancy": row[3],
                "status": row[4],
                "alerts": row[5],
            }
            for row in rows
        ]
    }


@app.post("/api/calibrate")
async def calibrate_planogram(file: UploadFile = File(...)) -> dict[str, Any]:
    import cv2
    import numpy as np
    from ultralytics import YOLO

    raw = await file.read()
    nparr = np.frombuffer(raw, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    model = YOLO(str(MODEL_PATH))
    results = model.predict(source=img, conf=0.25, verbose=False)
    boxes = results[0].boxes.xyxyn.tolist()

    if not boxes:
        return {"status": "error", "message": "No products detected"}

    centers = [(box[1] + box[3]) / 2 for box in boxes]
    boxes_with_centers = list(zip(boxes, centers))
    boxes_with_centers.sort(key=lambda item: item[1])

    rows = []
    current_row = [boxes_with_centers[0]]
    for index in range(1, len(boxes_with_centers)):
        if boxes_with_centers[index][1] - current_row[-1][1] > 0.06:
            rows.append(current_row)
            current_row = [boxes_with_centers[index]]
        else:
            current_row.append(boxes_with_centers[index])
    rows.append(current_row)

    zones = []
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for row_index, row in enumerate(rows):
        y1 = max(0, min(box[0][1] for box in row) * 100 - 2.0)
        y2 = min(100, max(box[0][3] for box in row) * 100 + 2.0)
        expected = int(len(row) * 1.1)
        half = max(1, expected // 2)
        letter = letters[row_index % 26]

        zones.append(
            {
                "id": f"{letter}1",
                "name": f"Shelf {row_index + 1} Left",
                "expected_count": half,
                "critical_threshold": 45,
                "low_threshold": 75,
                "bbox": [0, round(y1, 1), 50, round(y2, 1)],
            }
        )
        zones.append(
            {
                "id": f"{letter}2",
                "name": f"Shelf {row_index + 1} Right",
                "expected_count": half,
                "critical_threshold": 45,
                "low_threshold": 75,
                "bbox": [50, round(y1, 1), 100, round(y2, 1)],
            }
        )

    with PLANOGRAM_PATH.open("w", encoding="utf-8") as handle:
        json.dump({"zones": zones}, handle, indent=2)

    return {"status": "success", "zones_created": len(zones), "shelves": len(rows)}


@app.post("/api/analyze")
async def analyze(file: UploadFile | None = File(default=None)) -> dict[str, Any]:
    # If no file is provided, return an empty state safely
    if file is None:
        return {
            "occupancy": 0,
            "status": "Ready",
            "expected_items": 0,
            "detected_items": 0,
            "zones": [],
            "alerts": [],
            "detections": [],
            "trend": [0, 0, 0, 0, 0, 0],
            "image": None,
            "mode": "Waiting for input...",
        }

    raw = await file.read()
    image_data = f"data:{file.content_type};base64,{base64.b64encode(raw).decode('ascii')}"

    # Process real image
    detections = detect_products(raw, file.content_type)
    analysis = analyze_detections(detections)
    analysis["image"] = image_data
    analysis["mode"] = "YOLOv8 real model detection."

    record_scan(file.filename, analysis)
    return analysis


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
