from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import QPainter, QPen, QColor, QPixmap, QImage, QFont
import cv2
import numpy as np
from typing import List, Optional, Tuple, Set


class DrawState:
    IDLE = "idle"
    DRAWING = "drawing"
    MOVING = "moving"
    RESIZING = "resizing"


class BoundingBox:
    def __init__(self, x1: float, y1: float, x2: float, y2: float,
                 class_name: str = "", class_id: int = 0, color: QColor = None):
        self.x1 = min(x1, x2)
        self.y1 = min(y1, y2)
        self.x2 = max(x1, x2)
        self.y2 = max(y1, y2)
        self.class_name = class_name
        self.class_id = class_id
        self.color = color or QColor(0, 255, 0)

    def to_list(self) -> list:
        return [self.x1, self.y1, self.x2, self.y2]

    def contains(self, px: float, py: float, margin: int = 5) -> bool:
        return (self.x1 - margin <= px <= self.x2 + margin and
                self.y1 - margin <= py <= self.y2 + margin)

    def rect(self) -> QRectF:
        return QRectF(self.x1, self.y1, self.x2 - self.x1, self.y2 - self.y1)


COLORS = [
    QColor(255, 0, 0), QColor(0, 255, 0), QColor(0, 0, 255),
    QColor(255, 255, 0), QColor(255, 0, 255), QColor(0, 255, 255),
    QColor(128, 0, 0), QColor(0, 128, 0), QColor(0, 0, 128),
    QColor(128, 128, 0), QColor(128, 0, 128), QColor(0, 128, 128),
]


def get_color_for_class(class_id: int) -> QColor:
    return COLORS[class_id % len(COLORS)]


