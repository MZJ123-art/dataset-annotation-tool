# -*- mode: python ; coding: utf-8 -*-

import os

# ---------------------------------------------------------------- OpenCV FFmpeg
# cv2 的 cv2.pyd 运行时只会加载与自身版本号匹配的 opencv_videoio_ffmpeg<ver>_64.dll。
# site-packages\cv2 里可能残留其它版本的同名库（装过更高版本 opencv 之后就会残留），
# 一旦打包进不匹配的那个，cv2 的 FFmpeg 后端就加载不起来，VideoCapture() 对任何
# 视频都会失败（表现为视频抽帧报 "Cannot open video"）。
# 这里按 cv2.__version__ 精确挑出匹配的库，并剔除全部不匹配的版本。
import cv2 as _cv2

_cv2_dir = os.path.dirname(_cv2.__file__)
_v = _cv2.__version__.split(".")                          # 例如 4.10.0.84
_want = f"opencv_videoio_ffmpeg{_v[0]}{_v[1]}0_64.dll"   # -> opencv_videoio_ffmpeg4100_64.dll
_want_path = os.path.join(_cv2_dir, _want)
if os.path.exists(_want_path):
    print(f"[spec] OpenCV {_cv2.__version__} -> 打包 {_want}")
    binaries = [(_want_path, "cv2")]
else:
    print(f"[spec] 警告: {_cv2_dir} 下没有 {_want}，沿用 hook 收集结果")
    binaries = []


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=[],
    hiddenimports=['PyQt6.QtWidgets', 'PyQt6.QtCore', 'PyQt6.QtGui', 'cv2', 'numpy', 'PIL', 'ultralytics'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'scipy', 'pandas', 'matplotlib',
        # 本工具只用 .pt 做推理，不导出 onnx / 不做数据分析，这些依赖可以不带
        'onnxruntime', 'polars', 'pyarrow', 'hf_xet',
    ],
    noarchive=False,
    optimize=0,
)

# ---------------------------------------------------------------- torch 瘦身
# 依据 PE 导入表算出的硬依赖闭包 + 实测结论：
#   * torch_cuda.dll 硬导入 cusparse/cufft/cusolver/cublas，删掉 import torch 直接失败
#   * 删 cudnn_engines_precompiled / cudnn_adv 更危险：不报错但推理结果变错（静默失效）
#   * 下面这几个没有任何模块引用，实测剔除后 torch + CUDA + 推理结果与基线完全一致
_DROP_DLLS = {
    n.lower() for n in (
        "cusolverMg64_11.dll",     # 多卡直接求解器，150MB
        "curand64_10.dll",         # 随机数，推理用不到，69MB
        "nvrtc64_120_0.alt.dll",   # nvrtc 的重复副本，83MB
        "nvperf_host.dll",         # profiling，21MB
    )
}
_before = len(a.binaries)
a.binaries = [b for b in a.binaries if os.path.basename(b[0]).lower() not in _DROP_DLLS]
print(f"[spec] torch 瘦身：剔除 {_before - len(a.binaries)} 个未使用的 CUDA 库")

# hook-cv2 会用 *.dll 通配把 cv2 目录下所有 FFmpeg 库都收进来，这里剔除不匹配的，
# 并确保匹配的那个一定在。
a.binaries = [
    b for b in a.binaries
    if not (os.path.basename(b[0]).startswith("opencv_videoio_ffmpeg")
            and os.path.basename(b[0]) != _want)
]
if os.path.exists(_want_path) and not any(os.path.basename(b[0]) == _want for b in a.binaries):
    a.binaries.append((os.path.join("cv2", _want), _want_path, "BINARY"))

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='数据集标注工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='数据集标注工具',
)
