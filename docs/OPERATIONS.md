# Operations Setup

## Workspace

- Overview: per-image zone availability, stock gaps, saved evidence, and priority restocks.
- Monitor: browser or HTTP snapshot camera, detections, zones, heatmap, class filters, and inference controls.
- Analysis: searchable zone results and saved-image comparisons with warnings when settings differ.
- Restock: assignments, progress, completion notes, and an activity timeline.
- Inventory: editable bounds, expected counts, product metadata, and thresholds. Auto-Calibrate is removed.
- Reports: source/date/status/search filters, paginated history, CSV export, and printable reports.
- Admin: model status, camera connections, and admin/manager/staff/viewer accounts.

The responsive website is also the installable PWA. Both share the same backend and records. The application shell is cached; scanning and account data require a connection.

## Accounts

Create the first account before remote access:

```bash
.venv/bin/python -m scripts.create_admin
```

A fresh database permits setup from localhost only. Accounts use hashed passwords and expiring cookie sessions. Set secure cookies for HTTPS deployment.

## Detection and Consistency

Controls include confidence, IoU, image size, maximum detections, minimum box area, and optional contrast enhancement. Settings and model identity are saved with each scan. Camera task updates require two matching zone states within 120 seconds. Identical uploaded images reuse their saved record.

Controls cannot guarantee correct counts. Select settings on labelled validation images, then evaluate once on held-out test data:

```bash
.venv/bin/python scripts/evaluate_model.py --data training_data/SKU110K_YOLO/data.yaml
.venv/bin/python scripts/evaluate_model.py --data training_data/SKU110K_YOLO/data.yaml --split test --conf 0.25 --iou 0.7
```

Replace the second command's thresholds with those selected on validation data. SKU110K detects generic shelf items; assigning SKU metadata does not train brand recognition. Configure zones and expected counts for each shelf view before interpreting availability. The current inventory layout is shared across camera sources.

## Cameras

Set `SHELFSENSE_CAMERAS` to a JSON map of names to HTTP JPEG snapshot URLs:

```text
{"aisle-1":"http://192.168.1.20/snapshot.jpg"}
```

These are snapshot endpoints, not RTSP streams. The backend must reach the camera network. Keep credentials in server environment settings.

## Resource Use

Inference reuses one model and an eight-entry result cache. Images are bounded to 1920 pixels on the longest side and stored as compressed JPEGs. Queries use indexes and pagination; concurrent inference is limited to one scan per process. No performance benchmark or production load test is claimed.

```bash
.venv/bin/python -m scripts.prune_history --days 90
```

Review the preview before adding `--apply`. Back up first. Retention preserves scans referenced by tasks. Existing legacy scan tables remain intact but are not migrated into the new workspace.

## Verification

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest tests -q
.venv/bin/python tests/browser_smoke.py
```

The browser check uses installed Google Chrome and the repository test images. Validate against representative labelled store images before operational use; the browser checks verify workflows, not model accuracy.
