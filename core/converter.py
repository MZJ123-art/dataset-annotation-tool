import os
from pathlib import Path
from typing import List, Callable, Optional
from utils.data_model import Annotation, ClassMapping
from utils.formats import yolo_format, coco_format, voc_format
from utils.file_utils import safe_makedirs, get_image_files, find_label_for_image


class FormatType:
    YOLO = "YOLO"
    COCO = "COCO"
    VOC = "VOC"

    ALL = [YOLO, COCO, VOC]


def _check_yolo_in_dir(sd: Path) -> bool:
    """Check if a directory contains YOLO format txt files."""
    for f in sd.glob("*.txt"):
        if f.name in ("classes.txt", "classes.names"):
            continue
        try:
            with open(f, "r") as fh:
                lines = fh.read().strip().split("\n")
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 5:
                    try:
                        float(parts[1])
                        return True
                    except ValueError:
                        break
        except Exception:
            continue
    return False


def _check_voc_in_dir(d: Path) -> bool:
    """Check if a directory contains VOC XML files."""
    ann_dir = d / "Annotations" if (d / "Annotations").is_dir() else d
    if list(ann_dir.glob("*.xml")):
        return True
    return False


def detect_format(dataset_dir: str, label_dir: str = None, max_depth: int = 3) -> Optional[str]:
    p = Path(dataset_dir)
    lbl_dir = Path(label_dir) if label_dir else p

    # Build search dirs: lbl_dir, labels/, and up to max_depth levels of subdirs
    search_dirs = [lbl_dir]
    if (p / "labels").is_dir():
        search_dirs.append(p / "labels")

    def _collect_subdirs(base: Path, depth: int) -> list:
        dirs = []
        if depth <= 0:
            return dirs
        for subdir in sorted(base.iterdir()):
            if subdir.is_dir() and subdir.name not in ("labels", "Annotations"):
                dirs.append(subdir)
                dirs.extend(_collect_subdirs(subdir, depth - 1))
        return dirs

    search_dirs.extend(_collect_subdirs(lbl_dir, max_depth))

    # Check YOLO
    for sd in search_dirs:
        if _check_yolo_in_dir(sd):
            return FormatType.YOLO

    # Check COCO (search up to max_depth)
    json_file = coco_format.find_coco_json(dataset_dir, max_depth=max_depth)
    if json_file:
        return FormatType.COCO

    # Check VOC
    for sd in search_dirs:
        if _check_voc_in_dir(sd):
            return FormatType.VOC

    return None


def read_dataset_by_format(dataset_dir: str, fmt: str,
                           image_dir: str = None, label_dir: str = None) -> tuple[List[Annotation], ClassMapping]:
    if fmt == FormatType.YOLO:
        return yolo_format.read_dataset(dataset_dir, image_dir=image_dir, label_dir=label_dir)
    elif fmt == FormatType.COCO:
        json_path = coco_format.find_coco_json(dataset_dir)
        if not json_path:
            raise FileNotFoundError(f"COCO JSON not found in {dataset_dir}")
        return coco_format.read_annotation(json_path)
    elif fmt == FormatType.VOC:
        return voc_format.read_dataset(dataset_dir, image_dir=image_dir, label_dir=label_dir)
    else:
        raise ValueError(f"Unknown format: {fmt}")


def convert_dataset(
    src_dir: str, dst_dir: str,
    src_format: str, dst_format: str,
    image_dir: str = None, label_dir: str = None,
    class_mapping: Optional[ClassMapping] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> str:
    annotations, detected_mapping = read_dataset_by_format(
        src_dir, src_format, image_dir=image_dir, label_dir=label_dir)
    if not annotations:
        raise ValueError(f"未在 {src_dir} 中找到任何 {src_format} 格式的标注数据。\n请检查目录结构是否正确。")
    if class_mapping is None:
        class_mapping = detected_mapping

    # clean output directory to avoid leftover files from previous conversions
    import shutil
    if os.path.exists(dst_dir):
        shutil.rmtree(dst_dir)
    safe_makedirs(dst_dir)

    total = len(annotations)
    for i, ann in enumerate(annotations):
        if progress_callback:
            progress_callback(i, total, os.path.basename(ann.image_path))

        stem = Path(ann.image_path).stem
        if dst_format == FormatType.YOLO:
            label_out = os.path.join(dst_dir, "labels")
            safe_makedirs(label_out)
            label_path = os.path.join(label_out, f"{stem}.txt")
            yolo_format.write_label(label_path, ann, class_mapping)
        elif dst_format == FormatType.VOC:
            label_out = os.path.join(dst_dir, "Annotations")
            safe_makedirs(label_out)
            label_path = os.path.join(label_out, f"{stem}.xml")
            voc_format.write_annotation(label_path, ann, class_mapping)

    # write format-specific metadata
    if dst_format == FormatType.YOLO:
        classes_path = os.path.join(dst_dir, "classes.txt")
        with open(classes_path, "w", encoding="utf-8") as f:
            for name in class_mapping.names:
                f.write(name + "\n")
    elif dst_format == FormatType.COCO:
        json_path = os.path.join(dst_dir, "annotations.coco.json")
        coco_format.write_annotation(json_path, annotations, class_mapping)

    if progress_callback:
        progress_callback(total, total, "完成")

    return dst_dir
