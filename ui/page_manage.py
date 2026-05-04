import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLineEdit, QLabel, QFileDialog,
                             QTextEdit, QProgressBar, QSpinBox, QDoubleSpinBox,
                             QMessageBox, QCheckBox)
from PyQt6.QtCore import QThread, pyqtSignal
from core.dataset_manager import split_dataset, batch_rename
from core.validator import validate_dataset, ValidationIssue


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
        layout = QVBoxLayout(self)

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

        prefix_row = QHBoxLayout()
        prefix_row.addWidget(QLabel("前缀:"))
        self.edit_prefix = QLineEdit("img")
        prefix_row.addWidget(self.edit_prefix)
        prefix_row.addWidget(QLabel("起始编号:"))
        self.spin_start = QSpinBox()
        self.spin_start.setRange(0, 999999)
        prefix_row.addWidget(self.spin_start)
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

        self.btn_validate.setEnabled(False)
        self.log.clear()
        self.log.append("正在校验...")

        self._val_worker = ValidateWorker(img_dir, lbl_dir)
        self._val_worker.finished.connect(self._on_validate_done)
        self._val_worker.error.connect(self._on_error)
        self._val_worker.start()

    def _on_validate_done(self, issues):
        self.btn_validate.setEnabled(True)
        if not issues:
            self.log.append("校验通过！未发现问题。")
        else:
            self.log.append(f"发现 {len(issues)} 个问题:")
            for issue in issues[:100]:
                self.log.append(str(issue))
            if len(issues) > 100:
                self.log.append(f"... 还有 {len(issues)-100} 个问题")

    def _start_rename(self):
        d = self.rename_dir.text().strip()
        if not d:
            QMessageBox.warning(self, "提示", "请选择图片目录")
            return
        prefix = self.edit_prefix.text().strip() or "img"
        start = self.spin_start.value()

        self.btn_rename.setEnabled(False)
        self.log.clear()
        try:
            result = batch_rename(d, prefix=prefix, start_index=start)
            self.log.append(f"重命名完成，共 {len(result)} 个文件")
            for old, new in result[:20]:
                self.log.append(f"  {old} → {new}")
            if len(result) > 20:
                self.log.append(f"  ... 还有 {len(result)-20} 个")
        except Exception as e:
            self.log.append(f"错误: {e}")
        self.btn_rename.setEnabled(True)

    def _on_progress(self, current, total, msg):
        if total > 0:
            self.progress.setValue(int(current / total * 100))
        self.log.append(msg)

    def _on_error(self, err):
        self.log.append(f"错误: {err}")
        self.btn_split.setEnabled(True)
        self.btn_validate.setEnabled(True)
