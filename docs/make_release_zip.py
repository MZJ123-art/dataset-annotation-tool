"""把便携版程序目录打成 zip（用于 GitHub Release 附件）。

用法: python docs/make_release_zip.py <程序目录> <输出zip> [使用说明文件]
特点: 保留中文文件名并写入 UTF-8 标志位，Windows 资源管理器解压不乱码。
"""
import os
import sys
import time
import zipfile
from pathlib import Path

APP = Path(sys.argv[1])
OUT = Path(sys.argv[2])
README = Path(sys.argv[3]) if len(sys.argv) > 3 else None

assert APP.is_dir(), f"目录不存在: {APP}"

files = sorted(p for p in APP.rglob("*") if p.is_file())
total_bytes = sum(p.stat().st_size for p in files)
print(f"待压缩: {len(files)} 个文件, {total_bytes / 1024 ** 3:.2f} GB")

t0 = time.time()
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True) as z:
    if README and README.is_file():
        z.write(README, README.name)
    for i, p in enumerate(files, 1):
        z.write(p, str(Path(APP.name) / p.relative_to(APP)))
        if i % 500 == 0 or i == len(files):
            done = sum(f.stat().st_size for f in files[:i])
            el = time.time() - t0
            print(f"  {i}/{len(files)}  {done / 1024 ** 3:.2f} GB  {el:.0f}s", flush=True)

size = OUT.stat().st_size
print(f"完成: {OUT}  {size / 1024 ** 2:.1f} MB  "
      f"(压缩率 {size / max(total_bytes, 1):.2%}, 用时 {time.time() - t0:.0f}s)")
