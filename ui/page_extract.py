import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QComboBox, QPushButton, QLineEdit, QLabel,
                             QFileDialog, QTextEdit, QProgressBar, QSpinBox,
                             QDoubleSpinBox, QCheckBox, QMessageBox, QRadioButton,
                             QButtonGroup, QListWidget, QAbstractItemView)
from PyQt6.QtCore import QThread, pyqtSignal
from core.extractor import extract_frames, get_video_info, ExtractMode
from core.annotator import AutoAnnotator


class DownwardComboBox(QComboBox):
    """Combobox that always opens its dropdown downward."""
    def showPopup(self):
        from PyQt6.QtCore import QPoint, QTimer
        super().showPopup()
        # reposition popup below combobox after it appears
        popup = self.view().window()
        pos = self.mapToGlobal(QPoint(0, self.height()))
        popup.move(pos)
        QTimer.singleShot(0, lambda: popup.move(pos))


class ExtractWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, video_paths, output_dir, mode, interval, fmt):
        super().__init__()
        self.video_paths = video_paths
        self.output_dir = output_dir
        self.mode = mode
        self.interval = interval
        self.fmt = fmt

    def run(self):
        try:
            all_files = []
            for i, vp in enumerate(self.video_paths):
                self.progress.emit(i, len(self.video_paths), f"处理: {vp}")
                files = extract_frames(vp, self.output_dir, self.mode, self.interval, self.fmt,
                                       progress_callback=self.progress.emit)
                all_files.extend(files)
            self.finished.emit(all_files)
        except Exception as e:
            self.error.emit(str(e))


