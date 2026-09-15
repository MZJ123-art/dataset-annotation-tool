from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QStackedWidget, QLabel, QFrame,
                             QSizePolicy, QMenuBar, QMenu, QMessageBox,
                             QApplication)
from PyQt6.QtCore import Qt, QSize, QSettings
from PyQt6.QtGui import QFont, QAction, QKeySequence, QShortcut

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


def _app_settings() -> QSettings:
    return QSettings("DatasetTool", "数据集标注工具")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("数据集标注工具")
        # 最小值放宽，配合各页面的滚动区域，小屏幕（1366x768）也能完整操作
        self.setMinimumSize(900, 560)
        self._init_ui()
        self._restore_geometry()
        self._init_shortcuts()

    def _init_shortcuts(self):
        for i in range(5):
            sc = QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self)
            sc.activated.connect(lambda idx=i: self._switch_page(idx))

    def _restore_geometry(self):
        s = _app_settings()
        geo = s.value("window_geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.resize(min(1400, max(900, screen.width() - 80)),
                        min(900, max(560, screen.height() - 80)))
            self.move(screen.center().x() - self.width() // 2,
                      max(screen.top(), screen.center().y() - self.height() // 2))
        last = s.value("last_page", 0, type=int)
        if 0 <= last < self.stack.count():
            self._switch_page(last)

    def closeEvent(self, event):
        s = _app_settings()
        s.setValue("window_geometry", self.saveGeometry())
        s.setValue("last_page", self.stack.currentIndex())
        super().closeEvent(event)

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
        title = QLabel("数据集标注工具")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Microsoft YaHei", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #333; padding: 8px 0 4px 0;")
        sidebar_layout.addWidget(title)

        hint = QLabel("Ctrl+1~5 切换页面")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #aaa; font-size: 10px; padding-bottom: 12px;")
        sidebar_layout.addWidget(hint)

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
        ver = QLabel("v2.1")
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
