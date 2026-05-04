import os
from pathlib import Path
from typing import Callable, Optional, List
from utils.data_model import Annotation, AnnotationObject, ClassMapping
from utils.formats import yolo_format
from utils.file_utils import safe_makedirs, get_image_files


class AutoAnnotator:
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.model_path = model_path
        self._loaded = False

    def load_model(self, model_path: Optional[str] = None):
        if model_path:
            self.model_path = model_path
        from ultralytics import YOLO
        self.model = YOLO(self.model_path)
        self._loaded = True

    def get_class_names(self) -> list[str]:
        if not self._loaded:
            return []
        return list(self.model.names.values())

    def annotate_image(
        self, image_path: str, conf_threshold: float = 0.25
    ) -> Annotation:
        if not self._loaded:
            self.load_model()

        from PIL import Image
        with Image.open(image_path) as img:
            w, h = img.size

        results = self.model(image_path, conf=conf_threshold, verbose=False)
        objects = []
        for result in results:
            for box in result.boxes:
                cls_id = int(box.cls[0])
                cls_name = self.model.names[cls_id]
                conf = float(box.conf[0])
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                objects.append(AnnotationObject(
                    class_name=cls_name, class_id=cls_id,
                    bbox=[x1, y1, x2, y2], confidence=conf
                ))

        return Annotation(image_path=image_path, width=w, height=h, objects=objects)

    def annotate_directory(
        self,
        image_dir: str,
        output_dir: str,
        conf_threshold: float = 0.25,
        output_format: str = "yolo",
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[Annotation]:
        if not self._loaded:
            self.load_model()

        image_files = get_image_files(image_dir)
        safe_makedirs(output_dir)

        class_mapping = ClassMapping.from_names(self.get_class_names())
        annotations = []

        for i, img_path in enumerate(image_files):
            if progress_callback:
                progress_callback(i, len(image_files), os.path.basename(img_path))

            ann = self.annotate_image(img_path, conf_threshold)
            annotations.append(ann)

            stem = Path(img_path).stem
            if output_format == "yolo":
                label_path = os.path.join(output_dir, f"{stem}.txt")
                yolo_format.write_label(label_path, ann, class_mapping)

        # write classes file
        if output_format == "yolo":
            classes_path = os.path.join(output_dir, "classes.txt")
            with open(classes_path, "w", encoding="utf-8") as f:
                for name in self.get_class_names():
                    f.write(name + "\n")

        if progress_callback:
            progress_callback(len(image_files), len(image_files), "完成")

        return annotations
