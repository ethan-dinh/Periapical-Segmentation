"""
This script opens a directory containing images and subdirectories of annotations,
randomly selects a subset of the images to use for training and validation,
and creates a new directory structure with the selected images and annotations.

Optimizations vs original:
- Single-pass file discovery (no repeated expensive glob calls)
- Optional fast annotation index (map stem -> json path) to avoid per-file filesystem probing
- Uses shutil.copy2 for metadata-preserving copies
- Uses tqdm progress bars for copy operations
- Uses random.Random(seed) for reproducibility if desired
- Writes train.txt / val.txt using output paths (optionally relative)

Author: Ethan Dinh
Date: 2026-01-09
"""

from __future__ import annotations

import os
import random
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from tqdm import tqdm


# -----------------------------
# File discovery
# -----------------------------
IMAGE_EXTS = (".png", ".jpg", ".jpeg")
ANNOT_EXT = ".json"


def iter_images(images_dir: Path) -> Iterable[Path]:
    """Yield image paths under images_dir."""
    # rglob is typically faster and cleaner than multiple glob("**/*.ext")
    for p in images_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            yield p


def build_annotation_index(data_dir: Path) -> Dict[str, Path]:
    """
    Build an index from annotation stem -> json path by scanning *once*.
    This avoids repeated exists() checks per image.
    """
    ann_dir = data_dir / "annotations"
    idx: Dict[str, Path] = {}
    if not ann_dir.exists():
        return idx

    for p in ann_dir.rglob(f"*{ANNOT_EXT}"):
        if p.is_file():
            idx[p.stem] = p
    return idx


# -----------------------------
# Copy helpers
# -----------------------------
def copy_image_and_annotation(
    image_file: Path,
    dest_images_dir: Path,
    dest_annotations_dir: Path,
    ann_index: Optional[Dict[str, Path]] = None,
    warn_missing: bool = True,
) -> None:
    """
    Copy one image file to dest_images_dir and its annotation (if found) to dest_annotations_dir.

    Annotation resolution order:
    1) If ann_index provided and contains stem, use it
    2) image_file sibling: image_file.with_suffix(".json")
    3) image_file.parent.parent / "annotations" / f"{stem}.json"
    """
    # Copy image
    shutil.copy2(image_file, dest_images_dir / image_file.name)

    stem = image_file.stem
    candidate: Optional[Path] = None

    # 1) Indexed lookup (fast)
    if ann_index is not None:
        candidate = ann_index.get(stem)

    # 2) Same directory as image
    if candidate is None:
        sib = image_file.with_suffix(ANNOT_EXT)
        if sib.exists():
            candidate = sib

    # 3) Sibling annotations directory relative to image layout
    if candidate is None:
        sib_ann = image_file.parent.parent / "annotations" / f"{stem}{ANNOT_EXT}"
        if sib_ann.exists():
            candidate = sib_ann

    if candidate is not None and candidate.exists():
        shutil.copy2(candidate, dest_annotations_dir / candidate.name)
    else:
        if warn_missing:
            # Avoid spamming too much, but keep behavior consistent
            # You can disable with --no-warn-missing
            print(f"Warning: No annotation found for {image_file.name}")


