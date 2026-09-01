# Testing Report

## Tested Items

- Backend API startup.
- Static website loading.
- Shelf scan request.
- Mock detection generation.
- Planogram comparison.
- Occupancy calculation.
- Restock alert generation.

## Expected Result

The dashboard opens in the browser, scan results are displayed, shelf zones are color-coded, and low-stock alerts appear in the alerts center.

## Limitations

The current version uses mock detection output. Real YOLOv8 detection requires a trained model file at `models/best.pt`.
