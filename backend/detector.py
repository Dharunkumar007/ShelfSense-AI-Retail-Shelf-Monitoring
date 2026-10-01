"""YOLOv8 detector integration for ShelfSense AI."""

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "best.pt"
PLANOGRAM_PATH = ROOT / "sample_data" / "planogram.json"


def yolo_model_available() -> bool:
    return MODEL_PATH.exists()


def _zone_for_box(box: list[float], zones: list[dict[str, Any]]) -> str:
    x1, y1, x2, y2 = box
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2

    for zone in zones:
        zx1, zy1, zx2, zy2 = zone["bbox"]
        if zx1 <= center_x <= zx2 and zy1 <= center_y <= zy2:
            return zone["id"]

    return "unknown"


def detect_products(image_bytes: bytes, content_type: str | None = None) -> list[dict[str, Any]]:
    """Run YOLOv8 detection and return percentage-based bounding boxes."""
    if not yolo_model_available():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    with PLANOGRAM_PATH.open("r", encoding="utf-8") as handle:
        zones = json.load(handle)["zones"]

    # Decode image directly from memory (fixes Windows file lock issues)
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        print("Failed to decode image bytes!")
        return []

    # Pass the numpy array directly to YOLO
    model = YOLO(str(MODEL_PATH))
    results = model.predict(source=img, conf=0.25, verbose=False)

    detections: list[dict[str, Any]] = []
    for result in results:
        height, width = result.orig_shape
        names = result.names
        for index, box in enumerate(result.boxes):
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            # Convert bounding boxes to percentages (0 to 100)
            pct_box = [
                round((x1 / width) * 100, 2),
                round((y1 / height) * 100, 2),
                round((x2 / width) * 100, 2),
                round((y2 / height) * 100, 2),
            ]
            class_id = int(box.cls[0].item())
            detections.append(
                {
                    "id": f"yolo-{index}",
                    "label": names.get(class_id, "product"),
                    "confidence": round(float(box.conf[0].item()), 2),
                    "bbox": pct_box,
                    "zone_id": _zone_for_box(pct_box, zones),
                }
            )

    return detections