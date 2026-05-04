import os
import random
import shutil
from pathlib import Path
from typing import List, Tuple, Callable, Optional
from utils.file_utils import safe_makedirs, get_image_files, find_label_for_image


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


def batch_rename(
    image_dir: str,
    label_dir: Optional[str] = None,
    prefix: str = "img",
    start_index: int = 0,
    digits: int = 6,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[Tuple[str, str]]:
    images = get_image_files(image_dir)
    renamed = []
    total = len(images)

    for i, img_path in enumerate(images):
        if progress_callback:
            progress_callback(i, total, os.path.basename(img_path))

        ext = Path(img_path).suffix
        new_name = f"{prefix}_{str(start_index + i).zfill(digits)}{ext}"
        new_path = os.path.join(image_dir, new_name)
        os.rename(img_path, new_path)

        # rename label too
        if label_dir:
            label_path = find_label_for_image(img_path, label_dir)
            if label_path:
                label_ext = Path(label_path).suffix
                new_label = f"{prefix}_{str(start_index + i).zfill(digits)}{label_ext}"
                new_label_path = os.path.join(label_dir, new_label)
                os.rename(label_path, new_label_path)

        renamed.append((os.path.basename(img_path), new_name))

    if progress_callback:
        progress_callback(total, total, "完成")

    return renamed


def delete_image_and_label(image_path: str, label_dir: Optional[str] = None) -> bool:
    label_path = find_label_for_image(image_path, label_dir)
    if os.path.exists(image_path):
        os.remove(image_path)
    if label_path and os.path.exists(label_path):
        os.remove(label_path)
    return True
