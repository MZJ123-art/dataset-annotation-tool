from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QStackedWidget, QLabel, QFrame,
                             QSizePolicy, QMenuBar, QMenu, QMessageBox)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QAction

from ui.page_convert import PageConvert
from ui.page_extract import PageExtract
from ui.page_annotate import PageAnnotate
from ui.page_manage import PageManage
from ui.page_stats import PageStats


class NavButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setFixedHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                text-align: left;
                font-size: 14px;
                color: #333;
                background: transparent;
            }
            QPushButton:hover {
                background: #e8e8e8;
            }
            QPushButton:checked {
                background: #4CAF50;
                color: white;
                font-weight: bold;
            }
        """)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数据集标注工具")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # global style: limit combobox dropdown height so it always opens downward
        self.setStyleSheet("""
            QComboBox {
                padding: 2px 6px;
            }
            QComboBox QAbstractItemView {
                max-height: 200px;
            }
        """)

        # sidebar
        sidebar = QFrame()
        sidebar.setFixedWidth(180)
        sidebar.setStyleSheet("QFrame { background: #f0f0f0; border-right: 1px solid #ddd; }")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(6)

        # title
        title = QLabel("数据集工具")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #333; padding: 8px 0 16px 0;")
        sidebar_layout.addWidget(title)

        # nav buttons
        self.nav_buttons = []
        pages = [
            ("格式转换", 0),
            ("视频抽帧", 1),
            ("标注编辑", 2),
            ("数据管理", 3),
            ("统计分析", 4),
        ]

        for text, idx in pages:
            btn = NavButton(text)
            btn.clicked.connect(lambda checked, i=idx: self._switch_page(i))
            sidebar_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        sidebar_layout.addStretch()

        # version label
        ver = QLabel("v2.0")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet("color: #999; font-size: 11px;")
        sidebar_layout.addWidget(ver)

        main_layout.addWidget(sidebar)

        # content area
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QStackedWidget { background: white; }")

        self.page_convert = PageConvert()
        self.page_extract = PageExtract()
        self.page_annotate = PageAnnotate()
        self.page_manage = PageManage()
        self.page_stats = PageStats()

        self.stack.addWidget(self.page_convert)
        self.stack.addWidget(self.page_extract)
        self.stack.addWidget(self.page_annotate)
        self.stack.addWidget(self.page_manage)
        self.stack.addWidget(self.page_stats)

        main_layout.addWidget(self.stack, 1)

        # default selection
        self._switch_page(0)

        # fix combobox dropdown direction
        from PyQt6.QtWidgets import QComboBox
        for cb in self.findChildren(QComboBox):
            cb.setMaxVisibleItems(10)

        # menu bar
        self._init_menu()

        # status bar
        self.statusBar().showMessage("就绪")

    def _init_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件(&F)")
        act_quit = QAction("退出(&Q)", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        help_menu = menubar.addMenu("帮助(&H)")
        act_about = QAction("关于(&A)", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _switch_page(self, idx):
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == idx)

    def _show_about(self):
        QMessageBox.about(self, "关于",
                          "数据集标注工具 v2.0\n\n"
                          "功能: 格式转换 / 视频抽帧 / 自动标注 / 标注编辑 / 数据管理\n\n"
                          "支持格式: YOLO txt / COCO JSON / Pascal VOC XML")
