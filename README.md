# 数据集标注工具

一站式数据集标注/管理桌面工具，基于 PyQt6 开发。

## 功能特性

### 格式转换
- 支持 YOLO txt、COCO JSON、Pascal VOC XML 三种格式互转（6种转换方向）
- 自动检测源格式
- 批量转换，保留原目录不动

### 视频抽帧
- 支持 mp4/avi/mov/mkv 等常见格式
- 按帧间隔或时间间隔抽帧
- 输出格式可选（jpg/png）

### 标注编辑（类 LabelImg）
- 左侧文件列表 + 中间画布 + 右侧标签列表
- 绘制/选择/移动/缩放/删除矩形框
- 多选支持（Ctrl+点击）
- 快捷键：W 绘制框、D 下一张、A 上一张、Del 删除选中框
- 支持导入上层目录，自动遍历子目录
- 自动查找标签目录（支持图片和标签分离存储）

### 自动标注
- 基于 YOLOv8/YOLO11 推理
- 支持内置预训练模型和自定义 .pt 权重
- 批量推理，可设置置信度阈值

### 数据集管理
- train/val/test 自动拆分（可设比例）
- 批量重命名
- 标签一致性检查（越界/空标签/类别错误）

### 数据统计
- 各类别实例数量柱状图
- 图片尺寸分布
- 标注框面积分布
- 导出 HTML 统计报告

## 环境要求

- Python 3.10+
- Windows 10/11

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行

```bash
python main.py
```

## 打包为 exe

```bash
# 安装 PyInstaller
pip install pyinstaller

# 使用 PyInstaller 打包
python -m PyInstaller --name="数据集标注工具" --onedir --noconfirm --windowed \
  --hidden-import=PyQt6.QtWidgets \
  --hidden-import=PyQt6.QtCore \
  --hidden-import=PyQt6.QtGui \
  --hidden-import=cv2 \
  --hidden-import=numpy \
  --hidden-import=PIL \
  --hidden-import=ultralytics \
  --exclude-module=scipy \
  --exclude-module=pandas \
  --exclude-module=matplotlib \
  main.py
```

## 项目结构

```
├── main.py                    # 入口
├── requirements.txt           # 依赖
├── ui/
│   ├── main_window.py         # 主窗口（侧边栏导航 + 内容区）
│   ├── page_convert.py        # 格式转换页面
│   ├── page_extract.py        # 视频抽帧页面
│   ├── page_annotate.py       # 标注编辑页面
│   ├── page_manage.py         # 数据集管理页面
│   ├── page_stats.py          # 数据统计页面
│   └── widgets/
│       ├── image_viewer.py    # 图片查看/标注组件
│       ├── label_list.py      # 标签列表组件
│       └── progress_dialog.py # 进度对话框
├── core/
│   ├── converter.py           # 格式转换引擎
│   ├── extractor.py           # 视频抽帧引擎
│   ├── annotator.py           # 自动标注引擎
│   ├── dataset_manager.py     # 数据集管理
│   └── validator.py           # 标签校验
└── utils/
    ├── formats/
    │   ├── yolo_format.py     # YOLO txt 读写
    │   ├── coco_format.py     # COCO JSON 读写
    │   └── voc_format.py      # Pascal VOC XML 读写
    ├── file_utils.py          # 文件操作工具
    └── image_utils.py         # 图像工具
```

## 截图

| 格式转换 | 标注编辑 |
|---------|---------|
| 支持 YOLO/COCO/VOC 互转 | 类 LabelImg 标注体验 |

## 技术栈

| 组件 | 技术选型 |
|------|---------|
| GUI 框架 | PyQt6 |
| 视频处理 | OpenCV (cv2) |
| 模型推理 | ultralytics (YOLOv8/YOLO11) |
| 图像处理 | Pillow |
| 数据处理 | NumPy |

## License

MIT