class PageExtract(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # video selection
        vid_group = QGroupBox("视频文件")
        vid_layout = QVBoxLayout(vid_group)
        btn_row = QHBoxLayout()
        self.btn_add_files = QPushButton("添加视频文件")
        self.btn_add_files.clicked.connect(self._add_files)
        self.btn_add_dir = QPushButton("添加视频目录")
        self.btn_add_dir.clicked.connect(self._add_dir)
        btn_row.addWidget(self.btn_add_files)
        btn_row.addWidget(self.btn_add_dir)
        vid_layout.addLayout(btn_row)

        self.video_list = QListWidget()
        self.video_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.video_list.setMaximumHeight(120)
        vid_layout.addWidget(self.video_list)

        btn_row2 = QHBoxLayout()
        self.btn_remove_selected = QPushButton("移除选中")
        self.btn_remove_selected.clicked.connect(self._remove_selected)
        self.btn_clear_all = QPushButton("清空列表")
        self.btn_clear_all.clicked.connect(self._clear_videos)
        btn_row2.addWidget(self.btn_remove_selected)
        btn_row2.addWidget(self.btn_clear_all)
        btn_row2.addStretch()
        self.lbl_videos = QLabel("共 0 个视频")
        btn_row2.addWidget(self.lbl_videos)
        vid_layout.addLayout(btn_row2)

        self.video_info = QLabel("")
        vid_layout.addWidget(self.video_info)
        layout.addWidget(vid_group)

        self._video_paths = []

        # settings
        settings_group = QGroupBox("抽帧设置")
        settings_layout = QVBoxLayout(settings_group)

        mode_layout = QHBoxLayout()
        self.radio_frame = QRadioButton("按帧间隔")
        self.radio_time = QRadioButton("按时间间隔(秒)")
        self.radio_frame.setChecked(True)
        mode_group = QButtonGroup(self)
        mode_group.addButton(self.radio_frame)
        mode_group.addButton(self.radio_time)
        mode_layout.addWidget(self.radio_frame)
        mode_layout.addWidget(self.radio_time)
        settings_layout.addLayout(mode_layout)

        row_layout = QHBoxLayout()
        row_layout.addWidget(QLabel("间隔值:"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 10000)
        self.spin_interval.setValue(10)
        row_layout.addWidget(self.spin_interval)
        row_layout.addSpacing(20)
        row_layout.addWidget(QLabel("输出格式:"))
        self.combo_fmt = DownwardComboBox()
        self.combo_fmt.addItems(["jpg", "png"])
        row_layout.addWidget(self.combo_fmt)
        row_layout.addStretch()
        settings_layout.addLayout(row_layout)

        layout.addWidget(settings_group)

        # output dir
        out_group = QGroupBox("输出目录")
        out_layout = QHBoxLayout(out_group)
        self.out_path = QLineEdit()
        self.out_path.setPlaceholderText("选择输出目录...")
        btn_out = QPushButton("浏览")
        btn_out.clicked.connect(self._browse_out)
        out_layout.addWidget(self.out_path)
        out_layout.addWidget(btn_out)
        layout.addWidget(out_group)

        # auto annotate
        self.chk_annotate = QCheckBox("抽帧后自动标注 (使用YOLOv8)")
        layout.addWidget(self.chk_annotate)

        # start button
        self.btn_start = QPushButton("开始抽帧")
        self.btn_start.setMinimumHeight(40)
        self.btn_start.clicked.connect(self._start_extract)
        layout.addWidget(self.btn_start)

        # progress
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        layout.addWidget(self.log)

        layout.addStretch()

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择视频文件", "",
            "视频文件 (*.mp4 *.avi *.mov *.mkv *.flv *.wmv *.webm)")
        if files:
            existing = {os.path.normcase(os.path.normpath(p)) for p in self._video_paths}
            added, skipped = 0, 0
            for f in files:
                nf = os.path.normcase(os.path.normpath(f))
                if nf not in existing:
                    self._video_paths.append(nf)
                    self.video_list.addItem(os.path.basename(nf))
                    existing.add(nf)
                    added += 1
                else:
                    skipped += 1
            self._update_label()
            self._show_video_info()
            if skipped > 0:
                QMessageBox.information(self, "提示", f"已跳过 {skipped} 个重复视频")

    def _add_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择视频目录")
        if d:
            from utils.file_utils import get_video_files
            files = get_video_files(d)
            existing = {os.path.normcase(os.path.normpath(p)) for p in self._video_paths}
            added, skipped = 0, 0
            for f in files:
                nf = os.path.normcase(os.path.normpath(f))
                if nf not in existing:
                    self._video_paths.append(nf)
                    self.video_list.addItem(os.path.basename(nf))
                    existing.add(nf)
                    added += 1
                else:
                    skipped += 1
            self._update_label()
            self._show_video_info()
            if skipped > 0:
                QMessageBox.information(self, "提示", f"已跳过 {skipped} 个重复视频")

    def _remove_selected(self):
        rows = sorted([i.row() for i in self.video_list.selectedIndexes()], reverse=True)
        for row in rows:
            self.video_list.takeItem(row)
            del self._video_paths[row]
        self._update_label()

    def _clear_videos(self):
        self.video_list.clear()
        self._video_paths.clear()
        self._update_label()
        self.video_info.setText("")

    def _update_label(self):
        self.lbl_videos.setText(f"共 {len(self._video_paths)} 个视频")

    def _show_video_info(self):
        if self._video_paths:
            try:
                info = get_video_info(self._video_paths[0])
                self.video_info.setText(
                    f"首个视频: {info['width']}x{info['height']}, "
                    f"FPS: {info['fps']:.1f}, "
                    f"总帧数: {info['total_frames']}, "
                    f"时长: {info['duration']:.1f}秒"
                )
            except Exception:
                self.video_info.setText("")

    def _browse_out(self):
        d = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if d:
            self.out_path.setText(d)

    def _start_extract(self):
        if not self._video_paths:
            QMessageBox.warning(self, "提示", "请先添加视频文件")
            return
        out = self.out_path.text().strip()
        if not out:
            QMessageBox.warning(self, "提示", "请选择输出目录")
            return

        mode = ExtractMode.BY_FRAME if self.radio_frame.isChecked() else ExtractMode.BY_TIME
        interval = self.spin_interval.value()
        fmt = self.combo_fmt.currentText()

        self.btn_start.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.log.clear()

        self._worker = ExtractWorker(self._video_paths, out, mode, interval, fmt)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current, total, msg):
        if total > 0:
            self.progress.setValue(int(current / total * 100))
        self.log.append(msg)

    def _on_done(self, files):
        self.progress.setValue(100)
        self.log.append(f"\n抽帧完成！共生成 {len(files)} 张图片")
        self.btn_start.setEnabled(True)

        if self.chk_annotate.isChecked() and files:
            self._auto_annotate(files)

    def _auto_annotate(self, files):
        self.log.append("开始自动标注...")
        try:
            annotator = AutoAnnotator()
            annotator.load_model("yolov8n.pt")
            output_dir = self.out_path.text().strip()
            label_dir = os.path.join(output_dir, "labels")
            annotator.annotate_directory(output_dir, label_dir, output_format="yolo")
            self.log.append("自动标注完成！")
        except Exception as e:
            self.log.append(f"自动标注失败: {e}")

    def _on_error(self, err):
        self.log.append(f"\n错误: {err}")
        self.btn_start.setEnabled(True)
        QMessageBox.critical(self, "错误", f"抽帧失败: {err}")
