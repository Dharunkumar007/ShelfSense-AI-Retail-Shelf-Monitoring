"""Bounded, serialized YOLO inference with recorded per-scan settings."""
from __future__ import annotations

import hashlib
import io
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "best.pt"
LOCK = threading.Lock()
_model = None
_signature = None
_model_digest = None
_cache: OrderedDict = OrderedDict()


class Tuning(BaseModel):
    confidence: float = Field(default=0.25, ge=0.05, le=0.95)
    iou: float = Field(default=0.7, ge=0.1, le=0.9)
    image_size: Literal[640, 960, 1280] = 640
    max_detections: int = Field(default=500, ge=10, le=1500)
    min_area: float = Field(default=0, ge=0, le=5)
    contrast: bool = False


def yolo_model_available():
    return MODEL_PATH.is_file()


def prepare_image(raw):
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.width * source.height > 24_000_000:
                raise ValueError("Image exceeds 24 megapixels. Resize it before uploading.")
            source = ImageOps.exif_transpose(source).convert("RGB")
            source.thumbnail((1920, 1920))
            image = cv2.cvtColor(np.asarray(source), cv2.COLOR_RGB2BGR)
            output = io.BytesIO()
            source.save(output, "JPEG", quality=88)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Upload a valid JPEG, PNG, or WebP image.") from exc
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    sharpness = round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 1)
    brightness = round(float(gray.mean()), 1)
    warnings = []
    if sharpness < 60:
        warnings.append("Image may be blurred; verify counts or recapture.")
    if brightness < 45 or brightness > 220:
        warnings.append("Exposure may affect detection; check lighting.")
    return image, output.getvalue(), {"sharpness": sharpness, "brightness": brightness,
        "warnings": warnings, "width": image.shape[1], "height": image.shape[0]}


def _zone_for_box(box, zones):
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    # Smallest enclosing zone wins when a legacy layout overlaps.
    candidates = [z for z in zones if z["bbox"][0] <= cx <= z["bbox"][2]
                  and z["bbox"][1] <= cy <= z["bbox"][3]]
    if not candidates:
        return "unknown"
    return min(candidates, key=lambda z: ((z["bbox"][2] - z["bbox"][0]) *
                                         (z["bbox"][3] - z["bbox"][1]), z["id"]))["id"]


def infer(image, zones, tuning):
    global _model, _signature, _model_digest
    if not yolo_model_available():
        raise FileNotFoundError("Trained model missing. Place best.pt in models/ and restart.")
    stat = MODEL_PATH.stat()
    signature = (stat.st_mtime_ns, stat.st_size)
    key = (hashlib.sha256(image.tobytes()).hexdigest(), tuning.model_dump_json(), signature)
    with LOCK:
        if _signature != signature:
            from ultralytics import YOLO
            _model = YOLO(str(MODEL_PATH))
            with MODEL_PATH.open("rb") as handle:
                digest = hashlib.sha256()
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            _model_digest = digest.hexdigest()
            _signature = signature
            _cache.clear()
        cached = key in _cache
        if cached:
            boxes = _cache.pop(key)
        else:
            feed = image
            if tuning.contrast:
                lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
                lab[:, :, 0] = cv2.createCLAHE(clipLimit=2, tileGridSize=(8, 8)).apply(lab[:, :, 0])
                feed = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            result = _model.predict(feed, conf=tuning.confidence, iou=tuning.iou,
                imgsz=tuning.image_size, max_det=tuning.max_detections, augment=False, verbose=False)[0]
            boxes = []
            for index, row in enumerate(result.boxes.data.cpu().tolist()):
                x1, y1, x2, y2, confidence, cls = row[:6]
                h, w = image.shape[:2]
                bbox = [round(x1/w*100, 3), round(y1/h*100, 3), round(x2/w*100, 3), round(y2/h*100, 3)]
                if (bbox[2]-bbox[0]) * (bbox[3]-bbox[1]) / 100 < tuning.min_area:
                    continue
                boxes.append({"id": f"yolo-{index}", "label": result.names[int(cls)],
                              "confidence": round(confidence, 4), "bbox": bbox})
        _cache[key] = boxes
        while len(_cache) > 8:
            _cache.popitem(last=False)
        return [{**b, "zone_id": _zone_for_box(b["bbox"], zones)} for b in boxes], cached, _model_digest
