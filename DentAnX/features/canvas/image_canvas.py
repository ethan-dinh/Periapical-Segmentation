from __future__ import annotations

import uuid
from enum import Enum, auto
from typing import Dict, List

import math
import numpy as np
# pylint: disable=no-name-in-module
from PyQt5.QtCore import QEvent, QPoint, QPointF, QRect, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QCursor, QImage, QPixmap, QPainter, QPen, QTransform
from PyQt5.QtWidgets import (
    QGestureEvent,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QMenu,
)
# pylint: enable=no-name-in-module

from ...utils.landmarks import LANDMARK_COLORS, normalize_class, BBOX_CLASSES
from .point_item import LandmarkPointItem
from .bbox_item import BoundingBoxItem
from .bone_line_item import BoneLineItem


class CanvasMode(Enum):
    """ Enum for canvas modes. """
    LANDMARK = auto()
    BBOX = auto()
    BONE = auto()


class BBoxDrawMode(Enum):
    """ Enum for bbox draw modes. """
    DRAG = auto()
    THREE_POINT = auto()


class ImageCanvas(QGraphicsView):
    """Central QGraphicsView handling image display and point interactions."""

    pointsUpdated = pyqtSignal(list)
    bboxesUpdated = pyqtSignal(list)
    boneLinesUpdated = pyqtSignal(list)
    countsChanged = pyqtSignal(int, int, int)  # CEJ, Crest, BBox
    zoomChanged = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.grabGesture(Qt.PinchGesture)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        self._scene.setSceneRect(0, 0, 0, 0)

        self._point_items: Dict[str, LandmarkPointItem] = {}
        self._points: Dict[str, Dict[str, float | str]] = {}
        
        self._bbox_items: Dict[int, BoundingBoxItem] = {}
        self._bboxes: Dict[int, Dict[str, int | float | str]] = {}
        self._next_bbox_id = 0

        self._bone_line_items: Dict[str, BoneLineItem] = {}
        # Storage format: {id: [ {x, y}, ... ]}
        self._bone_lines: Dict[str, List[Dict[str, float]]] = {}
        self._selected_bone_line_id: str | None = None
        self._drawing_bone_line = False
        self._current_bone_line_points: List[QPointF] = []
        self._current_bone_line_item: BoneLineItem | None = None
        
        self._image_rect = QRectF()
        self._selected_point_id: str | None = None
        self._selected_bbox_id: int | None = None
        
        self._mode = CanvasMode.LANDMARK
        self._drawing_bbox = False
        self._bbox_start = QPointF()
        self._current_bbox_item: BoundingBoxItem | None = None
        self._bbox_filter = "All"  # Filter instead of class selector
        
        # Three-point drawing mode
        self._bbox_draw_mode = BBoxDrawMode.DRAG
        self._three_point_corners: List[QPointF] = []
        self._preview_line: QGraphicsLineItem | None = None
        self._preview_polygon: QGraphicsPolygonItem | None = None

        self._zoom_percent = 100
        self._zoom_factor = 1.0
        self._base_scale = 1.0
        self._base_transform = QTransform()
        self._original_np: np.ndarray | None = None
        self._display_qimage: QImage | None = None
        self._brightness = 0
        self._contrast = 0
        self._gamma = 1.0
        self._auto_enhance = False
        self._edge_enhance = False
        self._dot_radius = LandmarkPointItem.DEFAULT_RADIUS
        self._panning = False
        self._pan_start = QPoint()
        self._space_held = False
        self._magnifier = QLabel(self.viewport())
        self._magnifier.setFixedSize(140, 140)
        self._magnifier.setStyleSheet(
            "background-color: rgba(30,30,30,220); border: 2px solid #4DA3FF; border-radius: 70px;"
        )
        self._magnifier.setAlignment(Qt.AlignCenter)
        self._magnifier.hide()
        self._position_magnifier()

    def set_mode(self, mode: CanvasMode) -> None:
        self._mode = mode
        is_landmark = (mode == CanvasMode.LANDMARK)
        is_bone = (mode == CanvasMode.BONE)
        
        for bbox_item in self._bbox_items.values():
            bbox_item.set_landmark_mode(is_landmark or is_bone) # Lock bbox in BONE mode too?
            # Or should bboxes be hidden in bone mode? User didn't specify.
            # Let's assume we want to see them but not interact, effectively like landmark mode.
            # Let's assume we want to see them but not interact, effectively like landmark mode.
            
        for point_item in self._point_items.values():
            point_item.set_bbox_mode(not is_landmark)
            
        # Update visibility/interactivity of bone lines?
        # Maybe we only want to interact with them in BONE mode.
        for bone_item in self._bone_line_items.values():
            # Basic implementation: always visible, only interactive in BONE mode
            bone_item.setVisible(True)
            bone_item.setAcceptHoverEvents(is_bone)
            if is_bone:
                bone_item.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
            else:
                bone_item.setAcceptedMouseButtons(Qt.NoButton)
        for point_item in self._point_items.values():
            point_item.set_bbox_mode(not is_landmark)
        self.clear_selection()
        self.viewport().update()

    def set_bbox_filter(self, filter_label: str) -> None:
        """Set the bbox filter and update visibility of all bboxes."""
        self._bbox_filter = filter_label
        for bbox_id, item in self._bbox_items.items():
            bbox_label = self._bboxes[bbox_id].get("label", "Unlabeled")
            if filter_label == "All":
                item.setVisible(True)
            else:
                item.setVisible(bbox_label == filter_label)

    def has_image(self) -> bool:
        return not self._pixmap_item.pixmap().isNull()

    def clear(self) -> None:
        self._pixmap_item.setPixmap(QPixmap())
        self._scene.setSceneRect(QRectF())
        self._clear_points()
        self._clear_bboxes()
        self.resetTransform()
        self._zoom_percent = 100
        self.zoomChanged.emit(self._zoom_percent)
        self.viewport().setCursor(Qt.ArrowCursor)
        self._zoom_factor = 1.0
        self._base_scale = 1.0

    def load_image(self, path: str) -> tuple[int, int]:
        image = QImage(path)
        if image.isNull():
            raise ValueError(f"Unable to load image: {path}")
        rgba = image.convertToFormat(QImage.Format_RGBA8888)
        ptr = rgba.bits()
        ptr.setsize(rgba.byteCount())
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((rgba.height(), rgba.width(), 4)).copy()
        self._original_np = arr
        display_pixmap = QPixmap.fromImage(rgba)
        self._display_qimage = rgba
        self._clear_points()
        self._clear_bboxes()
        self._pixmap_item.setPixmap(display_pixmap)
        width, height = display_pixmap.width(), display_pixmap.height()
        self._image_rect = QRectF(0, 0, width, height)
        self._scene.setSceneRect(self._image_rect)
        self.resetTransform()
        if not self._image_rect.isNull():
            self.fitInView(self._image_rect, Qt.KeepAspectRatio)
        self._base_transform = self.transform()
        self._base_scale = max(1e-6, self.transform().m11())
        self._zoom_percent = 100
        self._zoom_factor = 1.0
        self.zoomChanged.emit(self._zoom_percent)
        self.viewport().update()
        self.viewport().setCursor(Qt.CrossCursor)
        self._apply_adjustments()
        self._hide_magnifier()
        return width, height

    def _clear_points(self) -> None:
        for item in self._point_items.values():
            self._scene.removeItem(item)
        self._point_items.clear()
        self._points.clear()
        self._selected_point_id = None
        self.countsChanged.emit(0, 0, 0)
        self._hide_magnifier()

    def _clear_bboxes(self) -> None:
        for item in self._bbox_items.values():
            self._scene.removeItem(item)
        self._bbox_items.clear()
        self._bboxes.clear()
        self._selected_bbox_id = None
        self._next_bbox_id = 0
        self.countsChanged.emit(0, 0, 0)

    def set_points(self, points: List[Dict[str, float | str]]) -> None:
        self._clear_points()
        for point in points:
            cls = normalize_class(point.get("class", "CEJ"))
            x = float(point.get("x", 0))
            y = float(point.get("y", 0))
            radius = float(point.get("radius", self._dot_radius))
            self._create_point(cls, QPointF(x, y), point_id=str(uuid.uuid4()), emit=False, radius=radius)
        self.countsChanged.emit(*self._count_items())

    def _clear_bone_lines(self) -> None:
        for item in self._bone_line_items.values():
            self._scene.removeItem(item)
        self._bone_line_items.clear()
        self._bone_lines.clear()
        self._selected_bone_line_id = None
        self._current_bone_line_points.clear()
        self._current_bone_line_item = None
        # countsChanged will need to be updated to include bone lines count?
        # User requested conversion and logic, maybe I should add bone lines to countsChanged later if needed.
        # For now, it keeps CEJ, CREST, BBOX.

    def set_bone_lines(self, bone_lines: List[List[Dict[str, float]]]) -> None:
        self._clear_bone_lines()
        for line_points in bone_lines:
            # line_points is a list of dicts {x, y}
            points = [QPointF(float(p["x"]), float(p["y"])) for p in line_points]
            if not points:
                continue
            self._create_bone_line(points, emit=False)
        self._emit_state_changed()

    def set_bboxes(self, bboxes: List[Dict[str, int | float | str]]) -> None:
        self._clear_bboxes()
        for bbox in bboxes:
            # Handle both OBB format (cx, cy, width, height, rotation) and legacy AABB format
            if "cx" in bbox:
                # OBB format
                cx = float(bbox["cx"])
                cy = float(bbox["cy"])
                w = float(bbox["width"])
                h = float(bbox["height"])
                rotation = float(bbox.get("rotation", 0.0))
                # Create rect from center, width, height
                xmin = cx - w / 2
                ymin = cy - h / 2
                xmax = cx + w / 2
                ymax = cy + h / 2
            else:
                # Legacy AABB format
                xmin = float(bbox.get("xmin", 0))
                ymin = float(bbox.get("ymin", 0))
                xmax = float(bbox.get("xmax", 0))
                ymax = float(bbox.get("ymax", 0))
                rotation = float(bbox.get("rotation", 0.0))
                
            rect = QRectF(QPointF(xmin, ymin), QPointF(xmax, ymax))
            label = str(bbox.get("label", BBOX_CLASSES[0]))
            self._create_bbox(rect, rotation=rotation, label=label, emit=False)
        self.countsChanged.emit(*self._count_items())

    def _create_point(
        self,
        label: str,
        scene_pos: QPointF,
        point_id: str | None = None,
        emit: bool = True,
        radius: float | None = None,
    ) -> None:
        if point_id is None:
            point_id = uuid.uuid4().hex
        label = normalize_class(label)
        clamped_pos = self._clamp_to_image(scene_pos)
        point_radius = radius if radius is not None else self._dot_radius
        item = LandmarkPointItem(point_id, label, self._image_rect, radius=point_radius)
        item.setPos(clamped_pos)
        item.moved.connect(self._on_point_moved)
        item.deleteRequested.connect(self._on_point_deleted)
        item.selected.connect(self._on_point_selected)
        self._scene.addItem(item)
        self._point_items[point_id] = item
        self._points[point_id] = {
            "x": clamped_pos.x(),
            "y": clamped_pos.y(),
            "class": label,
            "radius": point_radius,
        }
        self._select_point(item)
        if emit:
            self._emit_state_changed()
        
        # Initialize with correct mode state
        item.set_bbox_mode(self._mode == CanvasMode.BBOX)

    def _create_bone_line(self, points: List[QPointF], line_id: str | None = None, emit: bool = True) -> BoneLineItem:
        if line_id is None:
            line_id = uuid.uuid4().hex
        
        item = BoneLineItem(line_id, points, self._image_rect)
        item.lineChanged.connect(self._on_bone_line_changed)
        item.deleteRequested.connect(self._on_bone_line_deleted)
        item.selected.connect(self._on_bone_line_selected)
        
        # visibility based on current mode?
        is_bone = (self._mode == CanvasMode.BONE)
        item.setAcceptHoverEvents(is_bone)
        if is_bone:
            item.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
        else:
            item.setAcceptedMouseButtons(Qt.NoButton)
             
        self._scene.addItem(item)
        self._bone_line_items[line_id] = item
        self._bone_lines[line_id] = [{"x": p.x(), "y": p.y()} for p in points]
        
        if emit:
            self._emit_state_changed()
            
        return item

    def _create_bbox(self, rect: QRectF, rotation: float = 0.0, label: str | None = None, emit: bool = True) -> None:
        bbox_id = self._next_bbox_id
        self._next_bbox_id += 1
        
        # Auto-label based on current filter
        if label is not None:
            final_label = label
        elif self._bbox_filter in ["All", "Unlabeled"]:
            final_label = "Unlabeled"
        else:
            # Filter is set to a specific class, auto-label with that class
            final_label = self._bbox_filter
        item = BoundingBoxItem(bbox_id, rect, self._image_rect, rotation=rotation, label=final_label)
        item.moved.connect(self._on_bbox_moved)
        item.deleteRequested.connect(self._on_bbox_deleted)
        item.selected.connect(self._on_bbox_selected)
        item.labelChanged.connect(self._on_bbox_label_changed)
        
        # Set landmark mode based on current canvas mode
        is_landmark = (self._mode == CanvasMode.LANDMARK)
        is_bone = (self._mode == CanvasMode.BONE)
        item.set_landmark_mode(is_landmark or is_bone)
        
        self._scene.addItem(item)
        self._bbox_items[bbox_id] = item
        
        # Store in OBB format
        cx = rect.center().x()
        cy = rect.center().y()
        w = rect.width()
        h = rect.height()
        
        self._bboxes[bbox_id] = {
            "id": bbox_id,
            "cx": cx,
            "cy": cy,
            "width": w,
            "height": h,
            "rotation": rotation,
            "label": final_label,
        }
        
        if emit:
            self._emit_state_changed()

    def add_point_at(self, scene_pos: QPointF, label: str) -> None:
        if not self.has_image():
            return
        self._create_point(label, scene_pos)

    def set_bbox_draw_mode(self, mode: BBoxDrawMode) -> None:
        """Set the bounding box drawing mode (drag or three-point)."""
        self._bbox_draw_mode = mode
        self._clear_three_point_state()

    def _handle_three_point_click(self, pos: QPointF) -> None:
        """Handle click events for three-point bbox drawing."""
        if not self._image_rect.contains(pos):
            return
        
        self._three_point_corners.append(pos)
        
        if len(self._three_point_corners) == 3:
            # Create the bbox
            rect, rotation = self._calculate_obb_from_three_points()
            if rect.width() > BoundingBoxItem.MIN_SIZE and rect.height() > BoundingBoxItem.MIN_SIZE:
                self._create_bbox(rect, rotation=rotation)
            self._clear_three_point_state()

    def _update_three_point_preview(self, cursor_pos: QPointF) -> None:
        """Update the preview visualization for three-point drawing."""
        # Clear existing preview items
        if self._preview_line:
            self._scene.removeItem(self._preview_line)
            self._preview_line = None
        if self._preview_polygon:
            self._scene.removeItem(self._preview_polygon)
            self._preview_polygon = None
        
        if not self._three_point_corners:
            return
        
        if len(self._three_point_corners) == 1:
            # Draw line from first point to cursor
            pen = QPen(QColor(255, 255, 0), 2, Qt.DashLine)
            self._preview_line = QGraphicsLineItem(
                self._three_point_corners[0].x(),
                self._three_point_corners[0].y(),
                cursor_pos.x(),
                cursor_pos.y()
            )
            self._preview_line.setPen(pen)
            self._preview_line.setZValue(10)
            self._scene.addItem(self._preview_line)
            
        elif len(self._three_point_corners) == 2:
            # Draw preview polygon showing the prospective bbox
            # pylint: disable=no-name-in-module
            from PyQt5.QtGui import QPolygonF, QBrush
            # pylint: enable=no-name-in-module
            
            p1, p2 = self._three_point_corners[0], self._three_point_corners[1]
            p3 = cursor_pos
            
            # Calculate the fourth corner
            # p1 = top-left, p2 = top-right, p3 = bottom-right
            # p4 = bottom-left
            # Vector from p1 to p2 is the top edge
            # Vector from p2 to p3 is the right edge
            # p4 = p1 + (p3 - p2)
            p4 = QPointF(
                p1.x() + (p3.x() - p2.x()),
                p1.y() + (p3.y() - p2.y())
            )
            
            polygon = QPolygonF([p1, p2, p3, p4])
            self._preview_polygon = QGraphicsPolygonItem(polygon)
            self._preview_polygon.setPen(QPen(QColor(255, 255, 0), 2, Qt.DashLine))
            self._preview_polygon.setBrush(QBrush(QColor(255, 255, 0, 50)))
            self._preview_polygon.setZValue(10)
            self._scene.addItem(self._preview_polygon)

    def _clear_three_point_state(self) -> None:
        """Clear three-point drawing state and preview items."""
        self._three_point_corners.clear()
        if self._preview_line:
            self._scene.removeItem(self._preview_line)
            self._preview_line = None
        if self._preview_polygon:
            self._scene.removeItem(self._preview_polygon)
            self._preview_polygon = None

    def _calculate_obb_from_three_points(self) -> tuple[QRectF, float]:
        """Calculate oriented bounding box from three corner points.
        
        Points are: top-left, top-right, bottom-right
        Returns: (rect, rotation_angle)
        """
        if len(self._three_point_corners) != 3:
            return QRectF(), 0.0
        
        p1, p2, p3 = self._three_point_corners
        
        # Calculate width (distance from p1 to p2)
        width = math.sqrt((p2.x() - p1.x())**2 + (p2.y() - p1.y())**2)
        
        # Calculate height (distance from p2 to p3)
        height = math.sqrt((p3.x() - p2.x())**2 + (p3.y() - p2.y())**2)
        
        # Calculate rotation (angle from p1 to p2)
        rotation = math.degrees(math.atan2(p2.y() - p1.y(), p2.x() - p1.x()))
        
        # Calculate center
        # The center is at the middle of the diagonal from p1 to p3
        center_x = (p1.x() + p3.x()) / 2
        center_y = (p1.y() + p3.y()) / 2
        
        # Create rect centered at origin (will be positioned by setPos in BoundingBoxItem)
        rect = QRectF(
            center_x - width / 2,
            center_y - height / 2,
            width,
            height
        )
        
        return rect, rotation

    def _on_point_moved(self, point_id: str, x: float, y: float) -> None:
        self._points[point_id]["x"] = x
        self._points[point_id]["y"] = y
        self._emit_state_changed()
        item = self._point_items.get(point_id)
        if self._selected_point_id == point_id and item is not None:
            self._update_magnifier(QPointF(x, y), self._points[point_id]["class"], item.radius())

    def _on_point_selected(self, point_id: str) -> None:
        item = self._point_items.get(point_id)
        if item:
            self._select_point(item)

    def _on_point_deleted(self, point_id: str) -> None:
        item = self._point_items.pop(point_id, None)
        if item:
            self._scene.removeItem(item)
        if point_id in self._points:
            del self._points[point_id]
        if self._selected_point_id == point_id:
            self._selected_point_id = None
            self._hide_magnifier()
        self._emit_state_changed()

    def _on_bbox_moved(self, bbox_id: int, x_center: float, y_center: float, width: float, height: float, rotation: float) -> None:
        if bbox_id in self._bboxes:
            # We store rect as xmin, ymin, xmax, ymax relative to the item's center?
            # No, BoundingBoxItem stores _rect in local coordinates.
            # But for serialization, we want to store enough info to recreate it.
            # If we store xmin, ymin, xmax, ymax, that defines the size and local origin offset.
            # And we store rotation.
            # But we also need the position (center) in the scene if we used setPos.
            # Wait, in BoundingBoxItem, I used setPos for movement.
            # So the item's position in the scene is (x_center, y_center) roughly?
            # No, setPos sets the origin of the item.
            # If _rect is centered around (0,0), then setPos is the center.
            # But _rect might not be centered around (0,0).
            # In _create_bbox, I pass `rect`.
            # If I draw a box from (100,100) to (200,200), `rect` is (100,100, 100, 100).
            # The item is at (0,0).
            # If I rotate it, it rotates around (0,0).
            # This means it rotates around the top-left of the SCENE (0,0). This is BAD.
            # I need the item to rotate around its own center.
            
            # CORRECTION:
            # To rotate around its center, I should set the item's position to the center of the rect,
            # and set the local rect to be centered at (0,0).
            
            # I need to refactor `_create_bbox` and `BoundingBoxItem` slightly to handle this "centering".
            # Or `BoundingBoxItem` should handle it.
            # If I change `BoundingBoxItem` to always center itself on creation:
            # 1. Calculate center of `rect`.
            # 2. Set item pos to center.
            # 3. Set local `_rect` to `rect` translated by `-center`.
            
            # Let's assume I will fix `BoundingBoxItem` or `_create_bbox` logic.
            # For now, let's update `_on_bbox_moved` to store what we get.
            # The signal sends (id, x_center, y_center, width, height, rotation).
            # I should store these.
            # But `_bboxes` currently stores xmin, ymin, xmax, ymax.
            # I should change `_bboxes` structure to be OBB friendly: cx, cy, w, h, rotation.
            
            self._bboxes[bbox_id] = {
                "id": bbox_id,
                "cx": x_center,
                "cy": y_center,
                "width": width,
                "height": height,
                "rotation": rotation,
                "label": self._bboxes[bbox_id].get("label", BBOX_CLASSES[0]),
            }
            self._emit_state_changed()

    def _on_bbox_label_changed(self, bbox_id: int, label: str) -> None:
        if bbox_id in self._bboxes:
            self._bboxes[bbox_id]["label"] = label
            self._emit_state_changed()

    def _on_bbox_selected(self, bbox_id: int) -> None:
        item = self._bbox_items.get(bbox_id)
        if item:
            self._select_bbox(item)

    def _on_bbox_deleted(self, bbox_id: int) -> None:
        item = self._bbox_items.pop(bbox_id, None)
        if item:
            self._scene.removeItem(item)
        if bbox_id in self._bboxes:
            del self._bboxes[bbox_id]
        if self._selected_bbox_id == bbox_id:
            self._selected_bbox_id = None
        self._emit_state_changed()

    def _select_point(self, item: LandmarkPointItem | None) -> None:
        if item is not None:
            self._select_bbox(None) # Deselect bbox if selecting a point
        
        if self._selected_point_id and self._selected_point_id in self._point_items:
            self._point_items[self._selected_point_id].set_selected(False)
        if item is not None:
            self._selected_point_id = item.point_id
            item.set_selected(True)
            self._update_magnifier(item.pos(), self._points.get(item.point_id, {}).get("class"), item.radius())
        else:
            self._selected_point_id = None
            self._hide_magnifier()

    def _select_bbox(self, item: BoundingBoxItem | None) -> None:
        if item is not None:
            self._select_point(None) # Deselect point if selecting a bbox
        
        if self._selected_bbox_id is not None and self._selected_bbox_id in self._bbox_items:
            self._bbox_items[self._selected_bbox_id].set_selected(False)
        
        if item is not None:
            self._selected_bbox_id = item.bbox_id
            item.set_selected(True)
        else:
            self._selected_bbox_id = None

    def deselect_all(self) -> None:
        """Deselect all items without cancelling tools."""
        self._select_point(None)
        self._select_bbox(None)

    def clear_selection(self) -> None:
        """Deselect all items and cancel current tool operations (e.g. 3-point draw)."""
        self.deselect_all()
        self._clear_three_point_state()
        self.viewport().setCursor(Qt.ArrowCursor if not self.has_image() else Qt.CrossCursor)

    def delete_selected_item(self) -> None:
        if self._selected_point_id is not None:
            self._on_point_deleted(self._selected_point_id)
        elif self._selected_bbox_id is not None:
            self._on_bbox_deleted(self._selected_bbox_id)

    def has_selected_point(self) -> bool:
        return self._selected_point_id is not None

    def move_selected_point(self, dx: float, dy: float) -> None:
        if self._selected_point_id is None:
            return
        item = self._point_items.get(self._selected_point_id)
        if item is None:
            return
        new_pos = self._clamp_to_image(item.pos() + QPointF(dx, dy))
        item.setPos(new_pos)
        point = self._points.get(self._selected_point_id)
        if point is not None:
            point["x"] = new_pos.x()
            point["y"] = new_pos.y()
        self._update_magnifier(
            new_pos,
            self._points.get(self._selected_point_id, {}).get("class"),
            item.radius(),
        )
        self._emit_state_changed()

    def set_adjustments(self, brightness: int, contrast: int, gamma: float) -> None:
        self._brightness = brightness
        self._contrast = contrast
        self._gamma = max(0.1, gamma)
        self._apply_adjustments()

    def set_enhancements(self, auto_enhance: bool, edge_enhance: bool) -> None:
        self._auto_enhance = auto_enhance
        self._edge_enhance = edge_enhance
        self._apply_adjustments()

    def _apply_adjustments(self) -> None:
        if self._original_np is None:
            return
        arr = self._original_np.astype(np.float32)
        rgb = arr[..., :3]
        if self._auto_enhance:
            rgb = self._auto_enhance_channels(rgb)
        rgb = rgb * (1.0 + self._contrast / 100.0) + self._brightness
        rgb = np.clip(rgb, 0, 255)
        gamma = max(0.1, self._gamma)
        norm = np.clip(rgb / 255.0, 0, 1)
        rgb = np.power(norm, 1.0 / gamma) * 255.0
        if self._edge_enhance:
            rgb = self._edge_enhance_channels(rgb)
        arr[..., :3] = np.clip(rgb, 0, 255)
        arr = arr.astype(np.uint8)
        height, width, _ = arr.shape
        qimage = QImage(arr.data, width, height, width * 4, QImage.Format_RGBA8888).copy()
        self._display_qimage = qimage
        self._pixmap_item.setPixmap(QPixmap.fromImage(qimage))
        self._update_magnifier_from_selection()

    def serialize_points(self) -> List[Dict[str, float | str]]:
        return [
            {"x": round(data["x"], 3), "y": round(data["y"], 3), "class": data["class"], "radius": data.get("radius")}
            for data in self._points.values()
        ]

    def serialize_bboxes(self) -> List[Dict[str, int | float | str]]:
        return [
            {
                "id": data["id"], 
                "cx": round(data["cx"], 1), 
                "cy": round(data["cy"], 1), 
                "width": round(data["width"], 1), 
                "height": round(data["height"], 1),
                "rotation": round(data["rotation"], 1),
                "label": data.get("label", BBOX_CLASSES[0]),
            }
            for data in self._bboxes.values()
        ]

    def serialize_bone_lines(self) -> List[List[Dict[str, float]]]:
        return list(self._bone_lines.values())

    def _emit_state_changed(self) -> None:
        self.pointsUpdated.emit(self.serialize_points())
        self.bboxesUpdated.emit(self.serialize_bboxes())
        self.boneLinesUpdated.emit(self.serialize_bone_lines())
        self.countsChanged.emit(*self._count_items())

    def _count_items(self) -> tuple[int, int, int]:
        cej = sum(1 for data in self._points.values() if data["class"] == "CEJ")
        crest = sum(1 for data in self._points.values() if data["class"] == "CREST")
        bboxes = len(self._bboxes)
        return cej, crest, bboxes

    def _on_bone_line_changed(self, line_id: str, points: List[Dict[str, float]]) -> None:
        if line_id in self._bone_lines:
            self._bone_lines[line_id] = points
            self._emit_state_changed()

    def _on_bone_line_selected(self, line_id: str) -> None:
        item = self._bone_line_items.get(line_id)
        if item:
            self._select_bone_line(item)

    def _on_bone_line_deleted(self, line_id: str) -> None:
        item = self._bone_line_items.pop(line_id, None)
        if item:
            self._scene.removeItem(item)
        if line_id in self._bone_lines:
            del self._bone_lines[line_id]
        if self._selected_bone_line_id == line_id:
            self._selected_bone_line_id = None
        if self._current_bone_line_item == item:
            self._current_bone_line_item = None
            self._drawing_bone_line = False
            self._current_bone_line_points = []
        self._emit_state_changed()

    def _select_bone_line(self, item: BoneLineItem | None) -> None:
        if item is not None:
            self._select_point(None)
            self._select_bbox(None)
        
        if self._selected_bone_line_id and self._selected_bone_line_id in self._bone_line_items:
            self._bone_line_items[self._selected_bone_line_id].set_selected(False)
        
        if item is not None:
            self._selected_bone_line_id = item.line_id
            item.set_selected(True)
        else:
            self._selected_bone_line_id = None

    def _clamp_to_image(self, pos: QPointF) -> QPointF:
        if self._image_rect.isNull():
            return pos
        x = min(max(self._image_rect.left(), pos.x()), self._image_rect.right())
        y = min(max(self._image_rect.top(), pos.y()), self._image_rect.bottom())
        return QPointF(x, y)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        # Handle Right Click for Bone Line context menu
        if event.button() == Qt.RightButton:
            if self._mode == CanvasMode.BONE:
                self._show_bone_context_menu(event.pos())
                event.accept()
                return

        if event.button() == Qt.MiddleButton or (
            event.button() == Qt.LeftButton and (self._space_held or event.modifiers() & Qt.ShiftModifier)
        ):
            self._panning = True
            self._pan_start = event.pos()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())
            
            # Handle existing items
            if isinstance(item, LandmarkPointItem):
                self._select_point(item)
                super().mousePressEvent(event)
                return
            elif isinstance(item, BoundingBoxItem):
                # Only interact with bboxes in BBOX mode
                if self._mode == CanvasMode.BBOX:
                    self._select_bbox(item)
                    super().mousePressEvent(event)
                    return
                # In landmark mode, ignore bbox and fall through to add landmark
            
            self.deselect_all()
            
            if self.has_image():
                if self._mode == CanvasMode.BBOX:
                    if self._bbox_draw_mode == BBoxDrawMode.THREE_POINT:
                        # Three-point mode: handle click for corner placement
                        scene_pos = self.mapToScene(event.pos())
                        self._handle_three_point_click(scene_pos)
                        event.accept()
                        return
                    else:
                        # Drag mode: existing behavior  
                        self._drawing_bbox = True
                        self._bbox_start = self.mapToScene(event.pos())
                        self._current_bbox_item = None
                        event.accept()
                        return
                elif self._mode == CanvasMode.LANDMARK:
                    self._show_add_point_menu(event.pos())
                    return
                elif self._mode == CanvasMode.BONE:
                    # In Bone Mode, left click on empty space does nothing (except deselect handled above)
                    pass

        super().mousePressEvent(event)

    def _show_bone_context_menu(self, pos) -> None:
        scene_pos = self.mapToScene(pos)
        if not self._image_rect.contains(scene_pos):
            return
            
        # Try to find a bone line under the cursor if nothing is selected
        if not self._selected_bone_line_id:
            items_at = self.items(scene_pos)
            for item in items_at:
                if isinstance(item, BoneLineItem):
                    self._select_bone_line(item)
                    break

        menu = QMenu(self)
        add_action = menu.addAction("Add Point")
        
        # If we have a selected bone line, we add to it
        # If not, we start a new one
        if self._selected_bone_line_id:
            add_action.setText("Add Point to Selected Line")
        else:
            add_action.setText("Start New Bone Line")
            
        action = menu.exec_(self.viewport().mapToGlobal(pos))
        
        if action == add_action:
            if self._selected_bone_line_id and self._selected_bone_line_id in self._bone_line_items:
                item = self._bone_line_items[self._selected_bone_line_id]
                item.add_point(scene_pos)
                # Update our internal storage
                self._bone_lines[self._selected_bone_line_id] = item.get_points()
                self._emit_state_changed()
            else:
                # Start new line
                newItem = self._create_bone_line([scene_pos])
                newItem.set_selected(True)
                self._select_bone_line(newItem)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
            
        if self._drawing_bbox:
            current_pos = self.mapToScene(event.pos())
            rect = QRectF(self._bbox_start, current_pos).normalized()
            if self._current_bbox_item is None:
                # Create temporary item (defaults to Unlabeled)
                self._current_bbox_item = BoundingBoxItem(-1, rect, self._image_rect, label="Unlabeled")
                self._scene.addItem(self._current_bbox_item)
            else:
                # Update temporary item
                # We need to manually update the rect since BoundingBoxItem stores it internally
                # But BoundingBoxItem doesn't expose a setRect method in my previous implementation
                # I should have added one. For now, I'll remove and recreate or just access protected member if I can't change it easily.
                # Actually, I can just modify the _rect member since I'm in the same package/module context effectively? No.
                # I'll just remove and add for simplicity or better yet, assume I can update it.
                # Let's just recreate it for visual feedback or better, update BoundingBoxItem to have setRect.
                # Since I can't easily update BoundingBoxItem now without another tool call, I'll just remove and add.
                self._scene.removeItem(self._current_bbox_item)
                self._current_bbox_item = BoundingBoxItem(-1, rect, self._image_rect, label="Unlabeled")
                self._scene.addItem(self._current_bbox_item)
            event.accept()
            return
        
        # Three-point mode preview
        if self._mode == CanvasMode.BBOX and self._bbox_draw_mode == BBoxDrawMode.THREE_POINT:
            scene_pos = self.mapToScene(event.pos())
            if self._three_point_corners:
                self._update_three_point_preview(scene_pos)

        # Bone Line Preview (Rubber banding)
        if self._drawing_bone_line and self._current_bone_line_item:
           # Rubber banding support could be added here by updating the last point
           # But for now, we just stick to click-to-add without dynamic preview line.
           # To implement: update self._current_bone_line_item.points[-1] if we added a tracking point.
           pass

        self._update_hover_cursor(event.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._panning and event.button() in (Qt.LeftButton, Qt.MiddleButton):
            self._panning = False
            self._update_hover_cursor(event.pos())
            event.accept()
            return
            
        if self._drawing_bbox and event.button() == Qt.LeftButton:
            self._drawing_bbox = False
            if self._current_bbox_item:
                self._scene.removeItem(self._current_bbox_item)
                rect = self._current_bbox_item.boundingRect() # This includes handles, wait.
                # I need the actual rect.
                # Let's use the start and end points.
                end_pos = self.mapToScene(event.pos())
                rect = QRectF(self._bbox_start, end_pos).normalized()
                
                if rect.width() > BoundingBoxItem.MIN_SIZE and rect.height() > BoundingBoxItem.MIN_SIZE:
                    self._create_bbox(rect)
                
                self._current_bbox_item = None
            event.accept()
            return
            
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if not self.has_image():
            return
        delta = event.angleDelta().y() / 120
        if delta == 0:
            return
        factor = 1.15 ** delta
        self._set_zoom(self._zoom_factor * factor, centered=False)

    def zoom_in(self) -> None:
        self._set_zoom(self._zoom_factor * 1.1, centered=True)

    def zoom_out(self) -> None:
        self._set_zoom(self._zoom_factor / 1.1, centered=True)

    def reset_zoom(self) -> None:
        self._set_zoom(1.0, centered=True)

    def _set_zoom(self, zoom: float, centered: bool) -> None:
        if self._image_rect.isNull():
            return
        zoom = max(0.2, min(zoom, 8.0))
        ratio = zoom / self._zoom_factor
        if math.isclose(ratio, 1.0, abs_tol=1e-4):
            return
        anchor = QGraphicsView.AnchorViewCenter if centered else QGraphicsView.AnchorUnderMouse
        self.setTransformationAnchor(anchor)
        self.scale(ratio, ratio)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self._zoom_factor = zoom
        self._update_zoom_percent()
        self._position_magnifier()

    def _update_zoom_percent(self) -> None:
        if self._base_scale <= 0:
            self._base_scale = 1.0
        current_scale = self.transform().m11()
        percent = int(current_scale / self._base_scale * 100)
        self._zoom_percent = percent
        self.zoomChanged.emit(percent)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._image_rect.isNull():
            return
        prev_zoom = self._zoom_factor
        self.fitInView(self._image_rect, Qt.KeepAspectRatio)
        self._base_transform = self.transform()
        self._base_scale = max(1e-6, self.transform().m11())
        self.resetTransform()
        self.setTransform(self._base_transform)
        self._zoom_factor = 1.0
        self._update_zoom_percent()
        if not math.isclose(prev_zoom, 1.0, abs_tol=1e-3):
            self._set_zoom(prev_zoom, centered=True)
        self._position_magnifier()

    def scrollContentsBy(self, dx: int, dy: int) -> None:  # type: ignore[override]
        super().scrollContentsBy(dx, dy)
        self._position_magnifier()

    def _position_magnifier(self) -> None:
        margin = 16
        x = self.viewport().width() - self._magnifier.width() - margin
        y = margin
        self._magnifier.move(max(margin, x), y)

    def _update_magnifier(self, scene_pos: QPointF, label: str | None = None, radius: float | None = None) -> None:
        if self._display_qimage is None or self._selected_point_id is None:
            return
        x = int(scene_pos.x())
        y = int(scene_pos.y())
        half = 30
        rect = QRect(x - half, y - half, half * 2, half * 2)
        rect = rect.intersected(self._display_qimage.rect())
        if rect.isEmpty():
            self._hide_magnifier()
            return
        if rect.width() == 0 or rect.height() == 0:
            self._hide_magnifier()
            return
        snippet = self._display_qimage.copy(rect)
        pix = QPixmap.fromImage(
            snippet.scaled(
                self._magnifier.width(),
                self._magnifier.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        class_label = label or self._points.get(self._selected_point_id, {}).get("class")
        color = QColor(LANDMARK_COLORS.get(class_label, "#4DA3FF"))
        width_scale = pix.width() / rect.width()
        height_scale = pix.height() / rect.height()
        center_x = (scene_pos.x() - rect.left()) * width_scale
        center_y = (scene_pos.y() - rect.top()) * height_scale
        scaled_radius = max(width_scale, height_scale) * ((radius or LandmarkPointItem.DEFAULT_RADIUS) + 3)
        painter.setPen(QPen(QColor("#000000"), 5))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(center_x, center_y), scaled_radius, scaled_radius)
        painter.setPen(QPen(color, 3))
        painter.drawEllipse(QPointF(center_x, center_y), scaled_radius - 3, scaled_radius - 3)
        painter.end()
        self._magnifier.setPixmap(pix)
        self._position_magnifier()
        self._magnifier.show()

    def _update_magnifier_from_selection(self) -> None:
        if self._selected_point_id and self._selected_point_id in self._point_items:
            item = self._point_items[self._selected_point_id]
            self._update_magnifier(
                item.pos(),
                self._points.get(self._selected_point_id, {}).get("class"),
                item.radius(),
            )

    def _hide_magnifier(self) -> None:
        self._magnifier.hide()

    def event(self, event) -> bool:  # type: ignore[override]
        if event.type() == QEvent.Gesture:
            return self._handle_gesture(event)
        return super().event(event)

    def _handle_gesture(self, event: QGestureEvent) -> bool:
        pinch = event.gesture(Qt.PinchGesture)
        if pinch is not None:
            factor = pinch.scaleFactor()
            self._set_zoom(self._zoom_factor * factor, centered=False)
            return True
        return False

    def _auto_enhance_channels(self, rgb: np.ndarray) -> np.ndarray:
        reshaped = rgb.reshape(-1, 3)
        min_vals = reshaped.min(axis=0)
        max_vals = reshaped.max(axis=0)
        denom = np.maximum(max_vals - min_vals, 1e-3)
        enhanced = (rgb - min_vals) / denom * 255.0
        return np.clip(enhanced, 0, 255)

    def _edge_enhance_channels(self, rgb: np.ndarray) -> np.ndarray:
        padded = np.pad(rgb, ((1, 1), (1, 1), (0, 0)), mode="reflect")
        center = padded[1:-1, 1:-1]
        neighbors = (
            padded[:-2, 1:-1]
            + padded[2:, 1:-1]
            + padded[1:-1, :-2]
            + padded[1:-1, 2:]
        )
        laplacian = 4 * center - neighbors
        enhanced = center + 0.3 * laplacian
        return np.clip(enhanced, 0, 255)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key_Space:
            self._space_held = True
            self.viewport().setCursor(Qt.OpenHandCursor)
            event.accept()
            return
        if event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            if self._selected_point_id is not None:
                step = 1.0 if not (event.modifiers() & Qt.ShiftModifier) else 5.0
                dx = dy = 0.0
                if event.key() == Qt.Key_Left:
                    dx = -step
                elif event.key() == Qt.Key_Right:
                    dx = step
                elif event.key() == Qt.Key_Up:
                    dy = -step
                elif event.key() == Qt.Key_Down:
                    dy = step
                self.move_selected_point(dx, dy)
                event.accept()
                return
        
        # Three-point mode keyboard controls
        if self._mode == CanvasMode.BBOX and self._bbox_draw_mode == BBoxDrawMode.THREE_POINT:
            if event.key() == Qt.Key_Backspace and self._three_point_corners:
                # Remove last clicked point
                self._three_point_corners.pop()
                self._update_three_point_preview(self.mapToScene(self.mapFromGlobal(QCursor.pos())))
                event.accept()
                return
            elif event.key() == Qt.Key_Escape:
                # Cancel three-point operation
                self._clear_three_point_state()
                event.accept()
                return
        
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected_item()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.key() == Qt.Key_Space:
            self._space_held = False
            self._update_hover_cursor(self.mapFromGlobal(QCursor.pos()))
            event.accept()
            return
        super().keyReleaseEvent(event)

    def _show_add_point_menu(self, pos) -> None:
        scene_pos = self.mapToScene(pos)
        if not self._image_rect.contains(scene_pos):
            return
        menu = QMenu(self)
        cej_action = menu.addAction("CEJ")
        crest_action = menu.addAction("CREST")
        apex_action = menu.addAction("APEX")
        menu.addSeparator()
        action = menu.exec_(self.viewport().mapToGlobal(pos))
        if action == cej_action:
            self.add_point_at(scene_pos, "CEJ")
        elif action == crest_action:
            self.add_point_at(scene_pos, "CREST")
        elif action == apex_action:
            self.add_point_at(scene_pos, "APEX")

    def _update_hover_cursor(self, pos) -> None:
        if self._panning:
            return
        item = self.itemAt(pos)
        if isinstance(item, (LandmarkPointItem, BoundingBoxItem)):
            # Let the item handle the cursor if it wants, or set a default
            # BoundingBoxItem handles its own cursor in hoverMoveEvent
            # LandmarkPointItem also does
            pass
        else:
            if self._mode == CanvasMode.BBOX:
                self.viewport().setCursor(Qt.CrossCursor)
            else:
                self.viewport().setCursor(Qt.CrossCursor if self.has_image() else Qt.ArrowCursor)
