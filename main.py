import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow


def _selftest() -> int:
    """无界面自检：只验证所有页面能否构建成功。

    打包后用 `数据集标注工具.exe --selftest` 运行，结果写入临时文件
    （窗口模式没有控制台，且崩溃时的错误弹窗会阻塞，所以用文件传递结果）。
    """
    import tempfile
    import traceback

    log = os.path.join(tempfile.gettempdir(), "dataset_tool_selftest.txt")
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("数据集标注工具")
        app.setStyle("Fusion")
        window = MainWindow()
        window.show()
        app.processEvents()
        with open(log, "w", encoding="utf-8") as f:
            f.write(f"OK pages={window.stack.count()}\n")
        return 0
    except Exception:
        try:
            with open(log, "w", encoding="utf-8") as f:
                f.write("FAIL\n" + traceback.format_exc())
        except OSError:
            pass
        return 2


def main():
    if "--selftest" in sys.argv:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        return _selftest()

    app = QApplication(sys.argv)
    app.setApplicationName("数据集标注工具")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
