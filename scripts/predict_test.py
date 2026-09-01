from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description="Test a trained ShelfSense model on images.")
    parser.add_argument("--model", default="models/best.pt")
    parser.add_argument("--source", required=True, help="Image, folder, webcam index like 0, or video path.")
    parser.add_argument("--conf", type=float, default=0.25)
    args = parser.parse_args()

    model_path = Path(args.model).expanduser()
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    model = YOLO(str(model_path))
    results = model.predict(source=args.source, conf=args.conf, save=True)
    print(f"Saved predictions to: {results[0].save_dir}")


if __name__ == "__main__":
    main()
