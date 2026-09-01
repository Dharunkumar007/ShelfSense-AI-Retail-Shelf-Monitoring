"""YOLOv8 integration placeholder.

The current prototype uses deterministic mock detections in main.py so the full
project runs without a trained model. After training, place best.pt in models/
and move the inference code here.
"""

from pathlib import Path


MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "best.pt"


def yolo_model_available() -> bool:
    return MODEL_PATH.exists()
