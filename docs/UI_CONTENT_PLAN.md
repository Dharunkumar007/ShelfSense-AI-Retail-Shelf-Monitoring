# ShelfSense UI Content Plan

This document separates the sections already implemented from useful additions for a later production phase.

## Overview

Implemented sections:

- Shelf occupancy: the overall stock percentage calculated from the current image.
- Detected items: the detected count compared with the expected planogram count.
- Active alerts: the number of shelf zones below their configured threshold.
- Shelf health: a simple Healthy, Low, or Critical result for quick decisions.
- Latest shelf scan: the uploaded image with product detections and planogram zones.
- Stock level by zone: a dynamic chart generated entirely from the current image.
- Restock queue: the most urgent actions from the current scan.
- Recent scans: the latest results stored by the backend.

Recommended later:

- Store and aisle selector: lets a multi-store user change the monitored location.
- Daily comparison: compares the current result with the previous scan or opening stock.
- Estimated lost-sales risk: helps managers prioritize high-impact stock gaps.

## Live Monitor

Implemented sections:

- Detection canvas: shows the image and every detected product box.
- Detection summary: shows item count and average model confidence.
- Live zone inventory: shows occupancy and status for every configured zone.

Recommended later:

- Camera selector: switches between connected aisle cameras.
- Stream health: reports camera connection, frame rate, and last successful frame.
- Detection filters: toggles product boxes, zone boxes, and confidence labels.

## Analysis

Implemented sections:

- Scan summary: expected, detected, missing, and average confidence values.
- Zone performance table: compares detected and expected stock for each zone.
- Availability progress: gives a visual percentage and threshold status per zone.

Recommended later:

- Product-category breakdown: separates beverages, snacks, household items, and other classes.
- Scan comparison: compares two selected images or time periods.
- Export report: downloads the current result as CSV or PDF.
- Detection review: allows an authorized user to confirm false positives and missed products.

## Alerts

Implemented sections:

- Alert summary: shows how many zones need attention.
- Priority cards: show severity, availability, missing quantity, and zone.
- Severity legend: distinguishes Critical and Low Stock alerts.

Recommended later:

- Task assignment: assigns an alert to a store employee.
- Acknowledge and resolve controls: records action status and completion time.
- Alert history: supports audit and response-time reporting.
- Notification channels: sends selected alerts by push notification, email, or messaging service.

## Admin

Implemented sections:

- Product catalog: lists the product classes returned by the active model.
- Threshold rules: explains when Low Stock and Critical alerts are created.
- Camera zones: displays zones loaded from the backend planogram.
- AI model: shows model availability, model path, input type, and confidence threshold.

Recommended later:

- User roles: controls access for administrators, managers, and shelf staff.
- Store profile: manages store name, aisles, operating hours, and timezone.
- Integrations: connects inventory, point-of-sale, and notification systems.
- Audit log: records changes to thresholds, zones, users, and model versions.

## Optional New Views

- Reports: weekly availability, recurring stock gaps, alert response time, and export tools.
- Cameras: device setup, connectivity, image quality, and maintenance status.
- Inventory: product-to-zone mapping, expected facing count, and replenishment targets.
