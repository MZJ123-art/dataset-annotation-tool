import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from typing import List, Tuple, Optional
from utils.data_model import Annotation, AnnotationObject, ClassMapping

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def find_image_for_xml(xml_path: str) -> Optional[str]:
    stem = Path(xml_path).stem
    parent = Path(xml_path).parent
    for img_dir in [parent / "JPEGImages", parent / "images",
                    parent.parent / "JPEGImages", parent.parent / "images", parent]:
        if img_dir.is_dir():
            for ext in IMAGE_EXTS:
                for suffix in [ext, ext.upper()]:
                    img_path = img_dir / f"{stem}{suffix}"
                    if img_path.exists():
                        return str(img_path)
    return None


def read_annotation(xml_path: str) -> Tuple[Optional[Annotation], ClassMapping]:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # parse size
    size_elem = root.find("size")
    w = int(size_elem.find("width").text) if size_elem is not None and size_elem.find("width") is not None else 0
    h = int(size_elem.find("height").text) if size_elem is not None and size_elem.find("height") is not None else 0

    # find image
    filename_elem = root.find("filename")
    img_path = None
    if filename_elem is not None:
        parent = Path(xml_path).parent
        for img_dir in [parent / "JPEGImages", parent / "images",
                        parent.parent / "JPEGImages", parent.parent / "images", parent]:
            candidate = img_dir / filename_elem.text
            if candidate.exists():
                img_path = str(candidate)
                break
    if not img_path:
        img_path = find_image_for_xml(xml_path)
    if not img_path:
        return None, ClassMapping()

    class_mapping = ClassMapping()
    objects = []
    class_id_counter = 0
    name_to_id: dict[str, int] = {}

    for obj_elem in root.findall("object"):
        name_elem = obj_elem.find("name")
        class_name = name_elem.text if name_elem is not None else "unknown"
        if class_name not in name_to_id:
            name_to_id[class_name] = class_id_counter
            class_mapping.add(class_name, class_id_counter)
            class_id_counter += 1
        class_id = name_to_id[class_name]

        bndbox = obj_elem.find("bndbox")
        if bndbox is not None:
            x1 = float(bndbox.find("xmin").text)
            y1 = float(bndbox.find("ymin").text)
            x2 = float(bndbox.find("xmax").text)
            y2 = float(bndbox.find("ymax").text)
            objects.append(AnnotationObject(
                class_name=class_name, class_id=class_id,
                bbox=[x1, y1, x2, y2]
            ))

    return Annotation(image_path=img_path, width=w, height=h, objects=objects), class_mapping


def write_annotation(xml_path: str, annotation: Annotation, class_mapping: ClassMapping):
    root = ET.Element("annotation")

    folder = ET.SubElement(root, "folder")
    folder.text = str(Path(annotation.image_path).parent.name)

    filename = ET.SubElement(root, "filename")
    filename.text = Path(annotation.image_path).name

    size = ET.SubElement(root, "size")
    ET.SubElement(size, "width").text = str(annotation.width)
    ET.SubElement(size, "height").text = str(annotation.height)
    ET.SubElement(size, "depth").text = "3"

    for obj in annotation.objects:
        obj_elem = ET.SubElement(root, "object")
        ET.SubElement(obj_elem, "name").text = obj.class_name
        ET.SubElement(obj_elem, "pose").text = "Unspecified"
        ET.SubElement(obj_elem, "truncated").text = "0"
        ET.SubElement(obj_elem, "difficult").text = "0"

        bndbox = ET.SubElement(obj_elem, "bndbox")
        x1, y1, x2, y2 = obj.bbox
        ET.SubElement(bndbox, "xmin").text = str(int(round(x1)))
        ET.SubElement(bndbox, "ymin").text = str(int(round(y1)))
        ET.SubElement(bndbox, "xmax").text = str(int(round(x2)))
        ET.SubElement(bndbox, "ymax").text = str(int(round(y2)))

    xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(xml_str)


def read_dataset(dataset_dir: str) -> Tuple[List[Annotation], ClassMapping]:
    dataset_path = Path(dataset_dir)
    ann_dir = dataset_path / "Annotations" if (dataset_path / "Annotations").is_dir() else dataset_path

    all_annotations = []
    class_mapping = ClassMapping()
    name_to_id: dict[str, int] = {}
    cid = 0

    for xml_file in sorted(ann_dir.glob("*.xml")):
        ann, _ = read_annotation(str(xml_file))
        if ann is None:
            continue
        for obj in ann.objects:
            if obj.class_name not in name_to_id:
                name_to_id[obj.class_name] = cid
                class_mapping.add(obj.class_name, cid)
                cid += 1
            obj.class_id = name_to_id[obj.class_name]
        all_annotations.append(ann)

    return all_annotations, class_mapping
