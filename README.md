# ShelfSense AI

AI-powered retail shelf monitoring system using a YOLOv8-ready detection workflow, shelf planogram comparison, occupancy scoring, alerts, analytics, and an app-style live monitor.

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

This project is ready for Vercel deployment. Import the GitHub repository in Vercel, keep the framework preset as Other, and deploy. More details are in `docs/DEPLOYMENT.md`.

## Current Prototype

The app uses mock AI detections so the full workflow can be demonstrated without a trained model file. It is ready for YOLOv8 integration by placing a trained `best.pt` file in `models/` and moving inference logic into `backend/detector.py`.

## Review Workflow

1. Requirement analysis and module design.
2. Backend API and planogram database.
3. Website dashboard and app-style monitor.
4. Image upload and shelf scan.
5. Occupancy calculation and alert generation.
6. Testing, debugging, and GitHub submission.
