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
        self._label_root = ""  # 标签主目录 (e.g. E:\labels)
        self._image_dir = ""
        self._label_dir = ""
        self._image_files = []
        self._current_idx = -1
        self._class_names = []
        self._class_mapping = ClassMapping()
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # toolbar
        toolbar = QHBoxLayout()
        self.btn_open_dir = QPushButton("打开图片目录")
        self.btn_open_dir.clicked.connect(self._open_image_dir)
        self.btn_open_label_root = QPushButton("设置标签主目录")
        self.btn_open_label_root.clicked.connect(self._set_label_root)
        self.btn_open_label = QPushButton("打开标签目录")
        self.btn_open_label.clicked.connect(self._open_label_dir)

        toolbar.addWidget(self.btn_open_dir)
        toolbar.addWidget(self.btn_open_label_root)
        toolbar.addWidget(self.btn_open_label)
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

    def _open_image_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择图片目录")
        if not d:
            return
        self._base_dir = d
        self._image_dir = ""
        self._label_dir = ""
        self._image_files = []
        self._current_idx = -1
        self.file_list.clear()
        self.viewer.set_boxes([])
        self.label_list.set_items([])
        self.btn_back.setEnabled(False)
        self.lbl_path.setText(d)

        # find subdirectories and images
        subdirs = []
        for item in sorted(os.listdir(d)):
            full = os.path.join(d, item)
            if os.path.isdir(full):
                subdirs.append(item)
            elif os.path.splitext(item)[1].lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}:
                self._image_files.append(full)

        # if has images directly, show them
        if self._image_files:
            for f in self._image_files:
                self.file_list.addItem(os.path.basename(f))
            self._image_dir = d
            self._auto_find_labels(d)
            self.lbl_status.setText(f"已加载 {len(self._image_files)} 张图片")
            if self._image_files:
                self.file_list.setCurrentRow(0)
        # if has subdirs, show them as folders
        elif subdirs:
            for sd in subdirs:
                self.file_list.addItem(f"[目录] {sd}")
            self.lbl_status.setText(f"包含 {len(subdirs)} 个子目录，点击子目录加载内容")
        else:
            self.lbl_status.setText("未找到图片或子目录")

    def _set_label_root(self):
        d = QFileDialog.getExistingDirectory(self, "选择标签主目录")
        if not d:
            return
        self._label_root = d
        self.lbl_status.setText(f"标签主目录: {d}")
        # reload labels if currently viewing images
        if self._current_idx >= 0 and self._image_dir:
            self._auto_find_labels(self._image_dir)
            self._load_labels_for_current()

    def _go_back(self):
        if not self._base_dir:
            return
        if self._current_idx >= 0:
            self._save_labels()
        self._image_dir = ""
        self._label_dir = ""
        self._image_files = []
        self._current_idx = -1
        self.file_list.clear()
        self.viewer.set_boxes([])
        self.label_list.set_items([])
        self.btn_back.setEnabled(False)
        self.lbl_path.setText(self._base_dir)

        subdirs = []
        for item in sorted(os.listdir(self._base_dir)):
            full = os.path.join(self._base_dir, item)
            if os.path.isdir(full):
                subdirs.append(item)
            elif os.path.splitext(item)[1].lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}:
                self._image_files.append(full)

        if self._image_files:
            for f in self._image_files:
                self.file_list.addItem(os.path.basename(f))
            self._image_dir = self._base_dir
            self._auto_find_labels(self._base_dir)
            self.lbl_status.setText(f"已加载 {len(self._image_files)} 张图片")
            if self._image_files:
                self.file_list.setCurrentRow(0)
        elif subdirs:
            for sd in subdirs:
                self.file_list.addItem(f"[目录] {sd}")
            self.lbl_status.setText(f"包含 {len(subdirs)} 个子目录，点击子目录加载内容")

    def _auto_find_labels(self, img_dir):
        """Auto find labels dir and load classes."""
        self._label_dir = ""
        parent = os.path.dirname(img_dir)
        basename = os.path.basename(img_dir)

        # 1. try sibling labels/ dir
        for candidate in [os.path.join(parent, "labels"), os.path.join(img_dir, "labels")]:
            if os.path.isdir(candidate):
                self._label_dir = candidate
                break

        # 2. try label_root with matching subdir name
        if not self._label_dir and self._label_root:
            candidate = os.path.join(self._label_root, basename)
            if os.path.isdir(candidate):
                self._label_dir = candidate

        # 3. try label_root directly
        if not self._label_dir and self._label_root and os.path.isdir(self._label_root):
            self._label_dir = self._label_root

        # 4. fallback to image dir
        if not self._label_dir:
            self._label_dir = img_dir

        # load classes
        loaded = False
        for name in ["classes.txt", "classes.names"]:
            p = os.path.join(self._label_dir, name)
            if os.path.exists(p):
                self._load_classes(p)
                loaded = True
                break
        if not loaded:
            self._load_classes_from_labels(self._label_dir)

    def _open_label_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择标签目录")
        if not d:
            return
        self._label_dir = d
        # if the selected dir contains subdirs, treat it as label root
        has_subdirs = any(os.path.isdir(os.path.join(d, x)) for x in os.listdir(d))
        if has_subdirs:
            self._label_root = d
        loaded = False
        for name in ["classes.txt", "classes.names"]:
            p = os.path.join(d, name)
            if os.path.exists(p):
                self._load_classes(p)
                loaded = True
                break
        if not loaded:
            self._load_classes_from_labels(d)
        if self._current_idx >= 0:
            self._load_labels_for_current()

    def _load_classes_from_labels(self, label_dir):
        self._class_names = []
        self._class_mapping = ClassMapping()
        self.combo_class.clear()
        class_ids = set()
        label_files = [f for f in os.listdir(label_dir) if f.endswith(".txt") and f not in ("classes.txt", "classes.names")]
        for fname in label_files[:200]:  # scan up to 200 files
            fpath = os.path.join(label_dir, fname)
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
        # handle subdirectory click
        if item_text.startswith("[目录] "):
            dirname = item_text[5:]  # remove "[目录] " prefix (5 chars)
            subdir = os.path.join(self._base_dir, dirname)
            self._load_subdir(subdir)
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

    def _load_subdir(self, subdir):
        if self._current_idx >= 0:
            self._save_labels()
        self._image_dir = subdir
        self._image_files = get_image_files(subdir)
        self._auto_find_labels(subdir)
        self.file_list.clear()
        for f in self._image_files:
            self.file_list.addItem(os.path.basename(f))
        self.btn_back.setEnabled(True)
        self.lbl_path.setText(subdir)
        self.lbl_status.setText(f"已加载 {len(self._image_files)} 张图片 | 标签目录: {self._label_dir}")
        self._current_idx = -1
        if self._image_files:
            self.file_list.setCurrentRow(0)

    def _load_labels_for_current(self):
        if self._current_idx < 0:
            return
        img_path = self._image_files[self._current_idx]
        label_path = find_label_for_image(img_path, self._label_dir)
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
