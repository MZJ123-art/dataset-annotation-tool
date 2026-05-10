import os
from pathlib import Path
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QComboBox, QPushButton, QLineEdit, QLabel,
                             QFileDialog, QTextEdit, QProgressBar, QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal
from core.converter import FormatType, detect_format, convert_dataset
from utils.file_utils import get_image_files


class ConvertWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, src_dir, dst_dir, src_fmt, dst_fmt, image_dir=None, label_dir=None):
        super().__init__()
        self.src_dir = src_dir
        self.dst_dir = dst_dir
        self.src_fmt = src_fmt
        self.dst_fmt = dst_fmt
        self.image_dir = image_dir
        self.label_dir = label_dir

    def run(self):
        try:
            convert_dataset(self.src_dir, self.dst_dir, self.src_fmt, self.dst_fmt,
                            image_dir=self.image_dir, label_dir=self.label_dir,
                            progress_callback=self.progress.emit)
            self.finished.emit(self.dst_dir)
        except Exception as e:
            self.error.emit(str(e))


class PageConvert(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # label dir (main input)
        lbl_group = QGroupBox("标签目录")
        lbl_layout = QHBoxLayout(lbl_group)
        self.lbl_dir = QLineEdit()
        self.lbl_dir.setPlaceholderText("选择标签文件所在目录...")
        btn_lbl = QPushButton("浏览")
        btn_lbl.clicked.connect(lambda: self._browse_dir(self.lbl_dir))
        lbl_layout.addWidget(self.lbl_dir)
        lbl_layout.addWidget(btn_lbl)
        layout.addWidget(lbl_group)

        # image dir (only needed for YOLO source, to get image dimensions)
        self.img_group = QGroupBox("图片目录（YOLO格式转出时需要，用于读取图片尺寸）")
        img_layout = QHBoxLayout(self.img_group)
        self.img_dir = QLineEdit()
        self.img_dir.setPlaceholderText("留空则自动从标签目录同级查找...")
        btn_img = QPushButton("浏览")
        btn_img.clicked.connect(lambda: self._browse_dir(self.img_dir))
        img_layout.addWidget(self.img_dir)
        img_layout.addWidget(btn_img)
        layout.addWidget(self.img_group)

        # detected format
        self.lbl_detected = QLabel("检测格式: -")
        layout.addWidget(self.lbl_detected)

        # source format override
        fmt_layout = QHBoxLayout()
        fmt_layout.addWidget(QLabel("源格式:"))
        self.src_format = QComboBox()
        self.src_format.addItems(FormatType.ALL)
        self.src_format.currentTextChanged.connect(self._on_format_changed)
        fmt_layout.addWidget(self.src_format)
        fmt_layout.addWidget(QLabel("→"))
        fmt_layout.addWidget(QLabel("目标格式:"))
        self.dst_format = QComboBox()
        self.dst_format.addItems(FormatType.ALL)
        self.dst_format.setCurrentText(FormatType.COCO)
        fmt_layout.addWidget(self.dst_format)
        layout.addLayout(fmt_layout)

        # destination
        dst_group = QGroupBox("输出目录")
        dst_layout = QHBoxLayout(dst_group)
        self.dst_path = QLineEdit()
        self.dst_path.setPlaceholderText("选择输出目录...")
        btn_dst = QPushButton("浏览")
        btn_dst.clicked.connect(self._browse_dst)
        dst_layout.addWidget(self.dst_path)
        dst_layout.addWidget(btn_dst)
        layout.addWidget(dst_group)

        # convert button
        self.btn_convert = QPushButton("开始转换")
        self.btn_convert.setMinimumHeight(40)
        self.btn_convert.clicked.connect(self._start_convert)
        layout.addWidget(self.btn_convert)

        # progress
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        # log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(150)
        layout.addWidget(self.log)

        layout.addStretch()

        # connections
        self.lbl_dir.textChanged.connect(self._auto_detect)
        self._on_format_changed(self.src_format.currentText())

    def _browse_dir(self, line_edit):
        d = QFileDialog.getExistingDirectory(self, "选择目录")
        if d:
            line_edit.setText(d)

    def _browse_dst(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self.dst_path.setText(d)

    def _on_format_changed(self, fmt):
        self.img_group.setVisible(fmt == FormatType.YOLO)

    def _auto_detect(self, _=None):
        path = self.lbl_dir.text().strip()
        if not path or not os.path.isdir(path):
            self.lbl_detected.setText("检测格式: -")
            return

        fmt = detect_format(path)
        if fmt:
            self.src_format.setCurrentText(fmt)
        else:
            self.lbl_detected.setText("检测格式: 未识别")
            return

        # diagnostic (search top-level and subdirectories)
        p = Path(path)
        txt_files = [f for f in p.glob("*.txt") if f.name not in ("classes.txt", "classes.names")]
        txt_files += [f for sub in p.iterdir() if sub.is_dir() for f in sub.glob("*.txt") if f.name not in ("classes.txt", "classes.names")]
        txt_count = len(txt_files)
        xml_files = list(p.glob("*.xml"))
        xml_files += [f for sub in p.iterdir() if sub.is_dir() for f in sub.glob("*.xml")]
        xml_count = len(xml_files)
        json_count = len(list(p.glob("*.json")))
        count = max(txt_count, xml_count, json_count)

        info = f"标签文件: {count} 个"
        if fmt == FormatType.YOLO:
            img_count = len(get_image_files(self.img_dir.text().strip() or path))
            info += f" | 图片: {img_count} 张"
        self.lbl_detected.setText(f"检测格式: {fmt}  |  {info}")

    def _start_convert(self):
        lbl_dir = self.lbl_dir.text().strip()
        dst = self.dst_path.text().strip()
        if not lbl_dir or not dst:
            QMessageBox.warning(self, "提示", "请选择标签目录和输出目录")
            return
        if lbl_dir == dst:
            QMessageBox.warning(self, "提示", "标签目录和输出目录不能相同")
            return

        src_fmt = self.src_format.currentText()
        img_dir = self.img_dir.text().strip() or None
        # for YOLO source, use label dir as src_dir (for finding classes.txt etc.)
        src_dir = lbl_dir

        self.btn_convert.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.log.clear()

        self._worker = ConvertWorker(
            src_dir, dst, src_fmt, self.dst_format.currentText(),
            image_dir=img_dir, label_dir=lbl_dir)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current, total, msg):
        if total > 0:
            self.progress.setValue(int(current / total * 100))
        self.log.append(msg)

    def _on_done(self, dst_dir):
        self.progress.setValue(100)
        self.log.append(f"\n转换完成！输出目录: {dst_dir}")
        self.btn_convert.setEnabled(True)
        QMessageBox.information(self, "完成", f"转换完成！\n输出目录: {dst_dir}")

    def _on_error(self, err):
        self.log.append(f"\n错误: {err}")
        self.btn_convert.setEnabled(True)
        QMessageBox.critical(self, "错误", f"转换失败: {err}")