# -----------------------------
# Main selection routine
# -----------------------------
def select_random_images(
    data_dir: Path,
    train_dir: Path,
    val_dir: Path,
    train_percent: float,
    val_percent: float,
    max_images: Optional[int] = None,
    seed: Optional[int] = None,
    index_annotations: bool = True,
    warn_missing: bool = True,
    write_relative_paths: bool = False,
) -> Tuple[List[Path], List[Path]]:
    """
    Select a random subset of images from data_dir/images, split into train/val,
    copy images + annotations, and write train.txt/val.txt.

    Returns:
        (train_files, val_files) as lists of image Paths (original locations)
    """
    images_dir = data_dir / "images"
    if not images_dir.exists():
        raise ValueError(f"Images directory {images_dir} does not exist.")

    # One-pass collection
    image_files = list(iter_images(images_dir))
    total_found = len(image_files)

    if total_found == 0:
        raise ValueError(f"No images found under {images_dir} (extensions: {IMAGE_EXTS}).")

    # Optional cap
    if max_images is not None:
        # If you truly want random among all, sample before truncation.
        # Here we cap after shuffling for uniformity.
        pass

    rng = random.Random(seed)
    rng.shuffle(image_files)

    if max_images is not None:
        image_files = image_files[:max_images]

    n = len(image_files)
    if n == 0:
        raise ValueError("After applying max_images, no images remain to split.")

    # Validate percents
    if not (0.0 < train_percent < 1.0) or not (0.0 <= val_percent < 1.0):
        raise ValueError("train_percent must be in (0,1); val_percent must be in [0,1).")
    if train_percent + val_percent > 1.0:
        raise ValueError("train_percent + val_percent must be <= 1.0.")

    n_train = int(train_percent * n)
    n_val = int(val_percent * n)

    train_files = image_files[:n_train]
    val_files = image_files[n_train:n_train + n_val]

    # Output dirs
    train_images_dir = train_dir / "images"
    train_annotations_dir = train_dir / "annotations"
    val_images_dir = val_dir / "images"
    val_annotations_dir = val_dir / "annotations"

    for d in (train_images_dir, train_annotations_dir, val_images_dir, val_annotations_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Build annotation index once (optional)
    ann_index = build_annotation_index(data_dir) if index_annotations else None

    print(f"Found {total_found} images total under: {images_dir}")
    print(f"Using {n} images after max_images={max_images}")
    print(f"Train: {len(train_files)} ({train_percent:.2%}), Val: {len(val_files)} ({val_percent:.2%})")

    # Copy with progress bars
    for f in tqdm(train_files, desc="Copying train set", unit="img"):
        copy_image_and_annotation(
            f, train_images_dir, train_annotations_dir,
            ann_index=ann_index, warn_missing=warn_missing
        )

    for f in tqdm(val_files, desc="Copying val set", unit="img"):
        copy_image_and_annotation(
            f, val_images_dir, val_annotations_dir,
            ann_index=ann_index, warn_missing=warn_missing
        )

    # Write manifest files
    def _fmt_path(p: Path) -> str:
        if write_relative_paths:
            # relative to data_dir for portability
            return str(p.relative_to(data_dir))
        return str(p)

    (train_dir / "train.txt").write_text("\n".join(_fmt_path(p) for p in train_files) + "\n")
    (val_dir / "val.txt").write_text("\n".join(_fmt_path(p) for p in val_files) + "\n")

    return train_files, val_files


# -----------------------------
# CLI
# -----------------------------
def read_command_line_args():
    import argparse

    parser = argparse.ArgumentParser(
        description="Randomly select images for train/val, copy images+annotations, write train.txt/val.txt."
    )
    parser.add_argument("data_dir", type=str, help="Path to the data directory (must contain images/)")
    parser.add_argument("train_dir", type=str, help="Path to the train output directory")
    parser.add_argument("val_dir", type=str, help="Path to the val output directory")
    parser.add_argument("train_percent", type=float, help="Fraction of images to use for training (0-1)")
    parser.add_argument("val_percent", type=float, help="Fraction of images to use for validation (0-1)")
    parser.add_argument("max_images", type=int, nargs="?", default=None, help="Optional cap on number of images")

    parser.add_argument("--seed", type=int, default=23, help="Random seed for reproducibility")
    parser.add_argument(
        "--no-annotation-index",
        action="store_true",
        help="Disable pre-indexing annotations (slower when many files)."
    )
    parser.add_argument(
        "--no-warn-missing",
        action="store_true",
        help="Disable warnings for missing annotations."
    )
    parser.add_argument(
        "--write-relative-paths",
        action="store_true",
        help="Write train.txt/val.txt paths relative to data_dir."
    )

    return parser.parse_args()


def main():
    args = read_command_line_args()

    # If you do not want to change working directory, remove the next two lines.
    script_dir = Path(__file__).resolve().parent
    os.chdir(script_dir)

    data_dir = Path(args.data_dir)
    train_dir = Path(args.train_dir)
    val_dir = Path(args.val_dir)

    print(
        f"Selecting {args.train_percent:.2%} train and {args.val_percent:.2%} val "
        f"from data_dir={data_dir}"
    )

    select_random_images(
        data_dir=data_dir,
        train_dir=train_dir,
        val_dir=val_dir,
        train_percent=args.train_percent,
        val_percent=args.val_percent,
        max_images=args.max_images,
        seed=args.seed,
        index_annotations=not args.no_annotation_index,
        warn_missing=not args.no_warn_missing,
        write_relative_paths=args.write_relative_paths,
    )


if __name__ == "__main__":
    main()
