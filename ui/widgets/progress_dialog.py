from PyQt6.QtWidgets import QProgressDialog, QLabel, QVBoxLayout, QDialog
from PyQt6.QtCore import Qt


class ProgressDialog(QProgressDialog):
    def __init__(self, title="处理中...", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumWidth(400)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setValue(0)
        self.setCancelButton(None)

    def update_progress(self, current: int, total: int, message: str = ""):
        if total > 0:
            pct = int(current / total * 100)
            self.setValue(pct)
        if message:
            self.setLabelText(message)
