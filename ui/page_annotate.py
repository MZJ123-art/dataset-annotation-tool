import os
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLineEdit, QLabel, QFileDialog,
                             QListWidget, QComboBox, QMessageBox, QSplitter,
                             QInputDialog)
from PyQt6.QtCore import Qt
from utils.file_utils import get_image_files, find_label_for_image
from utils.formats.yolo_format import read_label, write_label
from utils.formats.voc_format import read_annotation as read_voc, write_annotation as write_voc
from utils.image_utils import get_image_size
from utils.data_model import Annotation, AnnotationObject, ClassMapping
from core.dataset_manager import delete_image_and_label
from ui.widgets.image_viewer import ImageViewer, BoundingBox, get_color_for_class
from ui.widgets.label_list import LabelListWidget


class PageAnnotate(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._base_dir = ""
        self._image_dir = ""
        self._label_dir = ""
        self._image_files = []
        self._current_idx = -1
        self._class_names = []
        self._class_mapping = ClassMapping()
        self._splits = []  # detected splits: [(name, img_dir, lbl_dir), ...]
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # toolbar
        toolbar = QHBoxLayout()
        self.btn_open_dir = QPushButton("打开数据集目录")
        self.btn_open_dir.clicked.connect(self._open_image_dir)
        toolbar.addWidget(self.btn_open_dir)
        toolbar.addStretch()

        self.lbl_current = QLabel("当前: -")
        toolbar.addWidget(self.lbl_current)
        main_layout.addLayout(toolbar)

        # path bar
        path_bar = QHBoxLayout()
        self.btn_back = QPushButton("返回上级")
        self.btn_back.clicked.connect(self._go_back)
        self.btn_back.setEnabled(False)
        self.lbl_path = QLabel("")
        path_bar.addWidget(self.btn_back)
        path_bar.addWidget(self.lbl_path, 1)
        main_layout.addLayout(path_bar)

        # main content: file list | image viewer | label panel
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # left: file list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(2, 2, 2, 2)
        left_layout.setSpacing(4)

        self.file_list = QListWidget()
        self.file_list.currentRowChanged.connect(self._on_file_selected)
        left_layout.addWidget(QLabel("文件列表"))
        left_layout.addWidget(self.file_list, 1)

        # class selector
        cls_row = QHBoxLayout()
        cls_row.setSpacing(2)
        cls_row.addWidget(QLabel("类别:"))
        self.combo_class = QComboBox()
        self.combo_class.setEditable(True)
        self.combo_class.currentTextChanged.connect(self._on_class_changed)
        cls_row.addWidget(self.combo_class, 1)
        left_layout.addLayout(cls_row)

        # compact buttons
        btn_h = 28
        btn_add_cls = QPushButton("+ 添加类别")
        btn_add_cls.setFixedHeight(btn_h)
        btn_add_cls.clicked.connect(self._add_class)
        left_layout.addWidget(btn_add_cls)

        self.btn_draw = QPushButton("绘制框 (W)")
        self.btn_draw.setCheckable(True)
        self.btn_draw.setFixedHeight(btn_h)
        self.btn_draw.toggled.connect(self._toggle_draw_mode)
        left_layout.addWidget(self.btn_draw)

        nav_row = QHBoxLayout()
        nav_row.setSpacing(2)
        self.btn_prev = QPushButton("上一张(A)")
        self.btn_prev.setFixedHeight(btn_h)
        self.btn_prev.clicked.connect(self._prev_image)
        self.btn_next = QPushButton("下一张(D)")
        self.btn_next.setFixedHeight(btn_h)
        self.btn_next.clicked.connect(self._next_image)
        nav_row.addWidget(self.btn_prev)
        nav_row.addWidget(self.btn_next)
        left_layout.addLayout(nav_row)

        self.btn_delete_img = QPushButton("删除(Ctrl+Del)")
        self.btn_delete_img.setFixedHeight(btn_h)
        self.btn_delete_img.clicked.connect(self._delete_current_image)
        left_layout.addWidget(self.btn_delete_img)


        splitter.addWidget(left_panel)

        # center: image viewer
        self.viewer = ImageViewer()
        self.viewer.box_created.connect(self._on_box_created)
        self.viewer.box_selected.connect(self._on_box_selected)
        self.viewer.box_deleted.connect(self._on_box_deleted)
        self.viewer.box_moved.connect(self._on_box_moved)
        self.viewer.image_dropped.connect(self._on_image_dropped)
        splitter.addWidget(self.viewer)

        # right: label list
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(2, 2, 2, 2)
        right_layout.setSpacing(4)
        right_layout.addWidget(QLabel("标注列表"))
        self.label_list = LabelListWidget()
        self.label_list.selection_changed.connect(self._on_label_selected)
        self.label_list.multi_selection_changed.connect(self._on_label_multi_selected)
        self.label_list.class_changed.connect(self._on_label_class_changed)
        self.label_list.delete_requested.connect(self._on_label_delete)
        right_layout.addWidget(self.label_list)
        splitter.addWidget(right_panel)

        left_panel.setMinimumWidth(120)
        left_panel.setMaximumWidth(220)
        right_panel.setMinimumWidth(120)
        right_panel.setMaximumWidth(220)
        splitter.setSizes([150, 800, 160])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        main_layout.addWidget(splitter, 1)

        # status
        self.lbl_status = QLabel("")
        main_layout.addWidget(self.lbl_status)

    def keyPressEvent(self, event):
        key = event.key()
        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        if ctrl and key == Qt.Key.Key_Delete:
            self._delete_current_image()
        elif key == Qt.Key.Key_W:
            self.btn_draw.setChecked(not self.btn_draw.isChecked())
        elif key == Qt.Key.Key_D:
            self._next_image()
        elif key == Qt.Key.Key_A:
            self._prev_image()
        else:
            super().keyPressEvent(event)

    def _detect_dataset_structure(self, root_dir):
        """Detect dataset directory structure.

        Returns list of (split_name, images_dir, labels_dir) tuples.
        If no splits found, returns empty list.
        """
        IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

        def _has_images(d):
            if not os.path.isdir(d):
                return False
            for f in os.listdir(d):
                if os.path.splitext(f)[1].lower() in IMAGE_EXTS:
                    return True
            return False

        def _find_labels_for_images(img_dir):
            """Find corresponding labels dir for an images dir."""
            parent = os.path.dirname(img_dir)
            basename = os.path.basename(img_dir)
            # sibling labels/ with same basename
            for candidate in [
                os.path.join(parent, "labels", basename),
                os.path.join(parent, "labels"),
                os.path.join(img_dir, "labels"),
            ]:
                if os.path.isdir(candidate):
                    return candidate
            return ""

        splits = []

        # Structure A: root/images/{split}/ + root/labels/{split}/
        images_dir = os.path.join(root_dir, "images")
        labels_dir = os.path.join(root_dir, "labels")
        if os.path.isdir(images_dir):
            subdirs = sorted([d for d in os.listdir(images_dir)
                              if os.path.isdir(os.path.join(images_dir, d))])
            if subdirs:
                for sd in subdirs:
                    img_sd = os.path.join(images_dir, sd)
                    lbl_sd = os.path.join(labels_dir, sd) if os.path.isdir(labels_dir) else ""
                    if not lbl_sd or not os.path.isdir(lbl_sd):
                        lbl_sd = _find_labels_for_images(img_sd)
                    splits.append((sd, img_sd, lbl_sd))
            elif _has_images(images_dir):
                lbl = _find_labels_for_images(images_dir)
                splits.append(("", images_dir, lbl))

        # Structure B: root/{split}/images/ + root/{split}/labels/
        if not splits:
            subdirs = sorted([d for d in os.listdir(root_dir)
                              if os.path.isdir(os.path.join(root_dir, d))
                              and d not in ("images", "labels", "Annotations")])
            found_splits = []
            for sd in subdirs:
                sd_path = os.path.join(root_dir, sd)
                img_sd = os.path.join(sd_path, "images")
                lbl_sd = os.path.join(sd_path, "labels")
                if os.path.isdir(img_sd) and _has_images(img_sd):
                    if not os.path.isdir(lbl_sd):
                        lbl_sd = _find_labels_for_images(img_sd)
                    found_splits.append((sd, img_sd, lbl_sd))
                elif _has_images(sd_path):
                    lbl = _find_labels_for_images(sd_path)
                    found_splits.append((sd, sd_path, lbl))
            if found_splits:
                splits = found_splits

        return splits

    def _open_image_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择数据集目录")
        if not d:
            return
        self._base_dir = d
        self._reset_state()
        self.lbl_path.setText(d)

        # Try to detect dataset structure
        self._splits = self._detect_dataset_structure(d)

        if self._splits:
            # Show splits as clickable entries in file list
            self._show_split_list()
        else:
            # No splits detected, try loading images directly (up to 3 levels)
            self._load_images_from_dir(d)

    def _reset_state(self):
        self._image_dir = ""
        self._label_dir = ""
        self._image_files = []
        self._current_idx = -1
        self.file_list.clear()
        self.viewer.set_boxes([])
        self.label_list.set_items([])
        self.btn_back.setEnabled(False)

    def _show_split_list(self):
        """Show detected splits as clickable entries in the file list."""
        self.file_list.blockSignals(True)
        self.file_list.clear()
        for name, img_dir, lbl_dir in self._splits:
            img_count = len(get_image_files(img_dir))
            lbl_info = "✓" if lbl_dir and os.path.isdir(lbl_dir) else "✗"
            self.file_list.addItem(f"[split] {name}  ({img_count}张 标签{lbl_info})")
        self.file_list.blockSignals(False)
        self.lbl_status.setText(f"检测到 {len(self._splits)} 个数据集分区，点击进入")

    def _load_images_from_dir(self, directory):
        """Load images from directory using deep search."""
        self._image_files = get_image_files(directory)
        if self._image_files:
            self._image_dir = directory
            self._auto_find_labels(directory)
            self.file_list.blockSignals(True)
            for f in self._image_files:
                self.file_list.addItem(os.path.basename(f))
            self.file_list.blockSignals(False)
            lbl_info = self._label_dir if self._label_dir else os.path.join(self._image_dir, "labels") + " (自动创建)"
            self.lbl_status.setText(f"已加载 {len(self._image_files)} 张图片 | 标签目录: {lbl_info}")
            self.file_list.setCurrentRow(0)
        else:
            self.lbl_status.setText("未找到图片")

    def _go_back(self):
        if not self._base_dir:
            return
        if self._current_idx >= 0:
            self._save_labels()
        self._reset_state()
        self.lbl_path.setText(self._base_dir)

        if self._splits:
            self._show_split_list()
        else:
            self._load_images_from_dir(self._base_dir)

    def _auto_find_labels(self, img_dir):
        """Auto find labels dir and load classes.

        Searches for a separate labels directory. If not found,
        leaves _label_dir empty so _save_labels will create img_dir/labels/.
        """
        self._label_dir = ""
        parent = os.path.dirname(img_dir)

        # 1. try sibling labels/ dir
        for candidate in [os.path.join(parent, "labels"), os.path.join(img_dir, "labels")]:
            if os.path.isdir(candidate):
                self._label_dir = candidate
                break

        # 2. if no separate labels dir found, leave _label_dir empty
        #    _save_labels will auto-create img_dir/labels/ for new annotations

        # load classes: check labels dir first, then image dir (for mixed folders)
        loaded = False
        search_dir = self._label_dir if self._label_dir else img_dir
        for name in ["classes.txt", "classes.names"]:
            p = os.path.join(search_dir, name)
            if os.path.exists(p):
                self._load_classes(p)
                loaded = True
                break
        if not loaded:
            self._load_classes_from_labels(search_dir)

    def _collect_txt_files(self, directory, max_depth=3):
        """Collect .txt label files up to max_depth levels deep."""
        exclude = {"classes.txt", "classes.names"}
        result = []
        for f in sorted(os.listdir(directory)):
            full = os.path.join(directory, f)
            if os.path.isfile(full) and f.endswith(".txt") and f not in exclude:
                result.append(full)
        if result or max_depth <= 0:
            return result
        for f in sorted(os.listdir(directory)):
            full = os.path.join(directory, f)
            if os.path.isdir(full):
                result.extend(self._collect_txt_files(full, max_depth - 1))
        return result

    def _load_classes_from_labels(self, label_dir):
        self._class_names = []
        self._class_mapping = ClassMapping()
        self.combo_class.clear()
        class_ids = set()
        # collect label files up to 3 levels deep
        label_files = self._collect_txt_files(label_dir, max_depth=3)
        for fpath in label_files[:200]:  # scan up to 200 files
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split()
                        if parts:
                            try:
                                class_ids.add(int(parts[0]))
                            except ValueError:
                                pass
            except Exception:
                pass
        for cid in sorted(class_ids):
            name = f"class_{cid}"
            self._class_names.append(name)
            self._class_mapping.add(name, cid)
            self.combo_class.addItem(name)
        if self._class_names:
            self.combo_class.setCurrentIndex(0)

    def _load_classes(self, path):
        self._class_names = []
        self._class_mapping = ClassMapping()
        self.combo_class.clear()
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                name = line.strip()
                if name:
                    self._class_names.append(name)
                    self._class_mapping.add(name, i)
                    self.combo_class.addItem(name)

    def _add_class(self):
        name, ok = QInputDialog.getText(self, "添加类别", "类别名:")
        if ok and name and name not in self._class_names:
            cid = len(self._class_names)
            self._class_names.append(name)
            self._class_mapping.add(name, cid)
            self.combo_class.addItem(name)
            self.combo_class.setCurrentText(name)

    def _on_class_changed(self, name):
        self.viewer.set_current_class(name)

    def _toggle_draw_mode(self, checked):
        self.viewer.set_drawing_mode(checked)

    def _on_file_selected(self, idx):
        if idx < 0:
            return
        item_text = self.file_list.item(idx).text()
        # handle split click
        if item_text.startswith("[split] "):
            if self._splits and idx < len(self._splits):
                self._load_split(idx)
            return
        # handle image file click
        if idx >= len(self._image_files):
            return
        if self._current_idx >= 0:
            self._save_labels()
        self._current_idx = idx
        img_path = self._image_files[idx]
        self.viewer.set_image(img_path)
        self._load_labels_for_current()
        self.lbl_current.setText(f"当前: {os.path.basename(img_path)} ({idx+1}/{len(self._image_files)})")

    def _load_split(self, split_idx):
        """Load images and labels for a specific split."""
        if self._current_idx >= 0:
            self._save_labels()
        name, img_dir, lbl_dir = self._splits[split_idx]
        self._image_dir = img_dir
        self._label_dir = lbl_dir if lbl_dir and os.path.isdir(lbl_dir) else img_dir
        self._image_files = get_image_files(img_dir)

        # load classes
        loaded = False
        for cname in ["classes.txt", "classes.names"]:
            p = os.path.join(self._label_dir, cname)
            if os.path.exists(p):
                self._load_classes(p)
                loaded = True
                break
        if not loaded:
            self._load_classes_from_labels(self._label_dir)

        self.file_list.blockSignals(True)
        self.file_list.clear()
        for f in self._image_files:
            self.file_list.addItem(os.path.basename(f))
        self.file_list.blockSignals(False)
        self.btn_back.setEnabled(True)
        self.lbl_path.setText(f"{self._base_dir}  ›  {name}" if name else self._base_dir)
        lbl_info = self._label_dir if self._label_dir else os.path.join(self._image_dir, "labels") + " (自动创建)"
        self.lbl_status.setText(f"已加载 {len(self._image_files)} 张图片 | 标签目录: {lbl_info}")
        self._current_idx = -1
        if self._image_files:
            self.file_list.setCurrentRow(0)

    def _load_labels_for_current(self):
        if self._current_idx < 0:
            return
        img_path = self._image_files[self._current_idx]
        label_path = find_label_for_image(img_path, self._label_dir or None)
        if not label_path:
            self.viewer.set_boxes([])
            self.label_list.set_items([])
            return

        w, h = get_image_size(img_path)
        boxes = []
        items = []

        if label_path.endswith(".txt"):
            objects = read_label(label_path, w, h, self._class_mapping)
            for obj in objects:
                color = get_color_for_class(obj.class_id)
                boxes.append(BoundingBox(*obj.bbox, obj.class_name, obj.class_id, color))
                x1, y1, x2, y2 = obj.bbox
                items.append((obj.class_name, f"[{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}]"))
        elif label_path.endswith(".xml"):
            ann, _ = read_voc(label_path)
            if ann:
                for obj in ann.objects:
                    color = get_color_for_class(obj.class_id)
                    boxes.append(BoundingBox(*obj.bbox, obj.class_name, obj.class_id, color))
                    x1, y1, x2, y2 = obj.bbox
                    items.append((obj.class_name, f"[{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}]"))

        self.viewer.set_boxes(boxes)
        self.label_list.set_items(items)

    def _save_labels(self):
        if self._current_idx < 0:
            return
        img_path = self._image_files[self._current_idx]
        w, h = get_image_size(img_path)
        stem = Path(img_path).stem

        objects = []
        for box in self.viewer._boxes:
            cls_id = self._class_mapping.get_id(box.class_name)
            if cls_id < 0:
                cls_id = 0
            objects.append(AnnotationObject(
                class_name=box.class_name, class_id=cls_id, bbox=box.to_list()
            ))
        ann = Annotation(image_path=img_path, width=w, height=h, objects=objects)

        label_dir = self._label_dir if self._label_dir else os.path.join(self._image_dir, "labels")
        os.makedirs(label_dir, exist_ok=True)
        label_path = os.path.join(label_dir, f"{stem}.txt")
        write_label(label_path, ann, self._class_mapping)

    def _on_box_created(self, x1, y1, x2, y2):
        cls_name = self.combo_class.currentText()
        cls_id = self._class_mapping.get_id(cls_name)
        if cls_id < 0:
            cls_id = 0
            if cls_name and cls_name not in self._class_names:
                self._class_names.append(cls_name)
                self._class_mapping.add(cls_name, cls_id)
                self.combo_class.addItem(cls_name)
        color = get_color_for_class(cls_id)
        self.viewer._boxes.append(BoundingBox(x1, y1, x2, y2, cls_name, cls_id, color))
        self._update_label_list()
        self._save_labels()

    def _on_box_selected(self, idx):
        self.label_list.select_indices(self.viewer._selected_indices)

    def _on_box_deleted(self):
        self._update_label_list()
        self._save_labels()

    def _on_box_moved(self, idx, x1, y1, x2, y2):
        self._save_labels()
        self._update_label_list()

    def _on_image_dropped(self, img_path):
        if self._current_idx >= 0:
            self._save_labels()
        img_dir = os.path.dirname(img_path)
        # If dropped image is from a different directory, load that directory
        if img_dir != self._image_dir:
            self._image_dir = img_dir
            self._image_files = get_image_files(img_dir)
            self._auto_find_labels(img_dir)
            self.file_list.blockSignals(True)
            self.file_list.clear()
            for f in self._image_files:
                self.file_list.addItem(os.path.basename(f))
            self.file_list.blockSignals(False)
            self.lbl_path.setText(img_dir)
            lbl_info = self._label_dir if self._label_dir else os.path.join(self._image_dir, "labels") + " (自动创建)"
            self.lbl_status.setText(f"已加载 {len(self._image_files)} 张图片 | 标签目录: {lbl_info}")
        # Select the dropped image in the list
        norm_path = os.path.normpath(img_path)
        for i, f in enumerate(self._image_files):
            if os.path.normpath(f) == norm_path:
                self.file_list.setCurrentRow(i)
                return
        # If not found in list (shouldn't happen), load directly
        self._current_idx = -1
        self.viewer.set_image(img_path)
        self.viewer.clear_boxes()
        self.lbl_current.setText(f"当前: {os.path.basename(img_path)}")

    def _on_label_selected(self, idx):
        self.viewer.select_box(idx)

    def _on_label_multi_selected(self, indices):
        self.viewer.select_boxes(indices)

    def _on_label_class_changed(self, idx, new_class):
        if 0 <= idx < len(self.viewer._boxes):
            self.viewer._boxes[idx].class_name = new_class
            if new_class not in self._class_names:
                cid = len(self._class_names)
                self._class_names.append(new_class)
                self._class_mapping.add(new_class, cid)
                self.combo_class.addItem(new_class)
            self.viewer._boxes[idx].class_id = self._class_mapping.get_id(new_class)
            self._update_label_list()
            self._save_labels()

    def _on_label_delete(self):
        indices = self.label_list.selected_indices()
        if not indices:
            return
        for idx in sorted(indices, reverse=True):
            if 0 <= idx < len(self.viewer._boxes):
                del self.viewer._boxes[idx]
        self.viewer._selected_indices.clear()
        self.viewer.update()
        self._update_label_list()
        self._save_labels()

    def _update_label_list(self):
        items = []
        for box in self.viewer._boxes:
            x1, y1, x2, y2 = box.x1, box.y1, box.x2, box.y2
            items.append((box.class_name, f"[{x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}]"))
        self.label_list.set_items(items)

    def _next_image(self):
        if self._current_idx < len(self._image_files) - 1:
            self.file_list.setCurrentRow(self._current_idx + 1)

    def _prev_image(self):
        if self._current_idx > 0:
            self.file_list.setCurrentRow(self._current_idx - 1)

    def _delete_current_image(self):
        if self._current_idx < 0:
            return
        img_path = self._image_files[self._current_idx]
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定删除 {os.path.basename(img_path)} 及其标签文件？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            delete_image_and_label(img_path, self._label_dir)
            del self._image_files[self._current_idx]
            self.file_list.takeItem(self._current_idx)
            if self._current_idx >= len(self._image_files):
                self._current_idx = len(self._image_files) - 1
            if self._current_idx >= 0:
                self.file_list.setCurrentRow(self._current_idx)
            self.lbl_status.setText(f"已删除，剩余 {len(self._image_files)} 张图片")
