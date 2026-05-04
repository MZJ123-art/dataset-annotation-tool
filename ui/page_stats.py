import os
from collections import Counter
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLineEdit, QLabel, QFileDialog,
                             QTextEdit, QMessageBox)
from utils.file_utils import get_image_files, find_label_for_image
from utils.formats.yolo_format import read_label
from utils.image_utils import get_image_size


class PageStats(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # input
        input_group = QGroupBox("数据集统计")
        input_layout = QVBoxLayout(input_group)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("图片目录:"))
        self.img_dir = QLineEdit()
        btn_img = QPushButton("浏览")
        btn_img.clicked.connect(lambda: self._browse(self.img_dir))
        dir_row.addWidget(self.img_dir)
        dir_row.addWidget(btn_img)
        input_layout.addLayout(dir_row)

        dir_row2 = QHBoxLayout()
        dir_row2.addWidget(QLabel("标签目录:"))
        self.lbl_dir = QLineEdit()
        btn_lbl = QPushButton("浏览")
        btn_lbl.clicked.connect(lambda: self._browse(self.lbl_dir))
        dir_row2.addWidget(self.lbl_dir)
        dir_row2.addWidget(btn_lbl)
        input_layout.addLayout(dir_row2)

        btn_row = QHBoxLayout()
        self.btn_stats = QPushButton("生成统计")
        self.btn_stats.setMinimumHeight(36)
        self.btn_stats.clicked.connect(self._generate_stats)
        btn_row.addWidget(self.btn_stats)

        self.btn_export = QPushButton("导出HTML报告")
        self.btn_export.clicked.connect(self._export_html)
        self.btn_export.setEnabled(False)
        btn_row.addWidget(self.btn_export)
        input_layout.addLayout(btn_row)

        layout.addWidget(input_group)

        # results
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text, 1)

        self._stats_data = {}

    def _browse(self, line_edit):
        d = QFileDialog.getExistingDirectory(self, "选择目录")
        if d:
            line_edit.setText(d)

    def _generate_stats(self):
        img_dir = self.img_dir.text().strip()
        lbl_dir = self.lbl_dir.text().strip() or img_dir
        if not img_dir:
            QMessageBox.warning(self, "提示", "请选择图片目录")
            return

        images = get_image_files(img_dir)
        if not images:
            QMessageBox.warning(self, "提示", "未找到图片文件")
            return

        class_counter = Counter()
        width_list = []
        height_list = []
        area_list = []
        labeled_count = 0
        unlabeled_count = 0
        total_objects = 0

        for img_path in images:
            w, h = get_image_size(img_path)
            width_list.append(w)
            height_list.append(h)

            label_path = find_label_for_image(img_path, lbl_dir)
            if label_path and label_path.endswith(".txt"):
                objects = read_label(label_path, w, h)
                if objects:
                    labeled_count += 1
                    for obj in objects:
                        class_counter[obj.class_name] += 1
                        x1, y1, x2, y2 = obj.bbox
                        area = (x2 - x1) * (y2 - y1)
                        area_list.append(area)
                    total_objects += len(objects)
                else:
                    unlabeled_count += 1
            else:
                unlabeled_count += 1

        # format output
        lines = ["=" * 50, "数据集统计报告", "=" * 50, ""]
        lines.append(f"总图片数: {len(images)}")
        lines.append(f"已标注图片: {labeled_count}")
        lines.append(f"未标注图片: {unlabeled_count}")
        lines.append(f"总标注框数: {total_objects}")
        lines.append("")

        if width_list:
            lines.append(f"图片宽度范围: {min(width_list)} ~ {max(width_list)}")
            lines.append(f"图片高度范围: {min(height_list)} ~ {max(height_list)}")
            avg_w = sum(width_list) / len(width_list)
            avg_h = sum(height_list) / len(height_list)
            lines.append(f"平均尺寸: {avg_w:.0f} x {avg_h:.0f}")
            lines.append("")

        if class_counter:
            lines.append("类别统计:")
            lines.append("-" * 30)
            for cls, count in class_counter.most_common():
                pct = count / total_objects * 100 if total_objects else 0
                lines.append(f"  {cls}: {count} ({pct:.1f}%)")
            lines.append("")

        if area_list:
            lines.append("标注框面积统计:")
            lines.append("-" * 30)
            avg_area = sum(area_list) / len(area_list)
            lines.append(f"  平均面积: {avg_area:.0f}")
            lines.append(f"  最小面积: {min(area_list):.0f}")
            lines.append(f"  最大面积: {max(area_list):.0f}")

        self._stats_data = {
            "total_images": len(images),
            "labeled": labeled_count,
            "unlabeled": unlabeled_count,
            "total_objects": total_objects,
            "class_counter": class_counter,
            "width_list": width_list,
            "height_list": height_list,
            "area_list": area_list,
        }

        self.result_text.setText("\n".join(lines))
        self.btn_export.setEnabled(True)

    def _export_html(self):
        if not self._stats_data:
            return
        path, _ = QFileDialog.getSaveFileName(self, "导出报告", "dataset_report.html", "HTML文件 (*.html)")
        if not path:
            return

        d = self._stats_data
        class_rows = ""
        for cls, count in d["class_counter"].most_common():
            pct = count / d["total_objects"] * 100 if d["total_objects"] else 0
            bar_w = max(2, pct)
            class_rows += f"""
            <tr>
                <td>{cls}</td>
                <td>{count}</td>
                <td>{pct:.1f}%</td>
                <td><div style="background:#4CAF50;height:20px;width:{bar_w}%"></div></td>
            </tr>"""

        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>数据集统计报告</title>
<style>
body {{ font-family: Arial; margin: 40px; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background: #4CAF50; color: white; }}
.stat-card {{ display: inline-block; padding: 20px; margin: 10px; background: #f5f5f5; border-radius: 8px; min-width: 150px; }}
.stat-num {{ font-size: 32px; font-weight: bold; color: #4CAF50; }}
</style></head><body>
<h1>数据集统计报告</h1>
<div>
    <div class="stat-card"><div class="stat-num">{d['total_images']}</div>总图片数</div>
    <div class="stat-card"><div class="stat-num">{d['labeled']}</div>已标注</div>
    <div class="stat-card"><div class="stat-num">{d['unlabeled']}</div>未标注</div>
    <div class="stat-card"><div class="stat-num">{d['total_objects']}</div>总标注框</div>
</div>
<h2>类别分布</h2>
<table>
<tr><th>类别</th><th>数量</th><th>占比</th><th>分布</th></tr>
{class_rows}
</table>
</body></html>"""

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        QMessageBox.information(self, "完成", f"报告已导出到: {path}")
