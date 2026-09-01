from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(description="Train ShelfSense YOLOv8 model.")
    parser.add_argument("--data", default="training_data/SKU110K_YOLO/data.yaml")
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--name", default="shelfsense_yolov8n")
    args = parser.parse_args()

    model = YOLO(args.model)
    model.train(
        data=str(Path(args.data).expanduser().resolve()),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        name=args.name,
    )

    print("Training complete.")
    print(f"Best model: runs/detect/{args.name}/weights/best.pt")


if __name__ == "__main__":
    main()
