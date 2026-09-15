import os
import shutil
import time
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


def has_mixed_labels(img_dir: str) -> bool:
    """图片目录里是否已经存在与之同名的标签文件（图片/标签混放布局）。

    labelImg 的 YOLO 模式默认就是这种布局，属于合法结构，必须沿用而不能
    另外新建 labels/ 目录，否则原本能读到的标签会突然读不到。
    """
    d = Path(img_dir)
    if not d.is_dir():
        return False
    try:
        stems = {p.stem for p in d.glob("*.txt")
                 if p.name not in ("classes.txt", "classes.names")}
        if not stems:
            return False
        for ext in (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"):
            for p in d.glob(f"*{ext}"):
                if p.stem in stems:
                    return True
    except OSError:
        return False
    return False


def resolve_label_dir(img_dir: str, detected_label_dir: str = "") -> str:
    """解析该图片目录对应的标签目录。

    优先级：
      1. 数据集检测到的 labels 目录
      2. 同级 / 内部的 labels 目录
      3. 已经存在的"图片与标签混放"布局（沿用，不新建）
      4. 兜底 <img_dir>/labels（自动创建）

    关键点：第 4 步以前是直接返回 img_dir，导致只是翻看图片就会把标签写进
    图片所在的文件夹；现在只有第 3 步（布局本来就已经混放）才可能返回 img_dir。
    """
    if (detected_label_dir and os.path.isdir(detected_label_dir)
            and os.path.normpath(detected_label_dir) != os.path.normpath(img_dir)):
        return detected_label_dir

    parent = os.path.dirname(img_dir)
    for candidate in (os.path.join(parent, "labels"), os.path.join(img_dir, "labels")):
        if os.path.isdir(candidate):
            return candidate

    if has_mixed_labels(img_dir):
        return img_dir

    fallback = os.path.join(img_dir, "labels")
    os.makedirs(fallback, exist_ok=True)
    return fallback


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
        self._dirty = False  # 当前图片的标注是否被改动过（未改动不写盘）
        self._undo_stack = []   # Ctrl+Z 撤销栈
        self._last_state = None  # 当前图片“上一次已落盘”的框状态
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

        # 缩放 / 平移
        zoom_row = QHBoxLayout()
        zoom_row.setSpacing(2)
        self.btn_fit = QPushButton("适应窗口(F)")
        self.btn_fit.setFixedHeight(btn_h)
        self.btn_fit.clicked.connect(self._reset_zoom)
        self.lbl_zoom = QLabel("缩放: 100%")
        zoom_row.addWidget(self.btn_fit)
        zoom_row.addWidget(self.lbl_zoom)
        left_layout.addLayout(zoom_row)

        self.btn_undo = QPushButton("撤销 (Ctrl+Z)")
        self.btn_undo.setFixedHeight(btn_h)
        self.btn_undo.clicked.connect(self._undo)
        left_layout.addWidget(self.btn_undo)

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
        self.viewer.zoom_changed.connect(self._on_zoom_changed)
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

        left_panel.setMinimumWidth(155)
        left_panel.setMaximumWidth(320)
        right_panel.setMinimumWidth(155)
        right_panel.setMaximumWidth(320)
        splitter.setSizes([255, 800, 200])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        main_layout.addWidget(splitter, 1)

        # status
        self.lbl_status = QLabel("")
        main_layout.addWidget(self.lbl_status)

    def _add_file_item(self, path: str):
        """加入文件列表项，并把完整路径放进 tooltip（长文件名会被截断）。"""
        self.file_list.addItem(os.path.basename(path))
        item = self.file_list.item(self.file_list.count() - 1)
        if item is not None:
            item.setToolTip(path)

    def _fill_file_list(self):
        self.file_list.blockSignals(True)
        self.file_list.clear()
        for f in self._image_files:
            self._add_file_item(f)
        self.file_list.blockSignals(False)

    def keyPressEvent(self, event):
        key = event.key()
        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        if ctrl and key == Qt.Key.Key_Delete:
            self._delete_current_image()
        elif ctrl and key == Qt.Key.Key_Z:
            self._undo()
        elif key == Qt.Key.Key_W:
            self.btn_draw.setChecked(not self.btn_draw.isChecked())
        elif key == Qt.Key.Key_D:
            self._next_image()
        elif key == Qt.Key.Key_A:
            self._prev_image()
        elif key == Qt.Key.Key_F:
            self._reset_zoom()
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
        self._dirty = False
        self._last_state = None
        self._undo_stack.clear()
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
            self._fill_file_list()
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

        # 1b. 图片/标签混放的目录（labelImg YOLO 模式默认）：沿用原布局
        if not self._label_dir and has_mixed_labels(img_dir):
            self._label_dir = img_dir

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
        if not os.path.isdir(directory):
            return []
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

    def _persist_classes(self):
        """把当前类别表写回 labels/classes.txt。

        否则新增类别只存在于内存：标签里已经写了新的 class_id，
        但磁盘上的 classes.txt 还是旧的，下次打开类别名就会整体错位。
        """
        label_dir = self._label_dir or (os.path.join(self._image_dir, "labels") if self._image_dir else "")
        if not label_dir or not self._class_names:
            return
        try:
            os.makedirs(label_dir, exist_ok=True)
            with open(os.path.join(label_dir, "classes.txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(self._class_names) + "\n")
        except OSError:
            pass

    def _ensure_class(self, name: str) -> bool:
        """确保类别存在；返回是否是本次新增的。"""
        if not name or name in self._class_names:
            return False
        cid = len(self._class_names)
        self._class_names.append(name)
        self._class_mapping.add(name, cid)
        self.combo_class.addItem(name)
        return True

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
        if ok and name:
            name = name.strip()
            if self._ensure_class(name):
                self._persist_classes()          # 立即写回 classes.txt，避免类别错位
            if name in self._class_names:
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
        self._dirty = False  # 刚加载完，还没改动
        self._last_state = self._snapshot_boxes()   # 撤销基准
        self.lbl_current.setText(f"当前: {os.path.basename(img_path)} ({idx+1}/{len(self._image_files)})")

    def _load_split(self, split_idx):
        """Load images and labels for a specific split."""
        if self._current_idx >= 0:
            self._save_labels()
        name, img_dir, lbl_dir = self._splits[split_idx]
        self._image_dir = img_dir
        self._label_dir = resolve_label_dir(img_dir, lbl_dir)
        self._image_files = get_image_files(img_dir)

        # load classes：依次在 标签目录 / 图片目录 / 上一级 里找类别表
        loaded = False
        for cls_dir in (self._label_dir, img_dir, os.path.dirname(img_dir)):
            if not cls_dir or not os.path.isdir(cls_dir):
                continue
            for cname in ["classes.txt", "classes.names"]:
                p = os.path.join(cls_dir, cname)
                if os.path.exists(p):
                    self._load_classes(p)
                    loaded = True
                    break
            if loaded:
                break
        if not loaded:
            self._load_classes_from_labels(self._label_dir)

        self._fill_file_list()
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
        # 只是翻看图片而没有改动时不要写盘：
        # 否则每浏览一张图就会生成一个标签文件（没有标注时还会写出空文件）。
        if not self._dirty:
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
        self._dirty = False
        self._last_state = self._snapshot_boxes()

    # ---------------------------------------------------------------- 撤销
    def _snapshot_boxes(self) -> list:
        return [(b.class_name, int(b.class_id),
                 round(b.x1, 3), round(b.y1, 3), round(b.x2, 3), round(b.y2, 3))
                for b in self.viewer._boxes]

    def _push_undo_state(self):
        """在一次标注编辑生效后调用，把“编辑前”的状态压入撤销栈。"""
        if self._current_idx < 0 or self._last_state is None:
            return
        if self._snapshot_boxes() == self._last_state:
            return                       # 没有实际变化，不记
        self._undo_stack.append({
            "kind": "boxes",
            "idx": self._current_idx,
            "img": self._image_files[self._current_idx],
            "boxes": list(self._last_state),
        })
        if len(self._undo_stack) > 100:
            self._undo_stack.pop(0)

    def _push_undo_image_delete(self, img_path, label_path, moved_img, moved_label):
        self._undo_stack.append({
            "kind": "image_delete",
            "img": str(img_path),
            "label": str(label_path) if label_path else "",
            "moved_img": str(moved_img),
            "moved_label": str(moved_label) if moved_label else "",
        })
        if len(self._undo_stack) > 100:
            self._undo_stack.pop(0)

    def _undo(self):
        if not self._undo_stack:
            self.lbl_status.setText("没有可撤销的操作")
            return
        op = self._undo_stack.pop()
        if op["kind"] == "image_delete":
            self._undo_image_delete(op)
        else:
            self._undo_boxes(op)

    def _undo_boxes(self, op):
        if op["img"] in self._image_files:
            idx = self._image_files.index(op["img"])
        elif self._image_files:
            idx = min(op["idx"], len(self._image_files) - 1)
        else:
            return
        if idx != self._current_idx:
            self._dirty = False          # 避免切图时把当前改动写进别的图
            self.file_list.setCurrentRow(idx)
        boxes = [BoundingBox(x1, y1, x2, y2, name, cid, get_color_for_class(cid))
                 for name, cid, x1, y1, x2, y2 in op["boxes"]]
        self.viewer.set_boxes(boxes)
        self._update_label_list()
        self._dirty = True
        self._save_labels()
        self.lbl_status.setText(f"已撤销（{os.path.basename(op['img'])}）")

    def _undo_image_delete(self, op):
        try:
            if op["moved_img"] and os.path.exists(op["moved_img"]):
                os.makedirs(os.path.dirname(op["img"]), exist_ok=True)
                shutil.move(op["moved_img"], op["img"])
            if op["moved_label"] and os.path.exists(op["moved_label"]) and op["label"]:
                os.makedirs(os.path.dirname(op["label"]), exist_ok=True)
                shutil.move(op["moved_label"], op["label"])
        except OSError as e:
            self.lbl_status.setText(f"撤销失败: {e}")
            return
        self._image_files = get_image_files(self._image_dir)
        self._fill_file_list()
        self._current_idx = -1
        if op["img"] in self._image_files:
            self._dirty = False
            self.file_list.setCurrentRow(self._image_files.index(op["img"]))
        self.lbl_status.setText(f"已撤销删除: {os.path.basename(op['img'])}")

    # ---------------------------------------------------------------- 缩放
    def _on_zoom_changed(self, zoom: float):
        self.lbl_zoom.setText(f"缩放: {zoom * 100:.0f}%")

    def _reset_zoom(self):
        self.viewer.reset_zoom()

    def _on_box_created(self, x1, y1, x2, y2):
        cls_name = self.combo_class.currentText()
        if self._ensure_class(cls_name):
            self._persist_classes()              # 新类别立刻落盘，保持与标签一致
        cls_id = self._class_mapping.get_id(cls_name)
        if cls_id < 0:
            cls_id = 0
        color = get_color_for_class(cls_id)
        self.viewer._boxes.append(BoundingBox(x1, y1, x2, y2, cls_name, cls_id, color))
        self._update_label_list()
        self._dirty = True
        self._push_undo_state()
        self._save_labels()

    def _on_box_selected(self, idx):
        self.label_list.select_indices(self.viewer._selected_indices)

    def _on_box_deleted(self):
        self._update_label_list()
        self._dirty = True
        self._push_undo_state()
        self._save_labels()

    def _on_box_moved(self, idx, x1, y1, x2, y2):
        self._dirty = True
        self._push_undo_state()
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
            self._fill_file_list()
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
            if self._ensure_class(new_class):
                self._persist_classes()          # 新类别立刻落盘
            self.viewer._boxes[idx].class_id = self._class_mapping.get_id(new_class)
            self._update_label_list()
            self._dirty = True
            self._push_undo_state()
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
        self._dirty = True
        self._push_undo_state()
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
        idx = self._current_idx
        img_path = self._image_files[idx]
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定删除 {os.path.basename(img_path)} 及其标签文件？\n\n"
            f"（图片与标签会移入 {os.path.join(self._image_dir, '_deleted')}，"
            "可用 Ctrl+Z 撤销）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # 移到 _deleted 暂存目录而不是永久删除，这样 Ctrl+Z 能恢复
        moved_img = moved_label = ""
        try:
            trash = os.path.join(self._image_dir, "_deleted")
            os.makedirs(trash, exist_ok=True)
            stamp = time.strftime("%H%M%S")
            moved_img = os.path.join(trash, os.path.basename(img_path))
            if os.path.exists(moved_img):
                moved_img = os.path.join(trash, f"{stamp}_{os.path.basename(img_path)}")
            shutil.move(img_path, moved_img)

            label_path = find_label_for_image(img_path, self._label_dir or None)
            if label_path and os.path.exists(label_path):
                moved_label = os.path.join(trash, os.path.basename(label_path))
                if os.path.exists(moved_label):
                    moved_label = os.path.join(trash, f"{stamp}_{os.path.basename(label_path)}")
                shutil.move(label_path, moved_label)
        except OSError as e:
            self.lbl_status.setText(f"删除失败: {e}")
            return

        self._push_undo_image_delete(img_path, label_path, moved_img, moved_label)

        # takeItem() 会让 Qt 自己调整当前行（实测从 idx 跳到 idx+1）并发出
        # currentRowChanged。此时 _image_files 已经删掉一项，_current_idx 还是旧值，
        # 于是 _on_file_selected 会在错位状态下被调用，造成两个问题：
        #   1. 画面会往下多跳一张（删掉后看到的是"下下一张"）
        #   2. 若当前图片有未保存改动，会把它的框写进别的图片的标签文件
        # 因此先屏蔽信号，手动维护状态，最后再显式加载目标图片。
        self.file_list.blockSignals(True)
        del self._image_files[idx]
        self.file_list.takeItem(idx)
        self.file_list.blockSignals(False)

        self._current_idx = -1
        self._dirty = False

        if not self._image_files:
            self.viewer.clear_boxes()
            self.label_list.set_items([])
            self.lbl_current.setText("当前: -")
            self.lbl_status.setText("已删除，没有剩余图片")
            return

        # 原 idx+1 的图片删除后落到 idx 位置，所以停在 idx 就是"下一张"；
        # 删的是最后一张时退回上一张。
        target = min(idx, len(self._image_files) - 1)
        if self.file_list.currentRow() == target:
            self._on_file_selected(target)      # 行号未变不会发信号，手动加载
        else:
            self.file_list.setCurrentRow(target)  # 触发 _on_file_selected
        self.lbl_status.setText(f"已删除，剩余 {len(self._image_files)} 张图片")
