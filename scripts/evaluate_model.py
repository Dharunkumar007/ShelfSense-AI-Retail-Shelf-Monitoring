"""Measure threshold candidates on labelled validation data, never on the test set."""
import argparse
import csv
from pathlib import Path
from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True)
    parser.add_argument("--model", default="models/best.pt")
    parser.add_argument("--conf", nargs="+", type=float, default=[0.15, 0.25, 0.4])
    parser.add_argument("--iou", nargs="+", type=float, default=[0.5, 0.7])
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--split", choices=["val", "test"], default="val")
    args = parser.parse_args()
    if any(not 0 < v < 1 for v in args.conf + args.iou):
        parser.error("Confidence and IoU must be between zero and one")
    model = YOLO(args.model)
    output = Path("validation_results")
    output.mkdir(exist_ok=True)
    with (output / f"thresholds-{args.split}.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["confidence", "iou", "precision", "recall", "mAP50", "mAP50-95", "inference_ms"])
        for confidence in args.conf:
            for iou in args.iou:
                metrics = model.val(data=args.data, split=args.split, conf=confidence, iou=iou,
                    imgsz=args.imgsz, max_det=500, batch=1, workers=0, plots=False,
                    project=str(output), name=f"{args.split}-{confidence}-{iou}")
                writer.writerow([confidence, iou, metrics.box.mp, metrics.box.mr, metrics.box.map50,
                                 metrics.box.map, metrics.speed["inference"]])
                handle.flush()
    print(f"Saved measurements to {output}. Select on validation data; confirm once on held-out test data.")


if __name__ == "__main__":
    main()
