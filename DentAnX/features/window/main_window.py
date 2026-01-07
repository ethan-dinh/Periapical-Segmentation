from __future__ import annotations

import shutil
from pathlib import Path
from typing import List, Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QAbstractSpinBox,
    QAction,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QShortcut,
    QStatusBar,
    QTextEdit,
    QWidget,
)

from ...data.annotation_manager import AnnotationManager, AnnotationRecord
from ...ui.theme import load_stylesheet
from ..canvas.image_canvas import ImageCanvas
from ..sidebar.panel import SidePanel


class AnnotationMainWindow(QMainWindow):
    """Top-level window orchestrating the sidebar, canvas, and autosave logic."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Bitewing Landmark Annotator")
        self.resize(1280, 800)
        self.setStyleSheet(load_stylesheet())

        self.annotation_manager = AnnotationManager()
        self.image_files: List[str] = []
        self.current_index = -1
        self.current_dimensions = (0, 0)
        self._pending_points: Optional[List[dict]] = None
        self._pending_bboxes: Optional[List[dict]] = None

        self.canvas = ImageCanvas()
        self.sidebar = SidePanel()

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(18)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.canvas, 1)
        self.setCentralWidget(central)

        self._build_menu()
        self._build_status_bar()
        self._build_shortcuts()

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(400)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._perform_autosave)

        self.sidebar.openFolderRequested.connect(self.open_folder)
        self.sidebar.prevRequested.connect(self.show_previous_image)
        self.sidebar.nextRequested.connect(self.show_next_image)
        self.sidebar.exportRequested.connect(self.export_annotations)
        self.sidebar.jumpRequested.connect(self.jump_to_image)
        self.sidebar.flagRequested.connect(self.flag_current_image)
        self.sidebar.modeChanged.connect(self.canvas.set_mode)
        self.sidebar.bboxFilterChanged.connect(self.canvas.set_bbox_filter)
        self.sidebar.bboxDrawModeChanged.connect(self.canvas.set_bbox_draw_mode)

        self.canvas.pointsUpdated.connect(self._on_points_updated)
        self.canvas.bboxesUpdated.connect(self._on_bboxes_updated)
        self.canvas.boneLinesUpdated.connect(self._on_bone_lines_updated)
        self.canvas.countsChanged.connect(self.sidebar.set_counts)
        self.canvas.zoomChanged.connect(self._update_zoom_label)
        self.sidebar.adjustmentsChanged.connect(self._on_adjustments_changed)
        self.sidebar.enhancementToggled.connect(self._on_enhancement_toggled)

        self.sidebar.set_controls_enabled(False)
        self.sidebar.set_navigation_state(False, False)
        self._current_brightness = 0
        self._current_contrast = 0
        self._current_gamma = 1.0
        self._auto_enhance = False
        self._edge_enhance = False
        self._pending_bone_lines: Optional[List[List[dict]]] = None

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        open_action = QAction("Open Folder", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self.open_folder)
        file_menu.addAction(open_action)

        export_action = QAction("Export All Annotations", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self.export_annotations)
        file_menu.addAction(export_action)

        save_action = QAction("Save Current Image", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self.save_current_image)
        file_menu.addAction(save_action)

        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _build_status_bar(self) -> None:
        status = QStatusBar()
        status.setSizeGripEnabled(False)
        self.zoom_label = QLabel("Zoom: 100%")
        self.autosave_label = QLabel("Saved ✓")
        self.autosave_label.setStyleSheet("color: #61D0B5;")
        status.addPermanentWidget(self.zoom_label)
        status.addPermanentWidget(self.autosave_label)
        self.setStatusBar(status)

    def _build_shortcuts(self) -> None:
        QShortcut(
            QKeySequence(Qt.Key_A),
            self,
            activated=lambda: self._navigate_if_allowed(self.show_previous_image, allow_with_selection=True),
        )
        QShortcut(
            QKeySequence(Qt.Key_D),
            self,
            activated=lambda: self._navigate_if_allowed(self.show_next_image, allow_with_selection=True),
        )
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.canvas.clear_selection)
        QShortcut(QKeySequence.ZoomIn, self, activated=self.canvas.zoom_in)
        QShortcut(QKeySequence.ZoomOut, self, activated=self.canvas.zoom_out)
        for seq in ("Ctrl++", "Ctrl+=", "Meta++", "Meta+=", "Ctrl+Plus", "Meta+Plus"):
            QShortcut(QKeySequence(seq), self, activated=self.canvas.zoom_in)
        for seq in ("Ctrl+-", "Ctrl+_", "Meta+-", "Meta+_", "Ctrl+Minus", "Meta+Minus"):
            QShortcut(QKeySequence(seq), self, activated=self.canvas.zoom_out)
        QShortcut(QKeySequence(Qt.Key_Delete), self, activated=self.canvas.delete_selected_item)
        QShortcut(QKeySequence(Qt.Key_Backspace), self, activated=self.canvas.delete_selected_item)

    def open_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if not directory:
            return
        self._load_directory(directory)

    def _load_directory(self, path: str) -> None:
        try:
            files = self.annotation_manager.set_image_directory(path)
        except FileNotFoundError:
            QMessageBox.warning(self, "Folder Not Found", "The selected folder could not be opened.")
            return
        self.image_files = files
        if not files:
            QMessageBox.information(self, "No Images", "The selected folder does not contain supported images.")
            self.current_index = -1
            self.canvas.clear()
            self.sidebar.set_controls_enabled(False)
            self.sidebar.set_navigation_state(False, False)
            self.sidebar.set_file_info("", 0, 0)
            self.autosave_label.setText("Idle")
            self.autosave_label.setStyleSheet("color: #9A9A9A;")
            return
        self.sidebar.set_controls_enabled(True)
        self._autosave_timer.stop()
        self._load_image_at_index(0)

    def _load_image_at_index(self, index: int) -> None:
        if not (0 <= index < len(self.image_files)):
            return
        assert self.annotation_manager.image_dir is not None
        file_name = self.image_files[index]
        image_path = str(self.annotation_manager.image_dir / file_name)
        try:
            width, height = self.canvas.load_image(image_path)
        except ValueError as exc:
            QMessageBox.critical(self, "Load Error", str(exc))
            return
        self.canvas.set_adjustments(self._current_brightness, self._current_contrast, self._current_gamma)
        self.canvas.set_enhancements(self._auto_enhance, self._edge_enhance)
        record = self.annotation_manager.load(file_name, width, height)
        self.current_dimensions = (record.width, record.height)
        self.current_index = index
        self._autosave_timer.stop()
        self.canvas.set_points(record.points)
        self.canvas.set_bboxes(record.bboxes)
        self.canvas.set_bone_lines(record.bone_lines)
        self.sidebar.set_file_info(file_name, index, len(self.image_files))
        self.sidebar.set_navigation_state(index > 0, index < len(self.image_files) - 1)
        self._pending_points = record.points
        self._pending_bboxes = record.bboxes
        self._pending_bone_lines = record.bone_lines
        self.autosave_label.setText("Saved ✓")
        self.autosave_label.setStyleSheet("color: #61D0B5;")
        self.setWindowTitle(f"Bitewing Landmark Annotator — {file_name}")
        self.sidebar.set_adjustments(self._current_brightness, self._current_contrast, self._current_gamma)
        self.sidebar.set_enhancement_state(self._auto_enhance, self._edge_enhance)

    def _on_points_updated(self, points: List[dict]) -> None:
        if self.current_index == -1:
            return
        self._pending_points = points
        self._trigger_autosave()

    def _on_bboxes_updated(self, bboxes: List[dict]) -> None:
        if self.current_index == -1:
            return
        self._pending_bboxes = bboxes
        self._trigger_autosave()
        
    def _on_bone_lines_updated(self, bone_lines: List[List[dict]]) -> None:
        if self.current_index == -1:
            return
        self._pending_bone_lines = bone_lines
        self._trigger_autosave()

    def _trigger_autosave(self) -> None:
        self.autosave_label.setText("Saving…")
        self.autosave_label.setStyleSheet("color: #F2C76E;")
        self._autosave_timer.start()

    def _perform_autosave(self) -> None:
        if self.current_index == -1 or self._pending_points is None:
            return
        file_name = self.image_files[self.current_index]
        record = AnnotationRecord(
            file_name=file_name,
            width=self.current_dimensions[0],
            height=self.current_dimensions[1],
            points=self._pending_points,
            bboxes=self._pending_bboxes if self._pending_bboxes is not None else [],
            bone_lines=self._pending_bone_lines if self._pending_bone_lines is not None else [],
        )
        self.annotation_manager.save(record)
        self.autosave_label.setText("Saved ✓")
        self.autosave_label.setStyleSheet("color: #61D0B5;")

    def save_current_image(self) -> None:
        self._autosave_timer.stop()
        self._perform_autosave()

    def export_annotations(self) -> None:
        if self.annotation_manager.annotation_dir is None:
            QMessageBox.information(self, "No Folder", "Open an image folder before exporting.")
            return
        export_folder = QFileDialog.getExistingDirectory(self, "Select Export Folder")
        if not export_folder:
            return
        try:
            summary = self.annotation_manager.export_datasets(Path(export_folder))
        except RuntimeError as exc:
            QMessageBox.warning(self, "Export Failed", str(exc))
            return
        QMessageBox.information(
            self,
            "Export Complete",
            summary,
        )

    def show_previous_image(self) -> None:
        if self.current_index > 0:
            self._load_image_at_index(self.current_index - 1)

    def show_next_image(self) -> None:
        if self.current_index + 1 < len(self.image_files):
            self._load_image_at_index(self.current_index + 1)

    def flag_current_image(self) -> None:
        if self.current_index == -1 or self.annotation_manager.image_dir is None:
            QMessageBox.information(self, "No Image", "Load an image before flagging.")
            return
        file_name = self.image_files[self.current_index]
        src_image = self.annotation_manager.image_dir / file_name
        if not src_image.exists():
            QMessageBox.warning(self, "Missing File", f"Image {file_name} could not be found.")
            return
        flagged_dir = self.annotation_manager.image_dir / "flagged"
        flagged_dir.mkdir(parents=True, exist_ok=True)
        dest_image = flagged_dir / file_name
        try:
            shutil.move(str(src_image), str(dest_image))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Flag Failed", f"Unable to move image:\n{exc}")
            return
        ann_path = self.annotation_manager.annotation_path(file_name)
        if ann_path.exists():
            dest_ann_dir = flagged_dir / "annotations"
            dest_ann_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(ann_path), str(dest_ann_dir / ann_path.name))
        self.annotation_manager._cache.pop(file_name, None)  # type: ignore[attr-defined]
        self.image_files.pop(self.current_index)
        if not self.image_files:
            self.current_index = -1
            self.canvas.clear()
            self.sidebar.set_file_info("", 0, 0)
            self.sidebar.set_navigation_state(False, False)
            QMessageBox.information(self, "Flagged", f"{file_name} moved to {flagged_dir}")
            return
        new_index = min(self.current_index, len(self.image_files) - 1)
        self._load_image_at_index(new_index)
        QMessageBox.information(self, "Flagged", f"{file_name} moved to {flagged_dir}")

    def _navigate_if_allowed(self, callback, allow_with_selection: bool = False) -> None:
        focus_widget = self.focusWidget()
        if isinstance(focus_widget, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)):
            return
        if self.canvas.has_selected_point() and not allow_with_selection:
            return
        callback()

    def jump_to_image(self, index: int) -> None:
        if index == self.current_index:
            return
        if 0 <= index < len(self.image_files):
            self._load_image_at_index(index)

    def _update_zoom_label(self, percent: int) -> None:
        self.zoom_label.setText(f"Zoom: {percent}%")

    def _on_adjustments_changed(self, brightness: int, contrast: int, gamma: float) -> None:
        self._current_brightness = brightness
        self._current_contrast = contrast
        self._current_gamma = gamma
        self.canvas.set_adjustments(brightness, contrast, gamma)

    def _on_enhancement_toggled(self, auto_enhance: bool, edge_enhance: bool) -> None:
        self._auto_enhance = auto_enhance
        self._edge_enhance = edge_enhance
        self.canvas.set_enhancements(auto_enhance, edge_enhance)
