import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLineEdit, QLabel, QFileDialog,
                             QTextEdit, QProgressBar, QSpinBox, QDoubleSpinBox,
                             QMessageBox, QCheckBox, QScrollArea, QFrame)
from PyQt6.QtCore import QThread, pyqtSignal
from core.dataset_manager import (split_dataset, batch_rename, plan_rename,
                                  count_previous_splits)
from core.validator import validate_dataset, ValidationIssue
from utils.file_utils import check_dir_conflict
from utils.formats.yolo_format import load_class_mapping


class SplitWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, image_dir, label_dir, output_dir, ratios):
        super().__init__()
        self.image_dir = image_dir
        self.label_dir = label_dir
        self.output_dir = output_dir
        self.ratios = ratios

    def run(self):
        try:
            result = split_dataset(
                self.image_dir, self.label_dir, self.output_dir,
                *self.ratios, progress_callback=self.progress.emit
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ValidateWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, image_dir, label_dir, class_names=None):
        super().__init__()
        self.image_dir = image_dir
        self.label_dir = label_dir
        self.class_names = class_names

    def run(self):
        try:
            issues = validate_dataset(self.image_dir, self.label_dir, self.class_names)
            self.finished.emit(issues)
        except Exception as e:
            self.error.emit(str(e))


class PageManage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # dataset split
        split_group = QGroupBox("数据集拆分 (train/val/test)")
        split_layout = QVBoxLayout(split_group)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("图片目录:"))
        self.split_img_dir = QLineEdit()
        btn_img = QPushButton("浏览")
        btn_img.clicked.connect(lambda: self._browse_dir(self.split_img_dir))
        dir_row.addWidget(self.split_img_dir)
        dir_row.addWidget(btn_img)
        split_layout.addLayout(dir_row)

        dir_row2 = QHBoxLayout()
        dir_row2.addWidget(QLabel("标签目录:"))
        self.split_lbl_dir = QLineEdit()
        btn_lbl = QPushButton("浏览")
        btn_lbl.clicked.connect(lambda: self._browse_dir(self.split_lbl_dir))
        dir_row2.addWidget(self.split_lbl_dir)
        dir_row2.addWidget(btn_lbl)
        split_layout.addLayout(dir_row2)

        dir_row3 = QHBoxLayout()
        dir_row3.addWidget(QLabel("输出目录:"))
        self.split_out_dir = QLineEdit()
        btn_out = QPushButton("浏览")
        btn_out.clicked.connect(lambda: self._browse_dir(self.split_out_dir))
        dir_row3.addWidget(self.split_out_dir)
        dir_row3.addWidget(btn_out)
        split_layout.addLayout(dir_row3)

        ratio_row = QHBoxLayout()
        ratio_row.addWidget(QLabel("训练集:"))
        self.spin_train = QDoubleSpinBox()
        self.spin_train.setRange(0, 1)
        self.spin_train.setValue(0.7)
        self.spin_train.setSingleStep(0.05)
        ratio_row.addWidget(self.spin_train)
        ratio_row.addWidget(QLabel("验证集:"))
        self.spin_val = QDoubleSpinBox()
        self.spin_val.setRange(0, 1)
        self.spin_val.setValue(0.2)
        self.spin_val.setSingleStep(0.05)
        ratio_row.addWidget(self.spin_val)
        ratio_row.addWidget(QLabel("测试集:"))
        self.spin_test = QDoubleSpinBox()
        self.spin_test.setRange(0, 1)
        self.spin_test.setValue(0.1)
        self.spin_test.setSingleStep(0.05)
        ratio_row.addWidget(self.spin_test)
        split_layout.addLayout(ratio_row)

        self.btn_split = QPushButton("开始拆分")
        self.btn_split.setMinimumHeight(36)
        self.btn_split.clicked.connect(self._start_split)
        split_layout.addWidget(self.btn_split)
        layout.addWidget(split_group)

        # validate
        val_group = QGroupBox("数据集校验")
        val_layout = QVBoxLayout(val_group)

        val_dir_row = QHBoxLayout()
        val_dir_row.addWidget(QLabel("图片目录:"))
        self.val_img_dir = QLineEdit()
        btn_val_img = QPushButton("浏览")
        btn_val_img.clicked.connect(lambda: self._browse_dir(self.val_img_dir))
        val_dir_row.addWidget(self.val_img_dir)
        val_dir_row.addWidget(btn_val_img)
        val_layout.addLayout(val_dir_row)

        val_dir_row2 = QHBoxLayout()
        val_dir_row2.addWidget(QLabel("标签目录:"))
        self.val_lbl_dir = QLineEdit()
        btn_val_lbl = QPushButton("浏览")
        btn_val_lbl.clicked.connect(lambda: self._browse_dir(self.val_lbl_dir))
        val_dir_row2.addWidget(self.val_lbl_dir)
        val_dir_row2.addWidget(btn_val_lbl)
        val_layout.addLayout(val_dir_row2)

        self.btn_validate = QPushButton("开始校验")
        self.btn_validate.setMinimumHeight(36)
        self.btn_validate.clicked.connect(self._start_validate)
        val_layout.addWidget(self.btn_validate)
        layout.addWidget(val_group)

        # rename
        rename_group = QGroupBox("批量重命名")
        rename_layout = QVBoxLayout(rename_group)
        rename_dir_row = QHBoxLayout()
        rename_dir_row.addWidget(QLabel("图片目录:"))
        self.rename_dir = QLineEdit()
        btn_rename = QPushButton("浏览")
        btn_rename.clicked.connect(lambda: self._browse_dir(self.rename_dir))
        rename_dir_row.addWidget(self.rename_dir)
        rename_dir_row.addWidget(btn_rename)
        rename_layout.addLayout(rename_dir_row)

        rename_label_row = QHBoxLayout()
        rename_label_row.addWidget(QLabel("标签目录:"))
        self.rename_label_dir = QLineEdit()
        self.rename_label_dir.setPlaceholderText("留空则自动查找同级 labels/ 目录")
        btn_rename_label = QPushButton("浏览")
        btn_rename_label.clicked.connect(lambda: self._browse_dir(self.rename_label_dir))
        rename_label_row.addWidget(self.rename_label_dir)
        rename_label_row.addWidget(btn_rename_label)
        rename_layout.addLayout(rename_label_row)

        prefix_row = QHBoxLayout()
        prefix_row.addWidget(QLabel("前缀:"))
        self.edit_prefix = QLineEdit("img")
        prefix_row.addWidget(self.edit_prefix)
        prefix_row.addWidget(QLabel("起始编号:"))
        self.spin_start = QSpinBox()
        self.spin_start.setRange(0, 999999)
        prefix_row.addWidget(self.spin_start)
        self.btn_preview_rename = QPushButton("预览")
        self.btn_preview_rename.clicked.connect(self._preview_rename)
        prefix_row.addWidget(self.btn_preview_rename)
        self.btn_rename = QPushButton("开始重命名")
        self.btn_rename.clicked.connect(self._start_rename)
        prefix_row.addWidget(self.btn_rename)
        rename_layout.addLayout(prefix_row)
        layout.addWidget(rename_group)

        # progress & log
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        layout.addWidget(self.log)

        layout.addStretch()

    def _browse_dir(self, line_edit):
        d = QFileDialog.getExistingDirectory(self, "选择目录")
        if d:
            line_edit.setText(d)

    def _start_split(self):
        img_dir = self.split_img_dir.text().strip()
        lbl_dir = self.split_lbl_dir.text().strip()
        out_dir = self.split_out_dir.text().strip()
        if not all([img_dir, lbl_dir, out_dir]):
            QMessageBox.warning(self, "提示", "请填写所有目录")
            return

        t, v, te = self.spin_train.value(), self.spin_val.value(), self.spin_test.value()
        total = t + v + te
        if abs(total - 1.0) > 0.01:
            QMessageBox.warning(self, "提示", f"比例之和应为1.0，当前为{total:.2f}")
            return

        # 输出目录与输入冲突检查 + 上次拆分的残留提示
        try:
            check_dir_conflict(img_dir, out_dir, "图片目录")
            check_dir_conflict(lbl_dir, out_dir, "标签目录")
        except ValueError as e:
            QMessageBox.warning(self, "提示", str(e))
            return

        stale = count_previous_splits(out_dir)
        if stale:
            reply = QMessageBox.question(
                self, "输出目录已有拆分结果",
                f"输出目录里还有上次拆分留下的 {stale} 个文件：\n{out_dir}\n\n"
                "继续会先清理它们（只清理 train/val/test 下的 images、labels），是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.btn_split.setEnabled(False)
        self.progress.setVisible(True)
        self.log.clear()

        self._split_worker = SplitWorker(img_dir, lbl_dir, out_dir, (t, v, te))
        self._split_worker.progress.connect(self._on_progress)
        self._split_worker.finished.connect(self._on_split_done)
        self._split_worker.error.connect(self._on_error)
        self._split_worker.start()

    def _on_split_done(self, result):
        self.progress.setValue(100)
        self.log.append(f"拆分完成: train={result.get('train',0)}, val={result.get('val',0)}, test={result.get('test',0)}")
        self.btn_split.setEnabled(True)

    def _start_validate(self):
        img_dir = self.val_img_dir.text().strip()
        lbl_dir = self.val_lbl_dir.text().strip()
        if not all([img_dir, lbl_dir]):
            QMessageBox.warning(self, "提示", "请填写图片和标签目录")
            return

        # 传入类别表，才能检查出“未知类别”（否则这项检查只能被跳过）
        mapping = load_class_mapping(lbl_dir, img_dir)
        class_names = mapping.names if mapping else None

        self.btn_validate.setEnabled(False)
        self.log.clear()
        self.log.append("正在校验..." + (f"（类别表: {len(class_names)} 类）" if class_names else "（未找到类别表，跳过未知类别检查）"))

        self._val_worker = ValidateWorker(img_dir, lbl_dir, class_names)
        self._val_worker.finished.connect(self._on_validate_done)
        self._val_worker.error.connect(self._on_error)
        self._val_worker.start()

    def _on_validate_done(self, issues):
        self.btn_validate.setEnabled(True)
        self.log.clear()
        if not issues:
            self.log.append("校验通过！未发现问题。")
        else:
            self.log.append(f"发现 {len(issues)} 个问题:")
            for issue in issues:
                self.log.append(str(issue))

    def _start_rename(self):
        d = self.rename_dir.text().strip()
        if not d:
            QMessageBox.warning(self, "提示", "请选择图片目录")
            return
        prefix = self.edit_prefix.text().strip() or "img"
        start = self.spin_start.value()

        # resolve label dir
        label_dir = self.rename_label_dir.text().strip()
        if not label_dir:
            # auto-detect: try sibling labels/ directory
            parent = os.path.dirname(d)
            candidate = os.path.join(parent, "labels")
            if os.path.isdir(candidate):
                label_dir = candidate
            elif os.path.isdir(os.path.join(d, "labels")):
                label_dir = os.path.join(d, "labels")

        self.btn_rename.setEnabled(False)
        self.log.clear()
        try:
            plan, conflicts = plan_rename(d, label_dir or None, prefix, start)
            self.log.append(f"将重命名 {len(plan)} 个文件（前缀 {prefix}_，起始 {start}）")
            if conflicts:
                self.log.append(f"⚠ 发现 {len(conflicts)} 个命名冲突，已阻止执行：")
                for c in conflicts[:20]:
                    self.log.append(f"    {c}")
                self.log.append("请修改前缀或起始编号后重试。")
                self.btn_rename.setEnabled(True)
                return
            self.log.append("未发现冲突。")

            reply = QMessageBox.question(
                self, "确认重命名",
                f"将重命名 {len(plan)} 个文件（图片和标签会一起改）。\n"
                f"示例: {plan[0]['old_img'].split(os.sep)[-1]} → {plan[0]['new_img'].split(os.sep)[-1]}\n\n"
                "重命名不可自动撤销，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                self.log.append("已取消。")
                self.btn_rename.setEnabled(True)
                return

            result = batch_rename(d, label_dir=label_dir or None, prefix=prefix, start_index=start)
            self.log.append(f"重命名完成，共 {len(result)} 个文件")
            if label_dir:
                self.log.append(f"标签目录: {label_dir}")
            for old, new in result[:20]:
                self.log.append(f"  {old} → {new}")
            if len(result) > 20:
                self.log.append(f"  ... 还有 {len(result)-20} 个")
        except Exception as e:
            self.log.append(f"错误: {e}")
        self.btn_rename.setEnabled(True)

    def _preview_rename(self):
        """只预览重命名结果和冲突，不改动任何文件。"""
        d = self.rename_dir.text().strip()
        if not d:
            QMessageBox.warning(self, "提示", "请选择图片目录")
            return
        label_dir = self.rename_label_dir.text().strip()
        if not label_dir:
            parent = os.path.dirname(d)
            for candidate in (os.path.join(parent, "labels"), os.path.join(d, "labels")):
                if os.path.isdir(candidate):
                    label_dir = candidate
                    break
        prefix = self.edit_prefix.text().strip() or "img"
        try:
            plan, conflicts = plan_rename(d, label_dir or None, prefix, self.spin_start.value())
        except Exception as e:  # noqa: BLE001
            self.log.clear()
            self.log.append(f"预览失败: {e}")
            return

        self.log.clear()
        self.log.append(f"预览：{len(plan)} 个文件将被重命名（前缀 {prefix}_，起始 {self.spin_start.value()}）")
        for item in plan[:20]:
            self.log.append(f"  {os.path.basename(item['old_img'])} → {os.path.basename(item['new_img'])}")
        if len(plan) > 20:
            self.log.append(f"  ... 还有 {len(plan)-20} 个")
        if conflicts:
            self.log.append(f"⚠ 发现 {len(conflicts)} 个命名冲突（执行会被阻止）：")
            for c in conflicts[:20]:
                self.log.append(f"    {c}")
        else:
            self.log.append("未发现命名冲突。")

    def _on_progress(self, current, total, msg):
        if total > 0:
            self.progress.setValue(int(current / total * 100))
        self.log.append(msg)

    def _on_error(self, err):
        self.log.clear()
        self.log.append(f"错误: {err}")
        self.btn_split.setEnabled(True)
        self.btn_validate.setEnabled(True)
