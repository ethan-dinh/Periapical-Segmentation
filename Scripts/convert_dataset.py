"""
This script converts the dataset from the format used by DentAnX to the format used by YOLOv8.
"""

from pathlib import Path
import json
import shutil
from PIL import Image

def main():
    """
    This function converts the dataset from the format used by DentAnX to the format used by YOLOv8.
    """

    # Paths
    project_root = Path(__file__).parent.resolve()
    source_json_dir = project_root / "../Dataset/Training/Key Points Annotations"
    source_img_dir = project_root / "../Dataset/Training/Images"

    # Destination directories
    training_dir = project_root / "Data"
    training_annotations_dir = training_dir / "annotations"

    # Create directories
    training_dir.mkdir(exist_ok=True)
    training_annotations_dir.mkdir(exist_ok=True)

    if not source_json_dir.exists():
        print(f"Error: Source JSON dir not found at {source_json_dir}")
        return

    json_files = list(source_json_dir.glob("*.json"))
    print(f"Found {len(json_files)} JSON files to process.")

    count = 0
    for input_json_path in json_files:
        basename = input_json_path.stem

        # Find corresponding image
        input_img_path = source_img_dir / f"{basename}.jpg"
        if not input_img_path.exists():
            # Try other extensions
            found = False
            for ext in ['.png', '.jpeg', '.bmp', '.tif', '.tiff']:
                potential = source_img_dir / f"{basename}{ext}"
                if potential.exists():
                    input_img_path = potential
                    found = True
                    break
            if not found:
                print(f"Warning: Image for {basename} not found. Skipping.")
                continue

        img_filename = input_img_path.name

        # Copy Image
        dest_img_path = training_dir / img_filename
        shutil.copy(input_img_path, dest_img_path)

        # Get Image Dimensions
        try:
            with Image.open(input_img_path) as img:
                width, height = img.size
        except Exception as e:
            print(f"Error opening image {input_img_path}: {e}")
            continue

        # Read Input JSON
        try:
            with open(input_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading JSON {input_json_path}: {e}")
            continue

        bboxes_out = []

        if "bboxes" in data:
            for bbox in data["bboxes"]:
                if len(bbox) == 4:
                    xmin, ymin, xmax, ymax = bbox
                    bboxes_out.append({
                        "label": "Tooth",
                        "xmin": float(xmin),
                        "ymin": float(ymin),
                        "xmax": float(xmax),
                        "ymax": float(ymax)
                    })
                else:
                    # Some files might have different formats or legacy data
                    pass

        points_out = []
        
        # Extract CEJ Points
        if "CEJ_Points" in data:
            for pt in data["CEJ_Points"]:
                if len(pt) == 2:
                    points_out.append({
                        "x": float(pt[0]),
                        "y": float(pt[1]),
                        "class": "CEJ"
                    })

        # Extract Apex Points
        if "Apex_Points" in data:
            for pt in data["Apex_Points"]:
                if len(pt) == 2:
                    points_out.append({
                        "x": float(pt[0]),
                        "y": float(pt[1]),
                        "class": "APEX"
                    })

        # Extract Bone Lines
        bone_lines_out = []
        # Bone annotations are in a separate folder
        bone_json_path = project_root / "../Dataset/Training/Bone Level Annotations" / f"{basename}.json"
        if bone_json_path.exists():
            try:
                with open(bone_json_path, 'r', encoding='utf-8') as f:
                    bone_data = json.load(f)
                if "Bone_Lines" in bone_data:
                    for line in bone_data["Bone_Lines"]:
                        # line is a list of points [x, y]
                        converted_line = []
                        for pt in line:
                            if len(pt) == 2:
                                converted_line.append({"x": float(pt[0]), "y": float(pt[1])})
                        if converted_line:
                            bone_lines_out.append(converted_line)
            except Exception as e:
                print(f"Error reading Bone JSON {bone_json_path}: {e}")

        # Sync Bone Line Endpoints to CREST points
        # Ensure that the first and last point of every bone line exists as a CREST point
        for line in bone_lines_out:
            if not line:
                continue
            
            endpoints = [line[0], line[-1]]
            for pt in endpoints:
                # Check if this point exists in points_out as CREST
                exists = False
                for existing_pt in points_out:
                    if existing_pt["class"] == "CREST":
                        # Euclidean distance check (tolerance 2.0 pixels)
                        dist = ((existing_pt["x"] - pt["x"])**2 + (existing_pt["y"] - pt["y"])**2)**0.5
                        if dist < 2.0:
                            exists = True
                            break
                
                if not exists:
                    points_out.append({
                        "x": pt["x"],
                        "y": pt["y"],
                        "class": "CREST"
                    })

        output_data = {
            "file_name": img_filename,
            "width": width,
            "height": height,
            "points": points_out, 
            "bboxes": bboxes_out,
            "bone_lines": bone_lines_out
        }

        # Save Output JSON
        output_json_path = training_annotations_dir / f"{basename}.json"
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

        count += 1
        if count % 10 == 0:
            print(f"Processed {count} files...", end='\r')

    print(f"\nBatch conversion completed. Processed {count} files.")

if __name__ == "__main__":
    main()
