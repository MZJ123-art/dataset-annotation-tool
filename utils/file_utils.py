import os
import shutil
from pathlib import Path
from typing import List, Optional

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm"}


def _search_files_in_dir(directory: Path, extensions: set) -> List[str]:
    """Search for files with given extensions in a single directory (non-recursive)."""
    files = []
    for ext in extensions:
        files.extend(str(f) for f in directory.glob(f"*{ext}"))
        files.extend(str(f) for f in directory.glob(f"*{ext.upper()}"))
    return sorted(set(files))


def _deep_search(directory: Path, extensions: set, max_depth: int = 3) -> List[str]:
    """Search for files up to max_depth levels of subdirectories.

    If the current directory has files, return them immediately.
    Otherwise, search ALL subdirectories at the next level and collect files.
    If still nothing, go deeper.
    """
    files = _search_files_in_dir(directory, extensions)
    if files:
        return files

    if max_depth <= 0:
        return []

    # Search all immediate subdirectories, collect from ALL that have files
    subdirs = sorted([d for d in directory.iterdir() if d.is_dir()])
    all_files = []
    for subdir in subdirs:
        all_files.extend(_search_files_in_dir(subdir, extensions))
    if all_files:
        return sorted(set(all_files))

    # Still nothing, go deeper
    if max_depth > 1:
        for subdir in subdirs:
            all_files.extend(_deep_search(subdir, extensions, max_depth - 1))
        if all_files:
            return sorted(set(all_files))

    return []


def get_image_files(directory: str) -> List[str]:
    p = Path(directory)
    if not p.is_dir():
        return []
    files = _search_files_in_dir(p, IMAGE_EXTS)
    if not files:
        files = _deep_search(p, IMAGE_EXTS, max_depth=3)
    return files


def get_video_files(directory: str) -> List[str]:
    p = Path(directory)
    if not p.is_dir():
        return []
    files = _search_files_in_dir(p, VIDEO_EXTS)
    if not files:
        files = _deep_search(p, VIDEO_EXTS, max_depth=3)
    return files


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
