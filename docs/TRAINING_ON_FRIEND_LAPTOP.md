# Train YOLOv8 On Friend Laptop

Use this guide if Kaggle is not working. Train on any laptop with good internet. A GPU is better, but CPU also works slowly for a small demo dataset.

## 1. Clone Project

```bash
git clone https://github.com/Ronnirvin2006/ShelfSense-AI-Retail-Shelf-Monitoring.git
cd ShelfSense-AI-Retail-Shelf-Monitoring
```

## 2. Create Python Environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements-training.txt
```

Ubuntu/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-training.txt
```

## 3. Download Dataset

Download this dataset:

```text
https://www.kaggle.com/datasets/mohamedessam3112002/sku110k?select=SKU110K_fixed
```

Extract the ZIP file. Keep the extracted folder path ready.

Example paths:

Windows:

```text
C:\Users\YourName\Downloads\SKU110K_fixed
```

Ubuntu/Linux:

```text
/home/yourname/Downloads/SKU110K_fixed
```

## 4. Prepare YOLO Dataset

Windows PowerShell:

```powershell
.\.venv\Scripts\python scripts\prepare_sku110k_yolo.py --dataset-root "C:\Users\YourName\Downloads\SKU110K_fixed" --train-limit 1000 --val-limit 200 --test-limit 200
```

Ubuntu/Linux:

```bash
.venv/bin/python scripts/prepare_sku110k_yolo.py --dataset-root "/home/yourname/Downloads/SKU110K_fixed" --train-limit 1000 --val-limit 200 --test-limit 200
```

This creates:

```text
training_data/SKU110K_YOLO/data.yaml
```

## 5. Train Model

Windows PowerShell:

```powershell
.\.venv\Scripts\python scripts\train_yolov8.py --data training_data\SKU110K_YOLO\data.yaml --epochs 25 --imgsz 640 --batch 8
```

Ubuntu/Linux:

```bash
.venv/bin/python scripts/train_yolov8.py --data training_data/SKU110K_YOLO/data.yaml --epochs 25 --imgsz 640 --batch 8
```

The trained model will be saved at:

```text
runs/detect/shelfsense_yolov8n/weights/best.pt
```

## 6. Test Model

Windows PowerShell:

```powershell
.\.venv\Scripts\python scripts\predict_test.py --model runs\detect\shelfsense_yolov8n\weights\best.pt --source training_data\SKU110K_YOLO\images\test
```

Ubuntu/Linux:

```bash
.venv/bin/python scripts/predict_test.py --model runs/detect/shelfsense_yolov8n/weights/best.pt --source training_data/SKU110K_YOLO/images/test
```

Prediction images will be saved inside:

```text
runs/detect/predict
```

## 7. Add Model To ShelfSense App

Copy the trained model:

From:

```text
runs/detect/shelfsense_yolov8n/weights/best.pt
```

To:

```text
models/best.pt
```

Then run the app:

Windows PowerShell:

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pip install ultralytics opencv-python
.\.venv\Scripts\python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Ubuntu/Linux:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install ultralytics opencv-python
.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

Upload a shelf image. If `models/best.pt` exists, the app uses real YOLOv8 detection. If the model is missing, it uses mock detection for demo.

## Faster Or Better Training

For a first review, keep:

```text
1000 train images, 200 validation images, 25 epochs
```

For better final output, try:

```text
3000 train images, 500 validation images, 50 epochs
```

If the laptop runs out of memory, reduce batch:

```bash
--batch 4
```
