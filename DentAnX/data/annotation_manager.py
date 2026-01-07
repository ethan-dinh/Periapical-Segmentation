"""
This module provides a class for loading, storing, and exporting per-image annotation JSON files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List
import shutil

from ..utils.landmarks import BBOX_CLASSES


SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


@dataclass
class AnnotationRecord:
    """Represents a per-image annotation JSON file."""
    file_name: str
    width: int
    height: int
    points: List[Dict[str, float | str]]
    bboxes: List[Dict[str, int | float | str]] = None
    bone_lines: List[List[Dict[str, float]]] = None  # New field

    def __post_init__(self):
        if self.bboxes is None:
            self.bboxes = []
        if self.bone_lines is None:
            self.bone_lines = []


class AnnotationManager:
    """Loads, stores, and exports per-image annotation JSON files."""

    def __init__(self) -> None:
        self.image_dir: Path | None = None
        self.annotation_dir: Path | None = None
        self._cache: Dict[str, AnnotationRecord] = {}

    def set_image_directory(self, path: str) -> List[str]:
        """Sets the image directory and initializes the annotation directory."""
        root = Path(path).expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(path)
        self.image_dir = root
        self.annotation_dir = root / "annotations"
        self.annotation_dir.mkdir(parents=True, exist_ok=True)
        self._cache.clear()
        return self._scan_images()

    def _scan_images(self) -> List[str]:
        if self.image_dir is None:
            return []
        files: List[str] = []
        for candidate in self.image_dir.iterdir():
            if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(candidate.name)
        files.sort(key=lambda n: n.lower())
        return files

    def annotation_path(self, file_name: str) -> Path:
        """Returns the path to the annotation file for the given image file name."""
        if self.annotation_dir is None:
            raise RuntimeError("Annotation directory is not set.")
        safe_name = file_name.replace("/", "_")
        return self.annotation_dir / f"{Path(safe_name).stem}.json"

    def load(self, file_name: str, width: int, height: int) -> AnnotationRecord:
        """Loads an annotation record from a JSON file."""
        path = self.annotation_path(file_name)
        if file_name in self._cache:
            return self._cache[file_name]
        if not path.exists():
            record = AnnotationRecord(
                file_name=file_name, 
                width=width, 
                height=height, 
                points=[], 
                bboxes=[],
                bone_lines=[]
            )
            self._cache[file_name] = record
            return record
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        points = data.get("points", [])
        bboxes = data.get("bboxes", [])
        bone_lines = data.get("bone_lines", [])
        record = AnnotationRecord(
            file_name=data.get("file_name", file_name),
            width=int(data.get("width", width)),
            height=int(data.get("height", height)),
            points=points,
            bboxes=bboxes,
            bone_lines=bone_lines,
        )
        self._cache[file_name] = record
        return record

    def save(self, record: AnnotationRecord) -> None:
        """Saves an annotation record to a JSON file."""
        path = self.annotation_path(record.file_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(asdict(record), fh, indent=2)
        self._cache[record.file_name] = record

    def export_all(self) -> Path:
        """Exports all annotations to a single JSON file."""
        if self.annotation_dir is None:
            raise RuntimeError("Annotation directory is not set.")
        points_path = self.annotation_dir / "points.json"
        images = self._load_all_records()
        export_payload = {"images": [asdict(img) for img in images]}
        with points_path.open("w", encoding="utf-8") as fh:
            json.dump(export_payload, fh, indent=2)
        return points_path

    def _load_all_records(self) -> List[AnnotationRecord]:
        if self.annotation_dir is None:
            raise RuntimeError("Annotation directory is not set.")
        images: List[AnnotationRecord] = []
        for json_path in sorted(self.annotation_dir.glob("*.json")):
            if json_path.name == "points.json":
                continue
            with json_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            images.append(
                AnnotationRecord(
                    file_name=data.get("file_name", json_path.stem),
                    width=int(data.get("width", 0)),
                    height=int(data.get("height", 0)),
                    points=data.get("points", []),
                    bboxes=data.get("bboxes", []),
                    bone_lines=data.get("bone_lines", []),
                )
            )
        images.sort(key=lambda rec: rec.file_name.lower())
        return images

    def export_datasets(self, destination: Path, val_split: float = 0.2, seed: int = 42) -> str:
        """Exports the dataset into training and validation sets."""
        if self.image_dir is None or self.annotation_dir is None:
            raise RuntimeError("Image directory is not set.")
        destination = destination.expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)

        # 1. Identify Annotated vs Unannotated
        all_files = self._scan_images()
        annotated_records: List[AnnotationRecord] = []
        unannotated_files: List[str] = []

        for fname in all_files:
            ann_path = self.annotation_path(fname)
            if ann_path.exists():
                try:
                    if fname in self._cache:
                        record = self._cache[fname]
                    else:
                        from PIL import Image
                        with Image.open(self.image_dir / fname) as img:
                            w, h = img.size
                        record = self.load(fname, w, h)

                    has_bbox = len(record.bboxes) > 0
                    has_crest = any(p.get("class") == "CREST" for p in record.points)
                    has_cej = any(p.get("class") == "CEJ" for p in record.points)

                    if has_bbox and has_crest and has_cej:
                        annotated_records.append(record)
                    else:
                        unannotated_files.append(fname)
                except Exception as e:
                    print(f"Error loading {fname}: {e}")
                    unannotated_files.append(fname)
            else:
                unannotated_files.append(fname)

        # 2. Split Annotated into Train/Val
        import random
        import math
        from PIL import Image

        random.seed(seed)
        random.shuffle(annotated_records)

        split_idx = int(len(annotated_records) * (1 - val_split))
        train_records = annotated_records[:split_idx]
        val_records = annotated_records[split_idx:]

        # Create Directories
        bbox_dir = destination / "bbox_dataset"
        landmark_dir = destination / "landmark_dataset"
        test_dir = destination / "test_images"

        (bbox_dir / "images" / "train").mkdir(parents=True, exist_ok=True)
        (bbox_dir / "images" / "val").mkdir(parents=True, exist_ok=True)
        (bbox_dir / "labels" / "train").mkdir(parents=True, exist_ok=True)
        (bbox_dir / "labels" / "val").mkdir(parents=True, exist_ok=True)

        (landmark_dir / "rois").mkdir(parents=True, exist_ok=True)
        test_dir.mkdir(parents=True, exist_ok=True)

        # Helper for BBox Export
        def export_bbox(records, split_name):
            for record in records:
                src_img = self.image_dir / record.file_name
                if not src_img.exists():
                    continue

                # Copy Image
                dst_img = bbox_dir / "images" / split_name / record.file_name
                shutil.copy(src_img, dst_img)

                # Generate Label
                label_path = bbox_dir / "labels" / split_name / f"{Path(record.file_name).stem}.txt"
                with open(label_path, "w", encoding="utf-8") as lf:
                    for bbox in record.bboxes:
                        # Skip unlabeled boxes
                        label = bbox.get("label", "Unlabeled")
                        if label == "Unlabeled":
                            continue

                        # Handle formats
                        if "cx" in bbox:
                            cx, cy = float(bbox["cx"]), float(bbox["cy"])
                            w, h = float(bbox["width"]), float(bbox["height"])
                            rotation = float(bbox.get("rotation", 0.0))
                        else:
                            xmin, ymin = float(bbox["xmin"]), float(bbox["ymin"])
                            xmax, ymax = float(bbox["xmax"]), float(bbox["ymax"])
                            cx = (xmin + xmax) / 2
                            cy = (ymin + ymax) / 2
                            w = xmax - xmin
                            h = ymax - ymin
                            rotation = 0.0

                        # Normalize
                        img_w, img_h = record.width, record.height

                        # Calculate corners for OBB
                        rad = math.radians(rotation)
                        cos_a = math.cos(rad)
                        sin_a = math.sin(rad)
                        hw, hh = w / 2, h / 2

                        corners_local = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
                        corners_global = []
                        for dx, dy in corners_local:
                            gx = cx + dx * cos_a - dy * sin_a
                            gy = cy + dx * sin_a + dy * cos_a
                            nx = max(0.0, min(1.0, gx / img_w))
                            ny = max(0.0, min(1.0, gy / img_h))
                            corners_global.extend([nx, ny])

                        # Get class ID (skip index 0 which is "Unlabeled")
                        try:
                            class_id = BBOX_CLASSES.index(label) - 1  # Subtract 1 to account for Unlabeled
                        except ValueError:
                            class_id = 0

                        lf.write(f"{class_id} " + " ".join(f"{c:.6f}" for c in corners_global) + "\n")

        # Helper for Landmark Export
        def export_landmark(records, _) -> List[dict]:
            dataset_entries = []
            for record in records:
                src_img = self.image_dir / record.file_name
                if not src_img.exists():
                    continue

                if not record.bboxes:
                    continue

                try:
                    with Image.open(src_img) as im:
                        for i, bbox in enumerate(record.bboxes):
                            # Rotation/Crop Logic
                            if "cx" in bbox:
                                cx, cy = float(bbox["cx"]), float(bbox["cy"])
                                w, h = float(bbox["width"]), float(bbox["height"])
                                rotation = float(bbox.get("rotation", 0.0))
                            else:
                                xmin, ymin = float(bbox["xmin"]), float(bbox["ymin"])
                                xmax, ymax = float(bbox["xmax"]), float(bbox["ymax"])
                                cx = (xmin + xmax) / 2
                                cy = (ymin + ymax) / 2
                                w = xmax - xmin
                                h = ymax - ymin
                                rotation = 0.0

                            rotated_im = im.rotate(rotation, center=(cx, cy), resample=Image.Resampling.BICUBIC)
                            left = cx - w / 2
                            top = cy - h / 2
                            right = cx + w / 2
                            bottom = cy + h / 2

                            roi_img = rotated_im.crop((left, top, right, bottom))
                            roi_filename = f"{Path(record.file_name).stem}_roi_{i}.png"
                            roi_path = landmark_dir / "rois" / roi_filename
                            roi_img.save(roi_path)

                            # Transform Points
                            rad = math.radians(rotation)
                            cos_a = math.cos(rad)
                            sin_a = math.sin(rad)

                            roi_points = []
                            for pt in record.points:
                                px, py = float(pt["x"]), float(pt["y"])
                                dx = px - cx
                                dy = py - cy
                                rx_rot = dx * cos_a + dy * sin_a
                                ry_rot = -dx * sin_a + dy * cos_a
                                rx = rx_rot + w / 2
                                ry = ry_rot + h / 2

                                if 0 <= rx <= w and 0 <= ry <= h:
                                    roi_points.append({
                                        "class": pt["class"],
                                        "x": rx,
                                        "y": ry,
                                        "global_x": px,
                                        "global_y": py
                                    })

                            dataset_entries.append({
                                "file_name": roi_filename,
                                "width": w,
                                "height": h,
                                "points": roi_points,
                                "original_image": record.file_name,
                                "bbox": {"cx": cx, "cy": cy, "width": w, "height": h, "rotation": rotation}
                            })
                except Exception as e:
                    print(f"Error processing landmark export for {record.file_name}: {e}")
            return dataset_entries

        # Execute Exports
        export_bbox(train_records, "train")
        export_bbox(val_records, "val")

        train_rois = export_landmark(train_records, "train")
        val_rois = export_landmark(val_records, "val")

        # Save Landmark JSONs
        with open(landmark_dir / "stage2_train.json", "w", encoding="utf-8") as f:
            json.dump({"images": train_rois}, f, indent=2)
        with open(landmark_dir / "stage2_val.json", "w", encoding="utf-8") as f:
            json.dump({"images": val_rois}, f, indent=2)

        # Create data.yaml for YOLO (exclude "Unlabeled" class)
        labeled_classes = [cls for cls in BBOX_CLASSES if cls != "Unlabeled"]
        yaml_content = f"""
path: {bbox_dir.absolute()}
train: images/train
val: images/val
names:
{chr(10).join(f"  {i}: {name}" for i, name in enumerate(labeled_classes))}
"""
        with open(bbox_dir / "data.yaml", "w", encoding="utf-8") as f:
            f.write(yaml_content.strip())

        # 3. Export Test Images
        for fname in unannotated_files:
            src = self.image_dir / fname
            if src.exists():
                shutil.copy(src, test_dir / fname)

        summary = (
            f"Export Complete:\n"
            f"- BBox Dataset: {len(train_records)} train, {len(val_records)} val images\n"
            f"- Landmark Dataset: {len(train_rois)} train, {len(val_rois)} val ROIs\n"
            f"- Test Images: {len(unannotated_files)} images"
        )
        return summary
