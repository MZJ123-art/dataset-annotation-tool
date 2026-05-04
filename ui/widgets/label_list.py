from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
                             QHBoxLayout, QPushButton, QLineEdit,
                             QAbstractItemView)
from PyQt6.QtCore import pyqtSignal, Qt


class LabelListWidget(QWidget):
    selection_changed = pyqtSignal(int)
    multi_selection_changed = pyqtSignal(set)
    class_changed = pyqtSignal(int, str)
    delete_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.currentRowChanged.connect(self.selection_changed.emit)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.list_widget)

        # inline edit row
        self._edit_row = QHBoxLayout()
        self._edit_input = QLineEdit()
        self._edit_input.setPlaceholderText("输入新类别名...")
        self._edit_btn_ok = QPushButton("确定")
        self._edit_btn_cancel = QPushButton("取消")
        self._edit_btn_ok.setFixedWidth(40)
        self._edit_btn_cancel.setFixedWidth(40)
        self._edit_row.addWidget(self._edit_input, 1)
        self._edit_row.addWidget(self._edit_btn_ok)
        self._edit_row.addWidget(self._edit_btn_cancel)
        self._edit_widget = QWidget()
        self._edit_widget.setLayout(self._edit_row)
        self._edit_widget.setVisible(False)
        layout.addWidget(self._edit_widget)

        self._edit_btn_ok.clicked.connect(self._on_edit_ok)
        self._edit_btn_cancel.clicked.connect(self._on_edit_cancel)
        self._edit_input.returnPressed.connect(self._on_edit_ok)

        btn_layout = QHBoxLayout()
        self.btn_rename = QPushButton("重命名")
        self.btn_delete = QPushButton("删除选中")
        self.btn_rename.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_delete.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_rename.clicked.connect(self._on_rename)
        self.btn_delete.clicked.connect(self._on_delete)
        btn_layout.addWidget(self.btn_rename)
        btn_layout.addWidget(self.btn_delete)
        layout.addLayout(btn_layout)

        self._items = []
        self._last_selected_idx = -1

    def set_items(self, items: list[tuple[str, str]]):
        self._items = items
        self.list_widget.clear()
        for cls_name, bbox_str in items:
            self.list_widget.addItem(f"{cls_name}  {bbox_str}")

    def set_current_index(self, idx: int):
        if 0 <= idx < self.list_widget.count():
            self.list_widget.setCurrentRow(idx)

    def select_indices(self, indices: set):
        self.list_widget.clearSelection()
        for i in indices:
            if 0 <= i < self.list_widget.count():
                self.list_widget.item(i).setSelected(True)

    def current_index(self) -> int:
        return self.list_widget.currentRow()

    def selected_indices(self) -> list[int]:
        return sorted([i.row() for i in self.list_widget.selectedIndexes()])

    def _on_selection_changed(self):
        indices = self.selected_indices()
        if indices:
            self._last_selected_idx = indices[0]
        self.multi_selection_changed.emit(set(indices))

    def _on_rename(self):
        idx = self._last_selected_idx
        if idx < 0:
            indices = self.selected_indices()
            idx = indices[0] if indices else -1
        if idx < 0 or idx >= len(self._items):
            return
        old_name = self._items[idx][0]
        self._edit_input.setText(old_name)
        self._edit_input.selectAll()
        self._edit_widget.setVisible(True)
        self._edit_input.setFocus()
        self._edit_input.selectAll()

    def _on_edit_ok(self):
        new_name = self._edit_input.text().strip()
        idx = self._last_selected_idx
        if not new_name or idx < 0 or idx >= len(self._items):
            self._edit_widget.setVisible(False)
            return
        old_name = self._items[idx][0]
        if new_name != old_name:
            self.class_changed.emit(idx, new_name)
        self._edit_widget.setVisible(False)

    def _on_edit_cancel(self):
        self._edit_widget.setVisible(False)

    def _on_delete(self):
        if self.list_widget.selectedItems():
            self.delete_requested.emit()
