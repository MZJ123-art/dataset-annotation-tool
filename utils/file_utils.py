import os
import shutil
from pathlib import Path
from typing import List, Optional

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm"}


def get_image_files(directory: str) -> List[str]:
    p = Path(directory)
    files = []
    for ext in IMAGE_EXTS:
        files.extend(str(f) for f in p.glob(f"*{ext}"))
        files.extend(str(f) for f in p.glob(f"*{ext.upper()}"))
    return sorted(set(files))


def get_video_files(directory: str) -> List[str]:
    p = Path(directory)
    files = []
    for ext in VIDEO_EXTS:
        files.extend(str(f) for f in p.glob(f"*{ext}"))
        files.extend(str(f) for f in p.glob(f"*{ext.upper()}"))
    return sorted(set(files))


def find_label_for_image(image_path: str, label_dir: Optional[str] = None) -> Optional[str]:
    stem = Path(image_path).stem
    if label_dir is None:
        label_dir = str(Path(image_path).parent)
    for ext in [".txt", ".xml", ".json"]:
        candidate = Path(label_dir) / f"{stem}{ext}"
        if candidate.exists():
            return str(candidate)
    # check sibling labels/ dir
    parent = Path(image_path).parent
    labels_dir = parent / "labels"
    if labels_dir.is_dir():
        for ext in [".txt", ".xml"]:
            candidate = labels_dir / f"{stem}{ext}"
            if candidate.exists():
                return str(candidate)
    return None


def safe_makedirs(path: str):
    os.makedirs(path, exist_ok=True)


def copy_with_structure(src: str, dst_dir: str) -> str:
    safe_makedirs(dst_dir)
    dst = os.path.join(dst_dir, os.path.basename(src))
    shutil.copy2(src, dst)
    return dst
