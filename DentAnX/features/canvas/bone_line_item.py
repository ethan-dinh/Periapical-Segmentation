from __future__ import annotations

import math
from typing import List, Optional
from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QBrush
from PyQt5.QtWidgets import QGraphicsObject, QMenu

class BoneLineItem(QGraphicsObject):
    """
    Interactive QGraphics item representing a bone line (polyline).
    Consists of a series of points connected by lines.
    """

    # Signal emitted when the line geometry changes
    # Arguments: line_id, list of points (each point is {x, y})
    lineChanged = pyqtSignal(str, list)
    deleteRequested = pyqtSignal(str)
    selected = pyqtSignal(str)

    HANDLE_SIZE = 8.0
    
    def __init__(self, line_id: str, points: List[QPointF], image_rect: QRectF, parent=None) -> None:
        super().__init__(parent)
        self.line_id = line_id
        # Convert list of points to local QPointF list
        self._points: List[QPointF] = [QPointF(p.x(), p.y()) for p in points]
        self._image_rect = image_rect
        
        self._selected = False
        self._hover_point_index: int = -1
        self._dragging_point_index: int = -1
        
        self.setZValue(6)  # Just above bboxes (5)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
        self.setFlag(QGraphicsObject.ItemIsMovable, False)
        self.setFlag(QGraphicsObject.ItemSendsGeometryChanges, True)

    def boundingRect(self) -> QRectF:
        if not self._points:
            return QRectF()
        
        # Calculate bounding rect of all points
        x_min = min(p.x() for p in self._points)
        y_min = min(p.y() for p in self._points)
        x_max = max(p.x() for p in self._points)
        y_max = max(p.y() for p in self._points)
        
        w = x_max - x_min
        h = y_max - y_min
        
        # Add padding for handles
        pad = self.HANDLE_SIZE
        return QRectF(x_min, y_min, w, h).adjusted(-pad, -pad, pad, pad)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        if not self._points:
            return path
            
        # Add lines with some thickness for hit testing
        stroker = QPainterPath()
        stroker.moveTo(self._points[0])
        for p in self._points[1:]:
            stroker.lineTo(p)
            
        # Create a wider path for easy clicking
        from PyQt5.QtGui import QPainterPathStroker
        ps = QPainterPathStroker()
        ps.setWidth(10)
        path = ps.createStroke(stroker)
        
        # Add handles explicitly if selected
        if self._selected:
            for p in self._points:
                r = QRectF(p.x() - self.HANDLE_SIZE/2, p.y() - self.HANDLE_SIZE/2, 
                           self.HANDLE_SIZE, self.HANDLE_SIZE)
                path.addRect(r)
                
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        
        if not self._points:
            return

        # Draw Line
        color = QColor("#00FF00")  # Green for bone lines
        width = 2.0
        if self._selected:
            color = QColor("#FFFF00")  # Yellow when selected
            width = 3.0
            
        pen = QPen(color, width)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        
        path = QPainterPath()
        path.moveTo(self._points[0])
        for p in self._points[1:]:
            path.lineTo(p)
        painter.drawPath(path)

        # Draw Handles (Points)
        # Always draw start and end points slightly different?
        # Or just draw all points when selected/hovered.
        
        draw_handles = self._selected or self._hover_point_index != -1
        
        if draw_handles:
            for i, p in enumerate(self._points):
                # Highlight hovered point
                if i == self._hover_point_index or i == self._dragging_point_index:
                    painter.setBrush(QBrush(QColor("#FF0000"))) # Red
                    size = self.HANDLE_SIZE + 2
                else:
                    painter.setBrush(QBrush(QColor("#FFFFFF"))) # White
                    size = self.HANDLE_SIZE
                
                painter.setPen(QPen(QColor("#000000"), 1))
                r = QRectF(p.x() - size/2, p.y() - size/2, size, size)
                painter.drawEllipse(r)

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self.prepareGeometryChange()
            self._selected = selected
            self.setZValue(11 if selected else 6)
            self.update()

    def add_point(self, pos: QPointF) -> None:
        self.prepareGeometryChange()
        self._points.append(pos)
        self.update()
        self._emit_changed()

    def update_last_point(self, pos: QPointF) -> None:
        if not self._points:
            return
        self.prepareGeometryChange()
        self._points[-1] = pos
        self.update()
        self._emit_changed()

    def get_points(self) -> List[dict]:
        return [{"x": p.x(), "y": p.y()} for p in self._points]

    def set_points(self, points: List[QPointF]) -> None:
        self.prepareGeometryChange()
        self._points = points
        self.update()

    def _emit_changed(self) -> None:
        self.lineChanged.emit(self.line_id, self.get_points())

    def _point_index_at(self, pos: QPointF) -> int:
        for i, p in enumerate(self._points):
            # Check distance
            dist = math.hypot(p.x() - pos.x(), p.y() - pos.y())
            if dist < self.HANDLE_SIZE:
                return i
        return -1

    def hoverMoveEvent(self, event) -> None:
        idx = self._point_index_at(event.pos())
        if idx != self._hover_point_index:
            self._hover_point_index = idx
            self.update()
            
        if idx != -1:
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor if self._selected else Qt.PointingHandCursor)
            
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        if self._hover_point_index != -1:
            self._hover_point_index = -1
            self.update()
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.line_id)
            
            # Check if clicking a point to drag
            idx = self._point_index_at(event.pos())
            if idx != -1:
                self._dragging_point_index = idx
                event.accept()
                return
                
            if self._selected:
                 # If just clicking the line (not a point), maybe start drag whole line?
                 # For now, just select.
                 pass
            
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging_point_index != -1:
            # Dragging a specific point
            new_pos = event.pos()
            # Clamp to bounds
            x = max(self._image_rect.left(), min(self._image_rect.right(), new_pos.x()))
            y = max(self._image_rect.top(), min(self._image_rect.bottom(), new_pos.y()))
            new_pos = QPointF(x, y)
            
            self.prepareGeometryChange()
            self._points[self._dragging_point_index] = new_pos
            self.update()
            self._emit_changed()
            event.accept()
            return
            
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._dragging_point_index != -1:
            self._dragging_point_index = -1
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu()
        delete_action = menu.addAction("Delete Line")
        
        # Check if clicking a point to delete just that point
        idx = self._point_index_at(event.pos())
        delete_point_action = None
        if idx != -1 and len(self._points) > 2:
             delete_point_action = menu.addAction("Delete Point")

        action = menu.exec_(event.screenPos())
        
        if action == delete_action:
            self.deleteRequested.emit(self.line_id)
        elif delete_point_action and action == delete_point_action:
            self.prepareGeometryChange()
            self._points.pop(idx)
            self.update()
            self._emit_changed()
            
        event.accept()
