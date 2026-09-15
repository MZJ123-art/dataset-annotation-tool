import os
import random
import shutil
from pathlib import Path
from typing import List, Tuple, Callable, Optional
from utils.file_utils import (safe_makedirs, get_image_files, find_label_for_image,
                              check_dir_conflict, norm_path, SKIP_DIR_NAMES)

SPLIT_NAMES = ("train", "val", "test")


def clean_previous_splits(output_dir: str) -> int:
    """清理上一次拆分产生的文件（只动 <out>/train|val|test/{images,labels} 里的文件）。"""
    removed = 0
    for split in SPLIT_NAMES:
        for sub in ("images", "labels"):
            d = Path(output_dir) / split / sub
            if not d.is_dir():
                continue
            for f in d.iterdir():
                if f.is_file():
                    try:
                        f.unlink()
                        removed += 1
                    except OSError:
                        pass
    return removed


def count_previous_splits(output_dir: str) -> int:
    """统计上一次拆分遗留的文件数（供界面提示）。"""
    n = 0
    for split in SPLIT_NAMES:
        for sub in ("images", "labels"):
            d = Path(output_dir) / split / sub
            if d.is_dir():
                n += sum(1 for f in d.iterdir() if f.is_file())
    return n


def split_dataset(
    image_dir: str,
    label_dir: str,
    output_dir: str,
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
    test_ratio: float = 0.1,
    shuffle: bool = True,
    seed: int = 42,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> dict:
    # 输出目录不能是输入目录本身或包含输入目录，否则拆分结果会混进源数据
    check_dir_conflict(image_dir, output_dir, "图片目录")
    if label_dir:
        check_dir_conflict(label_dir, output_dir, "标签目录")

    images = get_image_files(image_dir)
    if shuffle:
        random.seed(seed)
        random.shuffle(images)

    total = len(images)
    train_end = int(total * train_ratio)
    val_end = train_end + int(total * val_ratio)

    splits = {
        "train": images[:train_end],
        "val": images[train_end:val_end],
        "test": images[val_end:],
    }

    # 清掉上次拆分的残留，避免重复运行后新旧文件混在一起
    clean_previous_splits(output_dir)

    result = {}
    count = 0
    for split_name, split_images in splits.items():
        img_out = os.path.join(output_dir, split_name, "images")
        lbl_out = os.path.join(output_dir, split_name, "labels")
        safe_makedirs(img_out)
        safe_makedirs(lbl_out)

        for img_path in split_images:
            count += 1
            if progress_callback:
                progress_callback(count, total, os.path.basename(img_path))

            # copy image
            shutil.copy2(img_path, os.path.join(img_out, Path(img_path).name))

            # find and copy label
            label_path = find_label_for_image(img_path, label_dir)
            if label_path:
                stem = Path(img_path).stem
                label_ext = Path(label_path).suffix
                shutil.copy2(label_path, os.path.join(lbl_out, f"{stem}{label_ext}"))

        result[split_name] = len(split_images)

    if progress_callback:
        progress_callback(total, total, "完成")

    return result


def plan_rename(
    image_dir: str,
    label_dir: Optional[str] = None,
    prefix: str = "img",
    start_index: int = 0,
    digits: int = 6,
) -> Tuple[List[dict], List[str]]:
    """先算出重命名计划与冲突，不碰磁盘。

    返回 (计划列表, 冲突描述列表)。
    """
    images = get_image_files(image_dir)
    sources = {norm_path(p) for p in images}

    # 先把所有标签路径算一遍（O(n)），避免在循环里反复探测文件系统
    label_of = {}
    label_paths = set()
    for img in images:
        lp = find_label_for_image(img, label_dir) if label_dir else None
        label_of[img] = lp
        if lp:
            label_paths.add(norm_path(lp))

    plan, conflicts = [], []
    targets = {}

    for i, img_path in enumerate(images):
        stem = f"{prefix}_{str(start_index + i).zfill(digits)}"
        ext = Path(img_path).suffix
        new_img = os.path.join(image_dir, f"{stem}{ext}")
        label_path = label_of.get(img_path)
        new_label = None
        if label_path:
            new_label = os.path.join(label_dir, f"{stem}{Path(label_path).suffix}")

        # 目标已存在，且不是本批要改名的文件 -> 真冲突
        if os.path.exists(new_img) and norm_path(new_img) not in sources:
            conflicts.append(f"{os.path.basename(new_img)} 已存在（来自 {os.path.basename(img_path)}）")
        if new_img in targets:
            conflicts.append(f"{os.path.basename(new_img)} 被多个文件指向")
        targets[new_img] = img_path
        if new_label and os.path.exists(new_label) and norm_path(new_label) not in label_paths:
            conflicts.append(f"{os.path.basename(new_label)} 已存在（标签）")

        plan.append({
            "old_img": img_path, "new_img": new_img,
            "old_label": label_path, "new_label": new_label,
        })
    return plan, conflicts


def batch_rename(
    image_dir: str,
    label_dir: Optional[str] = None,
    prefix: str = "img",
    start_index: int = 0,
    digits: int = 6,
    dry_run: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[Tuple[str, str]]:
    """批量重命名图片（及对应的标签文件）。

    采用两阶段改名（先改成临时名，再改成目标名），避免目标名正好是
    另一个待改名文件时中途失败、留下改了一半的数据集。
    """
    plan, conflicts = plan_rename(image_dir, label_dir, prefix, start_index, digits)
    if conflicts:
        raise ValueError("存在命名冲突，未做任何修改：\n  " + "\n  ".join(conflicts[:20]))
    if dry_run:
        return [(os.path.basename(p["old_img"]), os.path.basename(p["new_img"])) for p in plan]

    total = len(plan)
    tmps = []
    try:
        for i, item in enumerate(plan):          # 第一阶段：改成临时名
            tmp_img = os.path.join(image_dir, f"__renaming_{i}{Path(item['old_img']).suffix}")
            os.rename(item["old_img"], tmp_img)
            item["tmp_img"] = tmp_img
            if item["old_label"] and os.path.exists(item["old_label"]):
                tmp_lbl = os.path.join(label_dir, f"__renaming_{i}{Path(item['old_label']).suffix}")
                os.rename(item["old_label"], tmp_lbl)
                item["tmp_label"] = tmp_lbl
            if progress_callback:
                progress_callback(i, total * 2, os.path.basename(item["old_img"]))
        for i, item in enumerate(plan):          # 第二阶段：改成目标名
            os.rename(item["tmp_img"], item["new_img"])
            if item.get("tmp_label"):
                os.rename(item["tmp_label"], item["new_label"])
            tmps.append((os.path.basename(item["old_img"]), os.path.basename(item["new_img"])))
            if progress_callback:
                progress_callback(total + i, total * 2, os.path.basename(item["new_img"]))
    except OSError:
        for item in plan:                        # 出错则尽量回滚
            try:
                if item.get("tmp_img") and os.path.exists(item["tmp_img"]):
                    os.rename(item["tmp_img"], item["old_img"])
                if item.get("tmp_label") and os.path.exists(item["tmp_label"]):
                    os.rename(item["tmp_label"], item["old_label"])
            except OSError:
                pass
        raise

    return tmps


def delete_image_and_label(image_path: str, label_dir: Optional[str] = None) -> bool:
    label_path = find_label_for_image(image_path, label_dir)
    if os.path.exists(image_path):
        os.remove(image_path)
    if label_path and os.path.exists(label_path):
        os.remove(label_path)
    return True
