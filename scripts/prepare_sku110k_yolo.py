from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd
from PIL import Image
from tqdm import tqdm


def find_dir(root: Path, names: tuple[str, ...]) -> Path:
    for path in [root, *root.rglob("*")]:
        if path.is_dir() and path.name.lower() in names:
            return path
    raise FileNotFoundError(f"Could not find one of these folders under {root}: {names}")


def find_csv(root: Path, split: str) -> Path:
    candidates = sorted(root.rglob(f"*{split}*.csv"))
    if not candidates:
        raise FileNotFoundError(f"Could not find a CSV file for split '{split}' under {root}")
    return candidates[0]


def read_annotations(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, header=None)
    if len(df.columns) < 6:
        raise ValueError(f"{csv_path} does not look like SKU-110K bounding-box annotations.")

    df = df.iloc[:, :8].copy()
    df.columns = ["image", "x1", "y1", "x2", "y2", "class", "image_width", "image_height"]
    return df


def image_size(image_path: Path) -> tuple[int, int]:
    with Image.open(image_path) as image:
        return image.size


def prepare_split(
    dataset_root: Path,
    output_root: Path,
    split: str,
    limit: int,
    images_dir: Path,
) -> None:
    csv_path = find_csv(dataset_root, split)
    df = read_annotations(csv_path)
    image_names = df["image"].drop_duplicates().head(limit)

    split_images = output_root / "images" / split
    split_labels = output_root / "labels" / split
    split_images.mkdir(parents=True, exist_ok=True)
    split_labels.mkdir(parents=True, exist_ok=True)

    for image_name in tqdm(image_names, desc=f"Preparing {split}"):
        source_image = images_dir / str(image_name)
        if not source_image.exists():
            matches = list(images_dir.rglob(str(image_name)))
            if not matches:
                continue
            source_image = matches[0]

        destination_image = split_images / source_image.name
        shutil.copy2(source_image, destination_image)

        width, height = image_size(source_image)
        rows = df[df["image"] == image_name]
        label_path = split_labels / f"{source_image.stem}.txt"

        with label_path.open("w", encoding="utf-8") as label_file:
            for _, row in rows.iterrows():
                x1, y1, x2, y2 = float(row["x1"]), float(row["y1"]), float(row["x2"]), float(row["y2"])
                x_center = ((x1 + x2) / 2) / width
                y_center = ((y1 + y2) / 2) / height
                box_width = (x2 - x1) / width
                box_height = (y2 - y1) / height
                label_file.write(f"0 {x_center:.6f} {y_center:.6f} {box_width:.6f} {box_height:.6f}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare SKU-110K as YOLOv8 format.")
    parser.add_argument("--dataset-root", required=True, help="Path to extracted SKU-110K folder.")
    parser.add_argument("--output-root", default="training_data/SKU110K_YOLO", help="Output YOLO dataset path.")
    parser.add_argument("--train-limit", type=int, default=1000)
    parser.add_argument("--val-limit", type=int, default=200)
    parser.add_argument("--test-limit", type=int, default=200)
    args = parser.parse_args()

    dataset_root = Path(args.dataset_root).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve()
    images_dir = find_dir(dataset_root, ("images", "image"))

    prepare_split(dataset_root, output_root, "train", args.train_limit, images_dir)
    prepare_split(dataset_root, output_root, "val", args.val_limit, images_dir)
    prepare_split(dataset_root, output_root, "test", args.test_limit, images_dir)

    data_yaml = output_root / "data.yaml"
    data_yaml.write_text(
        f"""path: {output_root}
train: images/train
val: images/val
test: images/test

names:
  0: product
""",
        encoding="utf-8",
    )

    print(f"YOLO dataset ready: {output_root}")
    print(f"Config file: {data_yaml}")


if __name__ == "__main__":
    main()
