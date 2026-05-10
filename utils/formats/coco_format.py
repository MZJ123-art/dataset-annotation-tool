import json
import os
from pathlib import Path
from typing import List, Tuple, Optional
from utils.data_model import Annotation, AnnotationObject, ClassMapping

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def read_annotation(json_path: str) -> Tuple[List[Annotation], ClassMapping]:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # build class mapping
    class_mapping = ClassMapping()
    categories = data.get("categories", [])
    for cat in categories:
        class_mapping.add(cat["name"], cat["id"])

    # build image id -> info
    images_info = {}
    for img in data.get("images", []):
        images_info[img["id"]] = img

    # group annotations by image_id
    ann_by_image: dict[int, list] = {}
    for ann in data.get("annotations", []):
        img_id = ann["image_id"]
        ann_by_image.setdefault(img_id, []).append(ann)

    annotations = []
    json_dir = Path(json_path).parent
    for img_id, img_info in images_info.items():
        img_filename = img_info["file_name"]
        # try relative to json dir
        img_path = str(json_dir / img_filename) if not os.path.isabs(img_filename) else img_filename
        w = img_info.get("width", 0)
        h = img_info.get("height", 0)

        objects = []
        for ann in ann_by_image.get(img_id, []):
            cat_id = ann["category_id"]
            cat_name = class_mapping.get_name(cat_id)
            bbox_coco = ann.get("bbox", [])  # [x, y, w, h]
            if len(bbox_coco) == 4:
                x, y, bw, bh = bbox_coco
                objects.append(AnnotationObject(
                    class_name=cat_name, class_id=cat_id,
                    bbox=[x, y, x + bw, y + bh],
                    confidence=ann.get("score")
                ))
            else:
                objects.append(AnnotationObject(
                    class_name=cat_name, class_id=cat_id, bbox=[]
                ))

        annotations.append(Annotation(image_path=img_path, width=w, height=h, objects=objects))

    return annotations, class_mapping


def write_annotation(json_path: str, annotations: List[Annotation], class_mapping: ClassMapping):
    # build categories from mapping, or from annotations if mapping is empty
    categories = []
    seen_cats = set()
    for name in class_mapping.names:
        cid = class_mapping.get_id(name)
        categories.append({"id": cid, "name": name})
        seen_cats.add(name)

    # collect any classes from annotations that aren't in the mapping
    for ann in annotations:
        for obj in ann.objects:
            if obj.class_name not in seen_cats:
                categories.append({"id": obj.class_id, "name": obj.class_name})
                seen_cats.add(obj.class_name)

    images = []
    all_anns = []
    ann_id = 1
    for img_id, ann in enumerate(annotations):
        img_filename = Path(ann.image_path).name
        images.append({
            "id": img_id, "file_name": img_filename,
            "width": ann.width, "height": ann.height
        })
        for obj in ann.objects:
            x1, y1, x2, y2 = obj.bbox
            coco_bbox = [x1, y1, x2 - x1, y2 - y1]
            cat_id = class_mapping.get_id(obj.class_name)
            if cat_id < 0:
                cat_id = obj.class_id
            ann_entry = {
                "id": ann_id, "image_id": img_id,
                "category_id": cat_id, "bbox": coco_bbox,
                "area": coco_bbox[2] * coco_bbox[3], "iscrowd": 0
            }
            if obj.confidence is not None:
                ann_entry["score"] = obj.confidence
            all_anns.append(ann_entry)
            ann_id += 1

    coco_data = {
        "images": images,
        "annotations": all_anns,
        "categories": categories
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(coco_data, f, ensure_ascii=False, indent=2)


def _find_coco_in_dir(directory: Path) -> Optional[str]:
    """Search for COCO JSON in a single directory."""
    for name in ["annotations.json", "_annotations.coco.json", "instances.json",
                 "result.json", "annotation.json"]:
        candidate = directory / name
        if candidate.exists():
            return str(candidate)
    for f in directory.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if "images" in data and "annotations" in data:
                return str(f)
        except (json.JSONDecodeError, KeyError):
            continue
    return None


def find_coco_json(dataset_dir: str, max_depth: int = 3) -> Optional[str]:
    p = Path(dataset_dir)
    result = _find_coco_in_dir(p)
    if result:
        return result
    if max_depth <= 0:
        return None
    for subdir in sorted(p.iterdir()):
        if subdir.is_dir():
            result = _find_coco_in_dir(subdir)
            if result:
                return result
    if max_depth > 1:
        for subdir in sorted(p.iterdir()):
            if subdir.is_dir():
                result = find_coco_json(str(subdir), max_depth - 1)
                if result:
                    return result
    return None