class ImageViewer(QWidget):
    box_created = pyqtSignal(float, float, float, float)
    box_selected = pyqtSignal(int)
    box_deleted = pyqtSignal()
    box_moved = pyqtSignal(int, float, float, float, float)
    image_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)

        self._pixmap: Optional[QPixmap] = None
        self._boxes: List[BoundingBox] = []
        self._selected_indices: Set[int] = set()
        self._scale: float = 1.0
        self._offset: Tuple[float, float] = (0, 0)

        self._state = DrawState.IDLE
        self._draw_start: Optional[QPointF] = None
        self._draw_end: Optional[QPointF] = None
        self._drag_start: Optional[QPointF] = None
        self._drag_box_orig: Optional[list] = None
        self._drag_indices: Set[int] = set()
        self._drag_origs: dict = {}

        self._current_class = "object"
        self._drawing_mode = False

    @property
    def _selected_idx(self) -> int:
        """Backward compat: return last selected index."""
        return max(self._selected_indices) if self._selected_indices else -1

    def set_image(self, image_path: str):
        # Use numpy fromfile + cv2.imdecode to handle non-ASCII paths
        import numpy as np
        buf = np.fromfile(image_path, dtype=np.uint8)
        cv_img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        if cv_img is None:
            return
        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)
        self._fit_view()
        self.update()

    def set_image_cv2(self, cv_img: np.ndarray):
        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(qimg)
        self._fit_view()
        self.update()

    def set_boxes(self, boxes: List[BoundingBox]):
        self._boxes = boxes
        self._selected_indices.clear()
        self.update()

    def clear_boxes(self):
        self._boxes.clear()
        self._selected_indices.clear()
        self.update()

    def select_box(self, idx: int):
        self._selected_indices = {idx}
        self.update()

    def select_boxes(self, indices: set):
        self._selected_indices = set(indices)
        self.update()

    def delete_selected(self):
        if not self._selected_indices:
            return
        for idx in sorted(self._selected_indices, reverse=True):
            if 0 <= idx < len(self._boxes):
                del self._boxes[idx]
        self._selected_indices.clear()
        self.update()
        self.box_deleted.emit()

    def delete_box(self, idx: int):
        if 0 <= idx < len(self._boxes):
            del self._boxes[idx]
            # fix selected indices
            new_selected = set()
            for i in self._selected_indices:
                if i < idx:
                    new_selected.add(i)
                elif i > idx:
                    new_selected.add(i - 1)
            self._selected_indices = new_selected
            self.update()

    def set_drawing_mode(self, enabled: bool):
        self._drawing_mode = enabled
        self.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor)

    def set_current_class(self, class_name: str):
        self._current_class = class_name

    def _fit_view(self):
        if not self._pixmap:
            return
        pw, ph = self._pixmap.width(), self._pixmap.height()
        ww, wh = self.width(), self.height()
        self._scale = min(ww / max(pw, 1), wh / max(ph, 1))
        self._offset = ((ww - pw * self._scale) / 2, (wh - ph * self._scale) / 2)

    def _img_to_widget(self, x: float, y: float) -> QPointF:
        return QPointF(x * self._scale + self._offset[0], y * self._scale + self._offset[1])

    def _widget_to_img(self, x: float, y: float) -> QPointF:
        return QPointF((x - self._offset[0]) / self._scale, (y - self._offset[1]) / self._scale)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_view()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(40, 40, 40))

        if not self._pixmap:
            painter.setPen(QColor(200, 200, 200))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "拖入图片或选择文件开始标注")
            return

        target = QRectF(self._offset[0], self._offset[1],
                        self._pixmap.width() * self._scale,
                        self._pixmap.height() * self._scale)
        painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))

        for i, box in enumerate(self._boxes):
            p1 = self._img_to_widget(box.x1, box.y1)
            p2 = self._img_to_widget(box.x2, box.y2)
            rect = QRectF(p1, p2)

            if i in self._selected_indices:
                pen = QPen(QColor(255, 255, 0), 3)
            else:
                pen = QPen(box.color, 2)
            painter.setPen(pen)
            painter.drawRect(rect)

            # draw class label above the box
            font = QFont("Arial", 10)
            painter.setFont(font)
            fm = painter.fontMetrics()
            text_width = fm.horizontalAdvance(box.class_name) + 8
            text_height = fm.height() + 2
            lx = rect.x()
            ly = rect.y() - text_height
            if ly < 0:
                ly = rect.y()
            label_rect = QRectF(lx, ly, max(text_width, rect.width()), text_height)
            painter.setPen(box.color)
            painter.drawText(label_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, box.class_name)

        if self._state == DrawState.DRAWING and self._draw_start and self._draw_end:
            pen = QPen(QColor(255, 255, 255), 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(QRectF(self._draw_start, self._draw_end))

        painter.end()

    def mousePressEvent(self, event):
        self.setFocus()
        if not self._pixmap:
            return
        pos = event.position()

        if event.button() == Qt.MouseButton.LeftButton:
            if self._drawing_mode:
                self._state = DrawState.DRAWING
                self._draw_start = pos
                self._draw_end = pos
            else:
                img_pos = self._widget_to_img(pos.x(), pos.y())
                clicked_idx = -1
                for i in range(len(self._boxes) - 1, -1, -1):
                    if self._boxes[i].contains(img_pos.x(), img_pos.y()):
                        clicked_idx = i
                        break

                ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
                if clicked_idx >= 0:
                    if ctrl:
                        # Ctrl+click: toggle this box
                        if clicked_idx in self._selected_indices:
                            self._selected_indices.discard(clicked_idx)
                        else:
                            self._selected_indices.add(clicked_idx)
                    else:
                        # plain click: add if not already selected
                        if clicked_idx not in self._selected_indices:
                            self._selected_indices.add(clicked_idx)
                    self._state = DrawState.MOVING
                    self._drag_start = pos
                    self._drag_indices = set(self._selected_indices)
                    self._drag_origs = {i: self._boxes[i].to_list() for i in self._drag_indices}
                    self.box_selected.emit(clicked_idx)
                    self.update()
                else:
                    self._selected_indices.clear()
                    self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()
        if self._state == DrawState.DRAWING:
            self._draw_end = pos
            self.update()
        elif self._state == DrawState.MOVING and self._drag_start:
            dx = (pos.x() - self._drag_start.x()) / self._scale
            dy = (pos.y() - self._drag_start.y()) / self._scale
            for i in self._drag_indices:
                if i in self._drag_origs:
                    orig = self._drag_origs[i]
                    self._boxes[i].x1 = orig[0] + dx
                    self._boxes[i].y1 = orig[1] + dy
                    self._boxes[i].x2 = orig[2] + dx
                    self._boxes[i].y2 = orig[3] + dy
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._state == DrawState.DRAWING and self._draw_start:
                p1 = self._widget_to_img(self._draw_start.x(), self._draw_start.y())
                p2 = self._widget_to_img(self._draw_end.x(), self._draw_end.y())
                x1, y1 = min(p1.x(), p2.x()), min(p1.y(), p2.y())
                x2, y2 = max(p1.x(), p2.x()), max(p1.y(), p2.y())
                if abs(x2 - x1) > 5 and abs(y2 - y1) > 5:
                    self.box_created.emit(x1, y1, x2, y2)
                self._state = DrawState.IDLE
                self._draw_start = None
                self._draw_end = None
                self.update()
            elif self._state == DrawState.MOVING:
                if self._drag_start:
                    pos = event.position()
                    dx = abs(pos.x() - self._drag_start.x())
                    dy = abs(pos.y() - self._drag_start.y())
                    if dx > 3 or dy > 3:
                        for i in self._drag_indices:
                            if i < len(self._boxes):
                                box = self._boxes[i]
                                self.box_moved.emit(i, box.x1, box.y1, box.x2, box.y2)
                self._state = DrawState.IDLE
                self._drag_start = None
                self._drag_indices.clear()
                self._drag_origs.clear()
            self.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            self.delete_selected()
        super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff', '.webp')):
                self.image_dropped.emit(path)
                break
