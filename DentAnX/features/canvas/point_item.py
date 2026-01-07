""" Landmark point item for DentAnX. """

from __future__ import annotations

from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QGraphicsObject, QMenu

from ...utils.landmarks import LANDMARK_COLORS


class LandmarkPointItem(QGraphicsObject):
    """Interactive QGraphics item representing a CEJ or Crest point."""

    DEFAULT_RADIUS = 3.0

    moved = pyqtSignal(str, float, float)
    deleteRequested = pyqtSignal(str)
    selected = pyqtSignal(str)

    def __init__(self, point_id: str, label: str, bounds: QRectF, parent=None, radius: float | None = None) -> None:
        super().__init__(parent)
        self.point_id = point_id
        self.label = label
        self._bounds = bounds
        self._radius = radius if radius is not None else self.DEFAULT_RADIUS
        self._selected = False
        self._dragging = False
        self._color = QColor(LANDMARK_COLORS.get(label, "#4DA3FF"))
        self.setZValue(10)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)

    def boundingRect(self) -> QRectF:  # type: ignore[override]
        r = self._radius + (4 if self._selected else 0)
        return QRectF(-r, -r, 2 * r, 2 * r)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # type: ignore[override]
        painter.setRenderHint(QPainter.Antialiasing)
        r = self._radius
        if self._selected:
            painter.setPen(QPen(QColor("#FFFFFF"), 2))
        else:
            painter.setPen(QPen(QColor("#1E1E1E"), 1))
        painter.setBrush(self._color)
        painter.drawEllipse(QPointF(0, 0), r, r)

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self.prepareGeometryChange()
            self._selected = selected
            self.update()

    def set_bounds(self, bounds: QRectF) -> None:
        self._bounds = bounds

    def hoverEnterEvent(self, event) -> None:  # type: ignore[override]
        if not self._dragging:
            self.setCursor(Qt.OpenHandCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # type:ignore[override]
        if not self._dragging:
            self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self.setCursor(Qt.ClosedHandCursor)
            self.selected.emit(self.point_id)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._dragging:
            new_pos = self._clamp_pos(event.scenePos())
            self.setPos(new_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._dragging and event.button() == Qt.LeftButton:
            self._dragging = False
            self.unsetCursor()
            point = self.pos()
            self.moved.emit(self.point_id, point.x(), point.y())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _clamp_pos(self, pos: QPointF) -> QPointF:
        if self._bounds is None:
            return pos
        x = min(max(self._bounds.left(), pos.x()), self._bounds.right())
        y = min(max(self._bounds.top(), pos.y()), self._bounds.bottom())
        return QPointF(x, y)

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        parent = None
        if self.scene() and self.scene().views():
            parent = self.scene().views()[0]
        menu = QMenu(parent)
        delete_action = menu.addAction("Delete point")
        cancel_action = menu.addAction("Cancel")
        action = menu.exec_(event.screenPos())
        if action == delete_action:
            self.deleteRequested.emit(self.point_id)
        event.accept()

    def radius(self) -> float:
        return self._radius

    def set_radius(self, radius: float) -> None:
        self.prepareGeometryChange()
        self._radius = radius
        self.update()

    def set_bbox_mode(self, enabled: bool) -> None:
        """Configure item for bbox mode (lower opacity, disabled interaction)."""
        if enabled:
            self.setOpacity(0.4)
            self.setAcceptedMouseButtons(Qt.NoButton)
            self.setAcceptHoverEvents(False)
        else:
            self.setOpacity(1.0)
            self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
            self.setAcceptHoverEvents(True)
