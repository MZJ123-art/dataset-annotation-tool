import cv2
import numpy as np
from PIL import Image
from typing import Tuple


def get_image_size(image_path: str) -> Tuple[int, int]:
    with Image.open(image_path) as img:
        return img.size  # (width, height)


def read_image_cv2(image_path: str) -> np.ndarray:
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot read image: {image_path}")
    return img


def resize_for_display(img: np.ndarray, max_width: int, max_height: int) -> np.ndarray:
    h, w = img.shape[:2]
    scale = min(max_width / w, max_height / h)
    if scale >= 1:
        return img
    new_w, new_h = int(w * scale), int(h * scale)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def adjust_brightness(img: np.ndarray, factor: float) -> np.ndarray:
    return cv2.convertScaleAbs(img, alpha=factor, beta=0)


def adjust_contrast(img: np.ndarray, factor: float) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mean = np.mean(gray)
    return cv2.convertScaleAbs(img, alpha=factor, beta=mean * (1 - factor))
