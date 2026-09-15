"""生成 README 用的界面截图（使用合成图片，不含任何真实数据）。

用法: python docs/make_screenshots.py
输出: docs/screenshot_*.png

注意：不能设置 QT_QPA_PLATFORM=offscreen —— offscreen 插件没有字体，
     文字会渲染成方块。这里用真实平台 + WA_DontShowOnScreen，
     既能用系统字体布局，又不会真的弹窗。
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from ui.main_window import MainWindow  # noqa: E402

APP = QApplication([])
OUT = ROOT / "docs"
OUT.mkdir(exist_ok=True)


def make_sample_dataset(root: Path, n=6):
    """造一个小的合成数据集：渐变天空 + 小目标，配 YOLO 标签。"""
    (root / "images").mkdir(parents=True, exist_ok=True)
    (root / "labels").mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    for i in range(n):
        h, w = 480, 640
        y = np.linspace(120, 200, h).reshape(-1, 1).repeat(w, 1)
        img = np.dstack([y * 0.9, y * 0.95, y * 1.0]).astype(np.uint8)
        img = np.ascontiguousarray(img)
        pil = Image.fromarray(img)
        d = ImageDraw.Draw(pil)
        cx, cy = int(rng.integers(120, w - 120)), int(rng.integers(80, h - 120))
        bw, bh = 34, 14
        d.ellipse([cx - bw, cy - bh, cx + bw, cy + bh], fill=(60, 60, 66))
        d.line([cx - bw, cy, cx + bw, cy], fill=(90, 90, 96), width=3)
        pil.save(root / "images" / f"sample_{i:04d}.png")
        (root / "labels" / f"sample_{i:04d}.txt").write_text(
            f"0 {cx / w:.6f} {cy / h:.6f} {2 * bw / w:.6f} {2 * bh / h:.6f}\n", encoding="utf-8")
    (root / "labels" / "classes.txt").write_text("drone\nperson\ncar\n", encoding="utf-8")


def shot(widget, name):
    widget.resize(1400, 880)
    APP.processEvents()
    pm = QPixmap(widget.size())
    widget.render(pm)
    path = OUT / name
    pm.save(str(path))
    print(f"  已保存 {path.relative_to(ROOT)}  ({pm.width()}x{pm.height()})")


win = MainWindow()
win.resize(1400, 880)
# 让 Qt 用系统字体完成布局，但窗口不真正显示
win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
win.show()
APP.processEvents()

tmp = Path(os.environ.get("SHOT_DEMO_DIR", r"D:\demo_dataset"))
shutil.rmtree(tmp, ignore_errors=True)
dataset = tmp
make_sample_dataset(dataset)
win.page_annotate._base_dir = str(dataset)
win.page_annotate._load_images_from_dir(str(dataset / "images"))
win.page_convert.lbl_dir.setText(str(dataset / "labels"))
win.page_convert.img_dir.setText(str(dataset / "images"))
win.page_convert.dst_path.setText(str(tmp / "converted"))
win.page_extract.out_path.setText(str(tmp / "frames"))
win.page_manage.split_img_dir.setText(str(dataset / "images"))
win.page_manage.split_lbl_dir.setText(str(dataset / "labels"))
win.page_manage.split_out_dir.setText(str(tmp / "split"))
win.page_manage.rename_dir.setText(str(dataset / "images"))
win.page_stats.img_dir.setText(str(dataset / "images"))
win.page_stats.lbl_dir.setText(str(dataset / "labels"))
APP.processEvents()

for idx, name in enumerate(["convert", "extract", "annotate", "manage", "stats"]):
    win._switch_page(idx)
    if name == "stats":
        win.page_stats._generate_stats()
    APP.processEvents()
    shot(win, f"screenshot_{idx + 1}_{name}.png")

print("完成")
