import os
from pathlib import Path
from typing import List, Dict
from utils.file_utils import get_image_files, find_label_for_image
from utils.formats.yolo_format import read_label
from utils.image_utils import get_image_size


def _collect_labels_recursive(directory: Path, result: list, max_depth: int = 3):
    """Collect .txt label files from directory and subdirectories."""
    for f in sorted(directory.glob("*.txt")):
        result.append(f)
    if max_depth <= 0:
        return
    for subdir in sorted(directory.iterdir()):
        if subdir.is_dir():
            _collect_labels_recursive(subdir, result, max_depth - 1)


class ValidationIssue:
    def __init__(self, file_path: str, issue_type: str, message: str, severity: str = "warning"):
        self.file_path = file_path
        self.issue_type = issue_type
        self.message = message
        self.severity = severity  # "error", "warning", "info"

    def __str__(self):
        return f"[{self.severity.upper()}] {self.file_path}: {self.message}"


def validate_dataset(
    image_dir: str,
    label_dir: str,
    class_names: List[str] = None
) -> List[ValidationIssue]:
    issues = []
    images = get_image_files(image_dir)

    for img_path in images:
        stem = Path(img_path).stem
        label_path = find_label_for_image(img_path, label_dir)

        # check if label exists
        if not label_path:
            issues.append(ValidationIssue(img_path, "missing_label", "图片无对应标签文件", "warning"))
            continue

        # check if label is empty
        if os.path.getsize(label_path) == 0:
            issues.append(ValidationIssue(label_path, "empty_label", "标签文件为空", "warning"))
            continue

        # check YOLO format
        if label_path.endswith(".txt"):
            try:
                w, h = get_image_size(img_path)
                objects = read_label(label_path, w, h)
                for obj in objects:
                    x1, y1, x2, y2 = obj.bbox
                    if x1 < 0 or y1 < 0 or x2 > w or y2 > h:
                        issues.append(ValidationIssue(
                            label_path, "out_of_bounds",
                            f"框坐标越界: [{x1:.1f},{y1:.1f},{x2:.1f},{y2:.1f}] 图片尺寸[{w},{h}]",
                            "error"
                        ))
                    if x2 <= x1 or y2 <= y1:
                        issues.append(ValidationIssue(
                            label_path, "invalid_bbox",
                            f"无效框尺寸: [{x1:.1f},{y1:.1f},{x2:.1f},{y2:.1f}]",
                            "error"
                        ))
                    if class_names and obj.class_name not in class_names:
                        issues.append(ValidationIssue(
                            label_path, "unknown_class",
                            f"未知类别: '{obj.class_name}'",
                            "warning"
                        ))
            except Exception as e:
                issues.append(ValidationIssue(label_path, "parse_error", f"解析失败: {e}", "error"))

    # check for orphan labels (search up to 3 levels deep)
    label_files = []
    _collect_labels_recursive(Path(label_dir), label_files, max_depth=3)
    image_stems = {Path(f).stem for f in images}
    for lf in label_files:
        if lf.name == "classes.txt":
            continue
        if lf.stem not in image_stems:
            issues.append(ValidationIssue(str(lf), "orphan_label", "标签文件无对应图片", "warning"))

    return issues
