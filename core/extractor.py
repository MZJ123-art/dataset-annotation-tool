import os
import cv2
from pathlib import Path
from typing import Callable, Optional
from utils.file_utils import safe_makedirs


class ExtractMode:
    BY_FRAME = "frame_interval"
    BY_TIME = "time_interval"


def get_video_info(video_path: str) -> dict:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")
    info = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "duration": cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1),
    }
    cap.release()
    return info


def extract_frames(
    video_path: str,
    output_dir: str,
    mode: str = ExtractMode.BY_FRAME,
    interval: int = 10,
    output_format: str = "jpg",
    max_frames: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> list[str]:
    safe_makedirs(output_dir)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if mode == ExtractMode.BY_TIME:
        frame_interval = int(fps * interval)
    else:
        frame_interval = max(1, interval)

    video_stem = Path(video_path).stem
    saved_files = []
    frame_idx = 0
    saved_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_interval == 0:
            filename = f"{video_stem}_{saved_count:06d}.{output_format}"
            filepath = os.path.join(output_dir, filename)
            # Use imencode + tofile to handle non-ASCII paths (Chinese chars)
            ext = os.path.splitext(filepath)[1]
            if ext.lower() in ('.jpg', '.jpeg'):
                ret_enc, buf = cv2.imencode(ext, frame, [cv2.IMWRITE_JPEG_QUALITY, 100])
            else:
                ret_enc, buf = cv2.imencode(ext, frame)
            if ret_enc:
                buf.tofile(filepath)
                saved_files.append(filepath)
                saved_count += 1

                if progress_callback:
                    progress_callback(frame_idx, total_frames, filename)

                if max_frames and saved_count >= max_frames:
                    break

        frame_idx += 1

    cap.release()

    if progress_callback:
        progress_callback(total_frames, total_frames, f"完成，共抽取 {saved_count} 帧")

    return saved_files


def extract_frames_batch(
    video_paths: list[str],
    output_dir: str,
    mode: str = ExtractMode.BY_FRAME,
    interval: int = 10,
    output_format: str = "jpg",
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> list[str]:
    all_files = []
    for i, vp in enumerate(video_paths):
        sub_dir = os.path.join(output_dir, Path(vp).stem)
        if progress_callback:
            progress_callback(i, len(video_paths), os.path.basename(vp))
        files = extract_frames(vp, sub_dir, mode, interval, output_format)
        all_files.extend(files)
    return all_files
