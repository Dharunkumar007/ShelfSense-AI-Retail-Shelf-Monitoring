# ShelfSense AI Workflow

## User Request

Build the project in `/home/ron/dharun` as an app and website, then create a new public GitHub repository and push the created project files.

## Document Instructions Used

The attached documents define the academic project as an AI-powered retail shelf monitoring system using YOLOv8, OpenCV, backend logic, planogram comparison, alerts, analytics, and a dashboard.

## Build Flow

1. Camera or uploaded image is sent to the backend.
2. Detection engine returns product boxes.
3. Shelf analyzer compares detected products with the planogram.
4. Alert system marks low-stock and critical shelves.
5. Website dashboard shows overview, analysis, alerts, admin settings, and monitor.
6. App-style monitor shows a live shelf view for demo presentation.

## Development Phases

- Phase 1: Prototype with mock detections.
- Phase 2: Train YOLOv8 model using Roboflow or Colab.
- Phase 3: Replace mock detections with the trained model.
- Phase 4: Add real CCTV or webcam input.
- Phase 5: Improve reporting and export options.
