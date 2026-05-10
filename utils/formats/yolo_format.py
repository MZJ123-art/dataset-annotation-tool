import os
from pathlib import Path
from typing import List, Tuple, Optional
from utils.data_model import Annotation, AnnotationObject, ClassMapping


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def find_image_for_label(label_path: str, search_dirs: list = None) -> Optional[str]:
    stem = Path(label_path).stem
    parent = Path(label_path).parent

    candidates = []
    if search_dirs:
        candidates.extend(Path(d) for d in search_dirs)
    candidates.append(parent)
    p = parent
    for _ in range(3):
        candidates.append(p / "images")
        candidates.append(p / "JPEGImages")
        p = p.parent

    for img_dir in candidates:
        if img_dir.is_dir():
            for ext in IMAGE_EXTS:
                for suffix in [ext, ext.upper()]:
                    img_path = img_dir / f"{stem}{suffix}"
                    if img_path.exists():
                        return str(img_path)
    return None


def read_classes_file(classes_path: str) -> ClassMapping:
    mapping = ClassMapping()
    with open(classes_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            name = line.strip()
            if name:
                mapping.add(name, i)
    return mapping


def read_label(label_path: str, image_width: int, image_height: int,
               class_mapping: Optional[ClassMapping] = None) -> List[AnnotationObject]:
    objects = []
    if not os.path.exists(label_path):
        return objects
    with open(label_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 5:
                continue
            class_id = int(parts[0])
            cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            x1 = (cx - w / 2) * image_width
            y1 = (cy - h / 2) * image_height
            x2 = (cx + w / 2) * image_width
            y2 = (cy + h / 2) * image_height
            class_name = class_mapping.get_name(class_id) if class_mapping else f"class_{class_id}"
            conf = float(parts[5]) if len(parts) > 5 else None
            objects.append(AnnotationObject(
                class_name=class_name, class_id=class_id,
                bbox=[x1, y1, x2, y2], confidence=conf
            ))
    return objects


def write_label(label_path: str, annotation: Annotation, class_mapping: ClassMapping):
    lines = []
    for obj in annotation.objects:
        x1, y1, x2, y2 = obj.bbox
        w_img, h_img = annotation.width, annotation.height
        cx = ((x1 + x2) / 2) / w_img
        cy = ((y1 + y2) / 2) / h_img
        w = (x2 - x1) / w_img
        h = (y2 - y1) / h_img
        class_id = class_mapping.get_id(obj.class_name)
        if class_id < 0:
            class_id = obj.class_id
        line = f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"
        if obj.confidence is not None:
            line += f" {obj.confidence:.4f}"
        lines.append(line)
    with open(label_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n" if lines else "")


def collect_images(directory: str) -> dict:
    """Collect all images in a directory and subdirectories, return {stem: full_path}"""
    result = {}
    p = Path(directory)
    if not p.is_dir():
        return result
    for ext in IMAGE_EXTS:
        for f in p.rglob(f"*{ext}"):
            result[f.stem] = str(f)
        for f in p.rglob(f"*{ext.upper()}"):
            result[f.stem] = str(f)
    return result


def _collect_label_files(lbl_dir: Path, max_depth: int = 3) -> list:
    """Collect label txt files from directory and subdirectories (up to max_depth levels)."""
    exclude = {"classes.txt", "classes.names"}
    files = []
    for f in sorted(lbl_dir.glob("*.txt")):
        if f.name not in exclude:
            files.append(f)
    if files or max_depth <= 0:
        return files
    for subdir in sorted(lbl_dir.iterdir()):
        if subdir.is_dir():
            files.extend(_collect_label_files(subdir, max_depth - 1))
    return files


def read_dataset(dataset_dir: str, image_dir: str = None, label_dir: str = None) -> Tuple[List[Annotation], ClassMapping]:
    dataset_path = Path(dataset_dir)

    # find classes file
    class_mapping = ClassMapping()
    for search_dir in [dataset_path, Path(image_dir) if image_dir else None, Path(label_dir) if label_dir else None]:
        if search_dir and search_dir.is_dir():
            for name in ["classes.txt", "classes.names"]:
                p = search_dir / name
                if p.exists():
                    class_mapping = read_classes_file(str(p))
                    break
            if class_mapping:
                break

    # resolve label dir
    if label_dir and Path(label_dir).is_dir():
        lbl_dir = Path(label_dir)
    elif (dataset_path / "labels").is_dir():
        lbl_dir = dataset_path / "labels"
    else:
        lbl_dir = dataset_path

    # resolve image dir and build stem->path map
    img_stem_map = {}
    if image_dir and Path(image_dir).is_dir():
        img_stem_map = collect_images(image_dir)
    else:
        for candidate in [dataset_path / "images", dataset_path / "JPEGImages", dataset_path]:
            if candidate.is_dir():
                img_stem_map.update(collect_images(str(candidate)))

    # match labels to images
    annotations = []
    label_files = _collect_label_files(lbl_dir)
    for lf in label_files:
        img_path = img_stem_map.get(lf.stem)
        if not img_path:
            img_path = find_image_for_label(str(lf))
        if not img_path:
            continue
        from PIL import Image
        with Image.open(img_path) as img:
            w, h = img.size
        objects = read_label(str(lf), w, h, class_mapping)
        annotations.append(Annotation(image_path=img_path, width=w, height=h, objects=objects))

    return annotations, class_mapping
