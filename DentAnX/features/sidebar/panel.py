from __future__ import annotations

from enum import Enum, auto
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..canvas.image_canvas import CanvasMode, BBoxDrawMode
from ...utils.landmarks import BBOX_CLASSES


class SidePanel(QWidget):
    """Left sidebar containing navigation controls and stats."""

    openFolderRequested = pyqtSignal()
    prevRequested = pyqtSignal()
    nextRequested = pyqtSignal()
    exportRequested = pyqtSignal()
    jumpRequested = pyqtSignal(int)
    adjustmentsChanged = pyqtSignal(int, int, float)
    enhancementToggled = pyqtSignal(bool, bool)
    flagRequested = pyqtSignal()
    flagRequested = pyqtSignal()
    modeChanged = pyqtSignal(CanvasMode)
    bboxFilterChanged = pyqtSignal(str)
    bboxDrawModeChanged = pyqtSignal(BBoxDrawMode)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("SidePanel")
        self.setMinimumWidth(220)
        layout = QVBoxLayout()
        layout.setSpacing(16)
        self._slider_labels: dict[str, QLabel] = {}

        self.open_button = QPushButton("Open Folder…")
        self.open_button.setObjectName("PrimaryButton")
        self.open_button.clicked.connect(self.openFolderRequested.emit)
        layout.addWidget(self.open_button)

        nav_container = QHBoxLayout()
        self.prev_button = QPushButton("◀ Prev")
        self.prev_button.clicked.connect(self.prevRequested.emit)
        nav_container.addWidget(self.prev_button)
        self.next_button = QPushButton("Next ▶")
        self.next_button.clicked.connect(self.nextRequested.emit)
        nav_container.addWidget(self.next_button)
        layout.addLayout(nav_container)

        jump_row = QHBoxLayout()
        self.jump_spin = QSpinBox()
        self.jump_spin.setMinimum(1)
        self.jump_spin.setMaximum(1)
        self.jump_spin.setButtonSymbols(QSpinBox.NoButtons)
        self.jump_spin.setAlignment(Qt.AlignCenter)
        self.jump_spin.setFixedWidth(70)
        self.jump_button = QPushButton("Go")
        self.jump_button.clicked.connect(self._emit_jump)
        jump_row.addWidget(self.jump_spin)
        jump_row.addWidget(self.jump_button)
        layout.addLayout(jump_row)

        self.export_button = QPushButton("Export All Annotations")
        self.export_button.setObjectName("PrimaryButton")
        self.export_button.clicked.connect(self.exportRequested.emit)
        layout.addWidget(self.export_button)

        self.flag_button = QPushButton("Flag Image")
        self.flag_button.clicked.connect(self.flagRequested.emit)
        layout.addWidget(self.flag_button)
        
        # Mode Selection
        mode_label = QLabel("Annotation Mode")
        mode_label.setObjectName("SectionLabel")
        layout.addWidget(mode_label)
        
        self.mode_group = QButtonGroup(self)
        self.landmark_mode_radio = QRadioButton("Landmarks")
        self.bone_mode_radio = QRadioButton("Bone Lines")
        self.bbox_mode_radio = QRadioButton("Bounding Boxes")
        self.landmark_mode_radio.setChecked(True)
        self.mode_group.addButton(self.landmark_mode_radio)
        self.mode_group.addButton(self.bone_mode_radio)
        self.mode_group.addButton(self.bbox_mode_radio)
        
        self.landmark_mode_radio.toggled.connect(self._on_mode_changed)
        self.bone_mode_radio.toggled.connect(self._on_mode_changed)
        self.bbox_mode_radio.toggled.connect(self._on_mode_changed)
        
        layout.addWidget(self.landmark_mode_radio)
        layout.addWidget(self.bone_mode_radio)
        layout.addWidget(self.bbox_mode_radio)
        
        # BBox Filter (not class selector)
        bbox_filter_label = QLabel("BBox Filter:")
        layout.addWidget(bbox_filter_label)
        self.bbox_filter_combo = QComboBox()
        self.bbox_filter_combo.addItem("All")
        self.bbox_filter_combo.addItems(BBOX_CLASSES)
        self.bbox_filter_combo.currentTextChanged.connect(self.bboxFilterChanged.emit)
        self.bbox_filter_combo.setEnabled(False)
        layout.addWidget(self.bbox_filter_combo)
        
        # BBox Drawing Mode (Drag vs Three-Point)
        bbox_draw_mode_label = QLabel("Draw Mode:") 
        layout.addWidget(bbox_draw_mode_label)
        
        self.bbox_draw_mode_group = QButtonGroup()
        self.bbox_drag_radio = QRadioButton("Drag")
        self.bbox_three_point_radio = QRadioButton("Three-Point")
        self.bbox_drag_radio.setChecked(True)
        self.bbox_draw_mode_group.addButton(self.bbox_drag_radio)
        self.bbox_draw_mode_group.addButton(self.bbox_three_point_radio)
        
        self.bbox_drag_radio.toggled.connect(self._on_bbox_draw_mode_changed)
        self.bbox_three_point_radio.toggled.connect(self._on_bbox_draw_mode_changed)
        
        self.bbox_drag_radio.setEnabled(False)
        self.bbox_three_point_radio.setEnabled(False)
        
        layout.addWidget(self.bbox_drag_radio)
        layout.addWidget(self.bbox_three_point_radio)

        correction_label = QLabel("Image Corrections")
        correction_label.setObjectName("SectionLabel")
        layout.addWidget(correction_label)

        self.brightness_slider = self._make_slider("Brightness", -100, 100, 0, layout)
        self.contrast_slider = self._make_slider("Contrast", -100, 100, 0, layout)
        self.gamma_slider = self._make_slider("Gamma", 10, 300, 100, layout, scale=0.01)

        enhancements_box = QHBoxLayout()
        self.auto_enhance_check = QCheckBox("Auto Enhance")
        self.edge_enhance_check = QCheckBox("Edge Enhance")
        self.auto_enhance_check.stateChanged.connect(self._emit_enhancements)
        self.edge_enhance_check.stateChanged.connect(self._emit_enhancements)
        enhancements_box.addWidget(self.auto_enhance_check)
        enhancements_box.addWidget(self.edge_enhance_check)
        enhancements_widget = QWidget()
        enhancements_widget.setLayout(enhancements_box)
        layout.addWidget(enhancements_widget)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        layout.addWidget(divider)

        self.filename_label = QLabel("No file loaded")
        self.filename_label.setObjectName("FilenameLabel")
        layout.addWidget(self.filename_label)

        self.index_label = QLabel("Image 0 / 0")
        layout.addWidget(self.index_label)

        self.cej_label = QLabel("CEJ points: 0")
        layout.addWidget(self.cej_label)

        self.crest_label = QLabel("Crest points: 0")
        layout.addWidget(self.crest_label)
        
        self.bbox_label = QLabel("BBoxes: 0")
        layout.addWidget(self.bbox_label)

        layout.addStretch(1)
        self.setLayout(layout)

    def _make_slider(
        self, name: str, minimum: int, maximum: int, value: int, parent_layout: QVBoxLayout, scale: float = 1.0
    ) -> QSlider:
        label_value = value * scale if name == "Gamma" else value
        label = QLabel(f"{name}: {label_value}")
        self._slider_labels[name] = label
        slider = QSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        slider.valueChanged.connect(lambda val, lbl=label, nm=name, sc=scale: self._on_adjustment_change(lbl, nm, val, sc))
        container = QVBoxLayout()
        container.setSpacing(4)
        container.addWidget(label)
        container.addWidget(slider)
        wrapper = QWidget()
        wrapper.setLayout(container)
        parent_layout.addWidget(wrapper)
        return slider

    def _on_adjustment_change(self, label_widget: QLabel, name: str, value: int, scale: float = 1.0) -> None:
        if name == "Gamma":
            label_widget.setText(f"{name}: {value * scale:.2f}")
        else:
            label_widget.setText(f"{name}: {value}")
        self.adjustmentsChanged.emit(
            self.brightness_slider.value(),
            self.contrast_slider.value(),
            self.gamma_slider.value() * 0.01,
        )
        
    def _on_mode_changed(self) -> None:
        if self.landmark_mode_radio.isChecked():
            self.modeChanged.emit(CanvasMode.LANDMARK)
            self.bbox_filter_combo.setEnabled(False)
            self.bbox_drag_radio.setEnabled(False)
            self.bbox_three_point_radio.setEnabled(False)
        elif self.bone_mode_radio.isChecked():
            self.modeChanged.emit(CanvasMode.BONE)
            self.bbox_filter_combo.setEnabled(False)
            self.bbox_drag_radio.setEnabled(False)
            self.bbox_three_point_radio.setEnabled(False)
        else:
            self.modeChanged.emit(CanvasMode.BBOX)
            self.bbox_filter_combo.setEnabled(True)
            self.bbox_drag_radio.setEnabled(True)
            self.bbox_three_point_radio.setEnabled(True)

    def _on_bbox_draw_mode_changed(self) -> None:
        if self.bbox_drag_radio.isChecked():
            self.bboxDrawModeChanged.emit(BBoxDrawMode.DRAG)
        else:
            self.bboxDrawModeChanged.emit(BBoxDrawMode.THREE_POINT)

    def _emit_jump(self) -> None:
        total = self.jump_spin.maximum()
        if total <= 0:
            return
        target_index = self.jump_spin.value() - 1
        self.jumpRequested.emit(target_index)

    def set_file_info(self, filename: str, index: int, total: int) -> None:
        self.filename_label.setText(filename or "No file loaded")
        total = max(total, 0)
        if total == 0:
            self.index_label.setText("Image 0 / 0")
        else:
            self.index_label.setText(f"Image {index + 1} / {total}")
        self.jump_spin.setMaximum(max(1, total))
        if total == 0:
            self.jump_spin.setValue(1)
        else:
            self.jump_spin.setValue(index + 1)

    def set_counts(self, cej: int, crest: int, bboxes: int) -> None:
        self.cej_label.setText(f"CEJ points: {cej}")
        self.crest_label.setText(f"Crest points: {crest}")
        self.bbox_label.setText(f"BBoxes: {bboxes}")

    def set_adjustments(self, brightness: int, contrast: int, gamma: float) -> None:
        self.brightness_slider.blockSignals(True)
        self.contrast_slider.blockSignals(True)
        self.gamma_slider.blockSignals(True)
        self.brightness_slider.setValue(brightness)
        self.contrast_slider.setValue(contrast)
        self.gamma_slider.setValue(int(gamma * 100))
        self.brightness_slider.blockSignals(False)
        self.contrast_slider.blockSignals(False)
        self.gamma_slider.blockSignals(False)
        self._slider_labels["Brightness"].setText(f"Brightness: {brightness}")
        self._slider_labels["Contrast"].setText(f"Contrast: {contrast}")
        self._slider_labels["Gamma"].setText(f"Gamma: {gamma:.2f}")

    def set_enhancement_state(self, auto_enhance: bool, edge_enhance: bool) -> None:
        self.auto_enhance_check.blockSignals(True)
        self.edge_enhance_check.blockSignals(True)
        self.auto_enhance_check.setChecked(auto_enhance)
        self.edge_enhance_check.setChecked(edge_enhance)
        self.auto_enhance_check.blockSignals(False)
        self.edge_enhance_check.blockSignals(False)

    def _emit_enhancements(self) -> None:
        self.enhancementToggled.emit(self.auto_enhance_check.isChecked(), self.edge_enhance_check.isChecked())

    def set_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.prev_button,
            self.next_button,
            self.jump_button,
            self.jump_spin,
            self.export_button,
            self.brightness_slider,
            self.contrast_slider,
            self.gamma_slider,
            self.auto_enhance_check,
            self.edge_enhance_check,
            self.flag_button,
            self.flag_button,
            self.landmark_mode_radio,
            self.bone_mode_radio,
            self.bbox_mode_radio,
            self.bbox_filter_combo,
            self.bbox_drag_radio,
            self.bbox_three_point_radio,
        ):
            widget.setEnabled(enabled)

    def set_navigation_state(self, has_prev: bool, has_next: bool) -> None:
        self.prev_button.setEnabled(has_prev)
        self.next_button.setEnabled(has_next)
