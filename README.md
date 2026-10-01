# ShelfSense AI

AI-powered retail shelf monitoring system using a YOLOv8-ready detection workflow, shelf planogram comparison, occupancy scoring, alerts, analytics, and an app-style live monitor.

**New computer? Start with [Setup and Launch](docs/SETUP_AND_LAUNCH.md).** It includes Windows and Ubuntu commands, downloads, a smaller CPU-only install, administrator setup, and troubleshooting. The trained `models/best.pt` is included; a dataset download is only needed for training.

## Project Modules

- Product Detection Engine: accepts shelf images and returns product bounding boxes.
- Shelf Stock Analyzer: compares detections with expected planogram zones.
- Alert System: creates low-stock and critical restock alerts.
- Analytics Dashboard: shows occupancy scores, trends, and zone status.
- Inventory and Admin Panel: manages products, zones, and thresholds.

## Run Locally

```bash
cd /home/ron/dharun
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

## Deploy

Deployment requires persistent storage and a host that can run the YOLO dependencies. See [deployment instructions](docs/DEPLOYMENT.md) and [operations setup](docs/OPERATIONS.md) before publishing.

## Current Prototype

The app requires a trained model; missing weights return an explicit error. After training, place the model at:

```text
models/best.pt
```

The runtime packages are included in `requirements.txt`. Run the app:

```bash
.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Uploaded images will use the real YOLOv8 model automatically.

## Train YOLOv8

Training instructions for another laptop are in:

```text
docs/TRAINING_ON_FRIEND_LAPTOP.md
```

Short version:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-training.txt
.venv/bin/python scripts/prepare_sku110k_yolo.py --dataset-root "/path/to/SKU110K_fixed" --train-limit 1000 --val-limit 200 --test-limit 200
.venv/bin/python scripts/train_yolov8.py --data training_data/SKU110K_YOLO/data.yaml --epochs 25 --imgsz 640 --batch 8
```

## Review Workflow

1. Requirement analysis and module design.
2. Backend API and planogram database.
3. Website dashboard and app-style monitor.
4. Image upload and shelf scan.
5. Occupancy calculation and alert generation.
6. Testing, debugging, and GitHub submission.
