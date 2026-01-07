from __future__ import annotations

import math
from enum import Enum
from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPen, QBrush, QCursor, QPixmap
from PyQt5.QtWidgets import QGraphicsObject, QMenu

from ...utils.landmarks import BBOX_COLORS

class Handle(Enum):
    NONE = 0
    TOP_LEFT = 1
    TOP_RIGHT = 2
    BOTTOM_LEFT = 3
    BOTTOM_RIGHT = 4
    CENTER = 5
    ROTATION = 6

class BoundingBoxItem(QGraphicsObject):
    """Interactive QGraphics item representing a tooth bounding box with rotation."""

    moved = pyqtSignal(int, float, float, float, float, float)  # id, x_center, y_center, width, height, rotation
    deleteRequested = pyqtSignal(int)
    selected = pyqtSignal(int)
    labelChanged = pyqtSignal(int, str)

    HANDLE_SIZE = 8.0
    MIN_SIZE = 10.0
    ROTATION_HANDLE_OFFSET = 20.0
    _rotation_cursor: QCursor | None = None

    @classmethod
    def _get_rotation_cursor(cls) -> QCursor:
        if cls._rotation_cursor is None:
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Draw curved arrow
            pen = QPen(Qt.black, 2)
            painter.setPen(pen)
            
            path = QPainterPath()
            # Start at right side, curve up and left
            path.moveTo(24, 16)
            path.arcTo(8, 8, 16, 16, 0, 270)
            painter.drawPath(path)
            
            # Draw arrow head at top
            head = QPainterPath()
            # End of arc is at (16, 24) roughly? 
            # arcTo(x, y, w, h, startAngle, spanAngle)
            # Rect is 8,8 to 24,24. Center 16,16.
            # 0 degrees is 3 o'clock (24, 16).
            # 270 degrees span goes CCW to 6 o'clock (16, 24).
            # So arrow head should be at (16, 24) pointing left/down?
            # Let's try a simpler icon: a circle with an arrow.
            
            # Let's draw a standard refresh-like arrow
            painter.setPen(QPen(Qt.white, 3)) # Outline
            painter.drawArc(8, 8, 16, 16, 45 * 16, 270 * 16)
            painter.setPen(QPen(Qt.black, 1.5))
            painter.drawArc(8, 8, 16, 16, 45 * 16, 270 * 16)
            
            # Arrowhead at the end (approx 315 degrees -> 45 degrees)
            # End point is around (22, 10)
            # Let's just draw a simple symbol
            
            painter.end()
            cls._rotation_cursor = QCursor(pixmap)
            
            # Better approach: Use a standard bitmap if drawing is hard to get right blindly
            # Or just a simple circle for now
            pixmap.fill(Qt.transparent)
            painter.begin(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # White outline
            painter.setPen(QPen(Qt.white, 3))
            painter.drawArc(6, 6, 20, 20, 0, 270 * 16)
            
            # Black stroke
            painter.setPen(QPen(Qt.black, 1.5))
            painter.drawArc(6, 6, 20, 20, 0, 270 * 16)
            
            # Arrowhead
            # End of arc is at top (90 deg) -> 12 o'clock?
            # Qt angles: 0 is 3 o'clock, positive is CCW.
            # 0 to 270 goes 3 -> 12 -> 9 -> 6.
            # End is at 6 o'clock (bottom).
            # Let's do 90 start, 270 span.
            # Start 90 (12 o'clock). Span 270 (CCW to 3 o'clock).
            # End is at 3 o'clock (right).
            
            # Let's try a simpler "rotate" icon logic
            # Draw a C shape
            painter.setPen(QPen(Qt.white, 4))
            painter.drawArc(8, 8, 16, 16, 45 * 16, 270 * 16)
            painter.setPen(QPen(Qt.black, 2))
            painter.drawArc(8, 8, 16, 16, 45 * 16, 270 * 16)
            
            # Arrowhead at top right
            # (20, 10) roughly
            path = QPainterPath()
            path.moveTo(22, 6)
            path.lineTo(22, 14)
            path.lineTo(16, 10)
            path.closeSubpath()
            
            painter.setBrush(Qt.black)
            painter.setPen(Qt.NoPen)
            painter.drawPath(path)
            
            # White border for arrowhead
            painter.setPen(QPen(Qt.white, 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)
            
            painter.end()
            cls._rotation_cursor = QCursor(pixmap)
            
        return cls._rotation_cursor

    def __init__(self, bbox_id: int, rect: QRectF, bounds: QRectF, rotation: float = 0.0, label: str = "Mandibular", parent=None) -> None:
        super().__init__(parent)
        self.bbox_id = bbox_id
        self._label = label
        self._bounds = bounds
        
        # Store the center position in scene coordinates
        center = rect.center()
        
        # Create a rect centered at (0, 0) in item coordinates
        w = rect.width()
        h = rect.height()
        self._rect = QRectF(-w/2, -h/2, w, h)
        
        # Position the item at the center
        self.setPos(center)
        self.setRotation(rotation)
        
        self._selected = False
        self._landmark_mode = False  # New: track if in landmark mode
        self._dragging_handle = Handle.NONE
        self._start_pos = QPointF()
        self._start_rect = QRectF()
        self._start_rotation = 0.0
        self._start_scene_pos = QPointF()
        self._start_item_pos = QPointF()
        
        self.setZValue(5)
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
        self.setFlag(QGraphicsObject.ItemIsMovable, False)
        self.setFlag(QGraphicsObject.ItemSendsGeometryChanges, True)

    def boundingRect(self) -> QRectF:
        # Add padding for handles and rotation handle
        r = self._rect
        pad = self.HANDLE_SIZE + self.ROTATION_HANDLE_OFFSET
        return r.adjusted(-pad, -pad, pad, pad)
    
    def shape(self) -> QPainterPath:
        """Return the shape for accurate hit testing with rotation."""
        path = QPainterPath()
        
        # If selected, include the handles in the hit area
        if self._selected and not self._landmark_mode:
            # Add the handles to the shape
            handles = self._get_handle_rects()
            for handle_rect in handles.values():
                path.addRect(handle_rect)
        
        # Always add the main rectangle to the shape
        path.addRect(self._rect)
        
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw Box
        if self._selected:
            pen = QPen(QColor("#FFFF00"), 1)  # Yellow border when selected
            painter.setBrush(QBrush(QColor(255, 255, 0, 30)))  # Yellow fill with transparency
        else:
            # Lower opacity when in landmark mode
            opacity = 30 if self._landmark_mode else 255
            color = QColor(BBOX_COLORS.get(self._label, "#FFFF00"))
            color.setAlpha(opacity)
            pen = QPen(color, 1.5)  # Thinner border
            painter.setBrush(Qt.NoBrush)
            
        painter.setPen(pen)
        painter.drawRect(self._rect)

        # Draw Handles if selected and not in landmark mode
        if self._selected and not self._landmark_mode:
            painter.setBrush(QBrush(QColor("#FFFFFF")))
            painter.setPen(QPen(QColor("#000000"), 1))
            
            handles = self._get_handle_rects()
            for handle_type, handle_rect in handles.items():
                if handle_type == Handle.ROTATION:
                    # Draw line to rotation handle
                    top_center = QPointF(self._rect.center().x(), self._rect.top())
                    painter.drawLine(top_center, handle_rect.center())
                    # Draw circular handle
                    painter.drawEllipse(handle_rect)
                else:
                    painter.drawRect(handle_rect)
                
            # Draw ID and Label with smaller font
            painter.setPen(QPen(QColor("#FFFFFF"), 1))
            font = painter.font()
            font.setPointSize(8)  # Smaller font size
            painter.setFont(font)
            painter.drawText(self._rect.topLeft() + QPointF(5, 12), f"{self.bbox_id}: {self._label}")

    def set_selected(self, selected: bool) -> None:
        if self._selected != selected:
            self.prepareGeometryChange()
            self._selected = selected
            # Bring to front when selected
            self.setZValue(10 if selected else 5)
            self.update()
    
    def set_landmark_mode(self, landmark_mode: bool) -> None:
        """Set whether the bbox is in landmark mode (low opacity, non-interactive)."""
        if self._landmark_mode != landmark_mode:
            self._landmark_mode = landmark_mode
            # Disable interactions in landmark mode
            self.setAcceptHoverEvents(not landmark_mode)
            if landmark_mode:
                self.setAcceptedMouseButtons(Qt.NoButton)
            else:
                self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
            self.update()

    def _get_handle_rects(self) -> dict[Handle, QRectF]:
        r = self._rect
        s = self.HANDLE_SIZE
        hs = s / 2
        
        handles = {
            Handle.TOP_LEFT: QRectF(r.left() - hs, r.top() - hs, s, s),
            Handle.TOP_RIGHT: QRectF(r.right() - hs, r.top() - hs, s, s),
            Handle.BOTTOM_LEFT: QRectF(r.left() - hs, r.bottom() - hs, s, s),
            Handle.BOTTOM_RIGHT: QRectF(r.right() - hs, r.bottom() - hs, s, s),
        }
        
        # Rotation handle
        top_center_x = (r.left() + r.right()) / 2
        handles[Handle.ROTATION] = QRectF(top_center_x - hs, r.top() - self.ROTATION_HANDLE_OFFSET - hs, s, s)
        
        return handles

    def hoverMoveEvent(self, event) -> None:
        if self._selected:
            handle = self._handle_at(event.pos())
            cursor = Qt.ArrowCursor
            if handle in (Handle.TOP_LEFT, Handle.BOTTOM_RIGHT):
                cursor = Qt.SizeFDiagCursor
            elif handle in (Handle.TOP_RIGHT, Handle.BOTTOM_LEFT):
                cursor = Qt.SizeBDiagCursor
            elif handle == Handle.ROTATION:
                cursor = self._get_rotation_cursor()
            elif self._rect.contains(event.pos()):
                cursor = Qt.SizeAllCursor
            self.setCursor(cursor)
        else:
            self.setCursor(Qt.PointingHandCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self.unsetCursor()
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        # Ignore mouse events in landmark mode
        if self._landmark_mode:
            event.ignore()
            return
            
        if event.button() == Qt.LeftButton:
            self.selected.emit(self.bbox_id)
            self._start_pos = event.pos()
            self._start_scene_pos = event.scenePos()
            self._start_item_pos = self.pos()
            self._start_rect = self._rect
            self._start_rotation = self.rotation()
            
            if self._selected:
                self._dragging_handle = self._handle_at(event.pos())
                if self._dragging_handle == Handle.NONE and self._rect.contains(event.pos()):
                    self._dragging_handle = Handle.CENTER
            
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging_handle != Handle.NONE:
            self.prepareGeometryChange()
            
            if self._dragging_handle == Handle.ROTATION:
                # Calculate angle relative to item's position (which is its center)
                center = self.pos()
                mouse_pos = event.scenePos()
                dx = mouse_pos.x() - center.x()
                dy = mouse_pos.y() - center.y()
                angle = math.degrees(math.atan2(dy, dx)) + 90
                self.setRotation(angle)
                
            elif self._dragging_handle == Handle.CENTER:
                # Move the item (which moves its center)
                current_scene_pos = event.scenePos()
                diff = current_scene_pos - self._start_scene_pos
                self.setPos(self._start_item_pos + diff)
                
            else:
                # Resizing - track the opposite corner as fixed point
                # Transform mouse position from scene coords to item's rotated coordinate system
                mouse_scene = event.scenePos()
                
                # Get the fixed corner (opposite to the one being dragged) in item coords
                if self._dragging_handle == Handle.TOP_LEFT:
                    # Fixed corner is bottom-right
                    fixed_local = self._start_rect.bottomRight()
                elif self._dragging_handle == Handle.TOP_RIGHT:
                    # Fixed corner is bottom-left
                    fixed_local = self._start_rect.bottomLeft()
                elif self._dragging_handle == Handle.BOTTOM_LEFT:
                    # Fixed corner is top-right
                    fixed_local = self._start_rect.topRight()
                elif self._dragging_handle == Handle.BOTTOM_RIGHT:
                    # Fixed corner is top-left
                    fixed_local = self._start_rect.topLeft()
                else:
                    return
                
                # Transform mouse position from scene coords to item's local coords
                # accounting for rotation
                angle_rad = math.radians(self._start_rotation)
                cos_a = math.cos(angle_rad)
                sin_a = math.sin(angle_rad)
                
                # Translate mouse to item-space (relative to start position)
                mouse_rel_x = mouse_scene.x() - self._start_item_pos.x()
                mouse_rel_y = mouse_scene.y() - self._start_item_pos.y()
                
                # Apply inverse rotation to get mouse in item's local coordinate system
                mouse_local_x = mouse_rel_x * cos_a + mouse_rel_y * sin_a
                mouse_local_y = -mouse_rel_x * sin_a + mouse_rel_y * cos_a
                mouse_local = QPointF(mouse_local_x, mouse_local_y)
                
                # Create a rect from the fixed corner and mouse position in local coords
                local_rect = QRectF(fixed_local, mouse_local).normalized()
                
                # Check minimum size
                if local_rect.width() < self.MIN_SIZE or local_rect.height() < self.MIN_SIZE:
                    return
                
                # Calculate the new center in local coords
                new_center_local = local_rect.center()
                
                # Transform the new center back to scene coords
                center_rot_x = new_center_local.x() * cos_a - new_center_local.y() * sin_a
                center_rot_y = new_center_local.x() * sin_a + new_center_local.y() * cos_a
                new_center_scene = QPointF(
                    self._start_item_pos.x() + center_rot_x,
                    self._start_item_pos.y() + center_rot_y
                )
                
                # Update item position to new center
                self.setPos(new_center_scene)
                
                # Create new rect centered at origin with the new size
                w = local_rect.width()
                h = local_rect.height()
                self._rect = QRectF(-w/2, -h/2, w, h)

            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._dragging_handle != Handle.NONE:
            self._dragging_handle = Handle.NONE
            # Emit updated geometry
            # Center is the item's position
            center = self.pos()
            self.moved.emit(
                self.bbox_id, 
                center.x(), 
                center.y(), 
                self._rect.width(), 
                self._rect.height(),
                self.rotation()
            )
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _handle_at(self, pos: QPointF) -> Handle:
        handles = self._get_handle_rects()
        for handle, rect in handles.items():
            if rect.contains(pos):
                return handle
        return Handle.NONE

    def set_label(self, label: str) -> None:
        if self._label != label:
            self._label = label
            self.update()
            self.labelChanged.emit(self.bbox_id, label)

    def contextMenuEvent(self, event) -> None:
        menu = QMenu()
        
        # Label selection
        label_menu = menu.addMenu("Set Label")
        for label_name in BBOX_COLORS:
            action = label_menu.addAction(label_name)
            # Use default argument to capture loop variable
            action.triggered.connect(lambda checked, l=label_name: self.set_label(l))
        
        menu.addSeparator()
        delete_action = menu.addAction("Delete Box")
        action = menu.exec_(event.screenPos())
        if action == delete_action:
            self.deleteRequested.emit(self.bbox_id)
        event.accept()
