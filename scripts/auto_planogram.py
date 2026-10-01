import json
import sys
from pathlib import Path
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "best.pt"
PLANOGRAM_PATH = ROOT / "sample_data" / "planogram.json"

def generate_planogram(image_path: str):
    print(f"Analyzing shelf structure from: {image_path}")
    model = YOLO(str(MODEL_PATH))
    
    # Run YOLO to find all products
    results = model.predict(image_path, conf=0.25, verbose=False)
    boxes = results[0].boxes.xyxyn.tolist() # Normalized [x1, y1, x2, y2]
    
    if not boxes:
        print("Error: No products detected. Cannot generate planogram.")
        return

    # Extract the center Y coordinate for every detected product
    centers = [(b[1] + b[3]) / 2 for b in boxes]
    boxes_with_centers = list(zip(boxes, centers))
    
    # Sort products from top to bottom
    boxes_with_centers.sort(key=lambda x: x[1])
    
    # Cluster products into distinct shelves based on vertical gaps
    rows = []
    current_row = [boxes_with_centers[0]]
    
    # If the vertical gap between two products is greater than 6% of the image, 
    # it assumes a new shelf has started.
    for i in range(1, len(boxes_with_centers)):
        prev_y = current_row[-1][1]
        curr_y = boxes_with_centers[i][1]
        
        if curr_y - prev_y > 0.06:
            rows.append(current_row)
            current_row = [boxes_with_centers[i]]
        else:
            current_row.append(boxes_with_centers[i])
    rows.append(current_row)

    print(f"Success: AI identified {len(rows)} distinct shelves.")

    # Generate the JSON configuration
    zones = []
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    
    for i, row in enumerate(rows):
        # Calculate row height boundaries as percentages
        y1 = min([b[0][1] for b in row]) * 100
        y2 = max([b[0][3] for b in row]) * 100
        
        # Add a 2% buffer above and below the products to cover the whole physical shelf
        y1 = max(0, y1 - 2.0)
        y2 = min(100, y2 + 2.0)
        
        # Automatically set expected count to the number of items found + 10% buffer for empty gaps
        expected = int(len(row) * 1.1)
        half_expected = max(1, expected // 2)

        letter = letters[i % 26]
        
        # Create Left Zone
        zones.append({
            "id": f"{letter}1", "name": f"Shelf {i+1} Left", 
            "expected_count": half_expected, 
            "critical_threshold": 45, "low_threshold": 75, 
            "bbox": [0, round(y1, 1), 50, round(y2, 1)]
        })
        # Create Right Zone
        zones.append({
            "id": f"{letter}2", "name": f"Shelf {i+1} Right", 
            "expected_count": half_expected, 
            "critical_threshold": 45, "low_threshold": 75, 
            "bbox": [50, round(y1, 1), 100, round(y2, 1)]
        })

    planogram = {"zones": zones}
    
    with open(PLANOGRAM_PATH, "w", encoding="utf-8") as f:
        json.dump(planogram, f, indent=2)
        
    print(f"Dynamic Planogram Generated! Wrote {len(zones)} zones to {PLANOGRAM_PATH}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        generate_planogram(sys.argv[1])
    else:
        print("Usage: python scripts/auto_planogram.py <path_to_reference_image.jpg>")