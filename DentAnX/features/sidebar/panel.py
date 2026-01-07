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
        self.setMinimumWidth(240) # Slightly wider for cleaner look
        
        # Main Layout
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(16, 16, 16, 16)
        self.main_layout.setSpacing(20)
        self.setLayout(self.main_layout)
        
        self._slider_labels: dict[str, QLabel] = {}

        # --- Section: File & Nav ---
        self._init_file_nav_section()
        
        # --- Section: Annotation Tools ---
        self._init_annotation_section()

        # --- Section: Image Adjustments ---
        self._init_image_section()
        
        # --- Section: Stats/Info ---
        self._init_stats_section()

        self.main_layout.addStretch(1)

    def _init_file_nav_section(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        # Open Button
        self.open_button = QPushButton("Open Folder")
        self.open_button.setObjectName("PrimaryButton")
        self.open_button.setCursor(Qt.PointingHandCursor)
        self.open_button.clicked.connect(self.openFolderRequested.emit)
        layout.addWidget(self.open_button)

        # File Info Label
        self.filename_label = QLabel("No file loaded")
        self.filename_label.setObjectName("FilenameLabel")
        self.filename_label.setAlignment(Qt.AlignCenter)
        self.filename_label.setWordWrap(True)
        layout.addWidget(self.filename_label)

        # Navigation Controls
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(8)
        
        self.prev_button = QPushButton("◀")
        self.prev_button.setToolTip("Previous Image (A)")
        self.prev_button.setFixedWidth(40)
        self.prev_button.clicked.connect(self.prevRequested.emit)
        
        self.index_label = QLabel("0 / 0")
        self.index_label.setAlignment(Qt.AlignCenter)
        self.index_label.setStyleSheet("color: #8E8E93; font-weight: 500;")
        
        self.next_button = QPushButton("▶")
        self.next_button.setToolTip("Next Image (D)")
        self.next_button.setFixedWidth(40)
        self.next_button.clicked.connect(self.nextRequested.emit)
        
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.index_label, 1) # Expand label to center
        nav_layout.addWidget(self.next_button)
        layout.addLayout(nav_layout)
        
        # Jump Controls
        jump_layout = QHBoxLayout()
        jump_layout.setContentsMargins(0, 4, 0, 0)
        jump_label = QLabel("Jump to:")
        jump_label.setStyleSheet("color: #8E8E93;")
        
        self.jump_spin = QSpinBox()
        self.jump_spin.setButtonSymbols(QSpinBox.NoButtons)
        self.jump_spin.setAlignment(Qt.AlignCenter)
        self.jump_spin.setFixedWidth(60)
        self.jump_spin.setMinimum(1)
        self.jump_spin.setMaximum(1)
        
        self.jump_button = QPushButton("Go")
        self.jump_button.setFixedWidth(40)
        self.jump_button.clicked.connect(self._emit_jump)
        
        jump_layout.addWidget(jump_label)
        jump_layout.addWidget(self.jump_spin)
        jump_layout.addWidget(self.jump_button)
        jump_layout.addStretch(1)
        layout.addLayout(jump_layout)
        
        self.main_layout.addLayout(layout)
        self.main_layout.addWidget(self._create_separator())

    def _init_annotation_section(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        layout.addWidget(self._create_section_header("Annotation Mode"))
        
        self.mode_group = QButtonGroup(self)
        self.landmark_mode_radio = QRadioButton("Landmarks")
        self.bone_mode_radio = QRadioButton("Bone Lines")
        self.bbox_mode_radio = QRadioButton("Bounding Boxes")
        self.landmark_mode_radio.setChecked(True)
        
        for radio in (self.landmark_mode_radio, self.bone_mode_radio, self.bbox_mode_radio):
            self.mode_group.addButton(radio)
            layout.addWidget(radio)
            
        self.landmark_mode_radio.toggled.connect(self._on_mode_changed)
        self.bone_mode_radio.toggled.connect(self._on_mode_changed)
        self.bbox_mode_radio.toggled.connect(self._on_mode_changed)
        
        # BBox Options Sub-panel
        self.bbox_options_widget = QWidget()
        bbox_layout = QVBoxLayout(self.bbox_options_widget)
        bbox_layout.setContentsMargins(12, 4, 0, 0) # Indent
        bbox_layout.setSpacing(8)
        
        # Filter
        filter_row = QHBoxLayout()
        filter_label = QLabel("Show:")
        self.bbox_filter_combo = QComboBox()
        self.bbox_filter_combo.addItem("All")
        self.bbox_filter_combo.addItems(BBOX_CLASSES)
        self.bbox_filter_combo.currentTextChanged.connect(self.bboxFilterChanged.emit)
        filter_row.addWidget(filter_label)
        filter_row.addWidget(self.bbox_filter_combo)
        bbox_layout.addLayout(filter_row)
        
        # Draw Mode
        draw_label = QLabel("Method:")
        bbox_layout.addWidget(draw_label)
        
        self.bbox_draw_mode_group = QButtonGroup()
        draw_mode_row = QHBoxLayout()
        self.bbox_drag_radio = QRadioButton("Drag")
        self.bbox_three_point_radio = QRadioButton("3-Point")
        self.bbox_drag_radio.setChecked(True)
        self.bbox_draw_mode_group.addButton(self.bbox_drag_radio)
        self.bbox_draw_mode_group.addButton(self.bbox_three_point_radio)
        
        self.bbox_drag_radio.toggled.connect(self._on_bbox_draw_mode_changed)
        self.bbox_three_point_radio.toggled.connect(self._on_bbox_draw_mode_changed)
        
        draw_mode_row.addWidget(self.bbox_drag_radio)
        draw_mode_row.addWidget(self.bbox_three_point_radio)
        draw_mode_row.addStretch(1)
        bbox_layout.addLayout(draw_mode_row)
        
        # Initially disabled
        self.bbox_filter_combo.setEnabled(False)
        self.bbox_drag_radio.setEnabled(False)
        self.bbox_three_point_radio.setEnabled(False)
        
        layout.addWidget(self.bbox_options_widget)
        
        self.main_layout.addLayout(layout)
        self.main_layout.addWidget(self._create_separator())

    def _init_image_section(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        layout.addWidget(self._create_section_header("Adjustments"))
        
        self.brightness_slider = self._make_slider("Brightness", -100, 100, 0, layout)
        self.contrast_slider = self._make_slider("Contrast", -100, 100, 0, layout)
        self.gamma_slider = self._make_slider("Gamma", 10, 300, 100, layout, scale=0.01)

        enhancements_box = QHBoxLayout()
        self.auto_enhance_check = QCheckBox("Auto")
        self.auto_enhance_check.setToolTip("Auto-enhance histogram")
        self.edge_enhance_check = QCheckBox("Edge")
        self.edge_enhance_check.setToolTip("Edge enhancement filter")
        
        self.auto_enhance_check.stateChanged.connect(self._emit_enhancements)
        self.edge_enhance_check.stateChanged.connect(self._emit_enhancements)
        
        enhancements_box.addWidget(self.auto_enhance_check)
        enhancements_box.addWidget(self.edge_enhance_check)
        enhancements_box.addStretch(1)
        layout.addLayout(enhancements_box)
        
        self.main_layout.addLayout(layout)
        self.main_layout.addWidget(self._create_separator())

    def _init_stats_section(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(10)
        
        # Actions
        self.export_button = QPushButton("Export Data")
        self.export_button.clicked.connect(self.exportRequested.emit)
        layout.addWidget(self.export_button)
        
        self.flag_button = QPushButton("Flag Image")
        self.flag_button.setStyleSheet("color: #FF453A;") # System Red for destructive/flag action
        self.flag_button.clicked.connect(self.flagRequested.emit)
        layout.addWidget(self.flag_button)
        
        # Stats Grid
        stats_frame = QFrame()
        stats_frame.setObjectName("StatsFrame") # Can style this if needed
        stats_layout = QVBoxLayout(stats_frame)
        stats_layout.setContentsMargins(0, 8, 0, 0)
        stats_layout.setSpacing(4)
        
        self.cej_label = QLabel("CEJ Points: 0")
        self.crest_label = QLabel("Crest Points: 0")
        self.bbox_label = QLabel("Objects: 0")
        
        for lbl in (self.cej_label, self.crest_label, self.bbox_label):
            lbl.setStyleSheet("color: #8E8E93; font-size: 12px;")
            stats_layout.addWidget(lbl)
            
        layout.addWidget(stats_frame)
        self.main_layout.addLayout(layout)

    def _create_separator(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #38383A; max-height: 1px; border: none;")
        return line

    def _create_section_header(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionLabel")
        return label

    def _make_slider(
        self, name: str, minimum: int, maximum: int, value: int, parent_layout: QVBoxLayout, scale: float = 1.0
    ) -> QSlider:
        # Compact slider row: Label | Slider | Value
        container = QHBoxLayout()
        container.setSpacing(8)
        
        label = QLabel(name)
        label.setFixedWidth(70)
        label.setStyleSheet("color: #D0D0D0;")
        
        slider = QSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)
        
        val_label = QLabel(f"{value * scale:.2f}" if name == "Gamma" else str(value))
        val_label.setFixedWidth(40)
        val_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        val_label.setStyleSheet("color: #8E8E93; font-variant-numeric: tabular-nums;")
        
        self._slider_labels[name] = val_label
        
        slider.valueChanged.connect(lambda val, lbl=val_label, nm=name, sc=scale: self._on_adjustment_change(lbl, nm, val, sc))
        
        container.addWidget(label)
        container.addWidget(slider)
        container.addWidget(val_label)
        
        parent_layout.addLayout(container)
        return slider

    def _on_adjustment_change(self, label_widget: QLabel, name: str, value: int, scale: float = 1.0) -> None:
        if name == "Gamma":
            label_widget.setText(f"{value * scale:.2f}")
        else:
            label_widget.setText(f"{value}")
        self.adjustmentsChanged.emit(
            self.brightness_slider.value(),
            self.contrast_slider.value(),
            self.gamma_slider.value() * 0.01,
        )
        
    def _on_mode_changed(self) -> None:
        if self.landmark_mode_radio.isChecked():
            self.modeChanged.emit(CanvasMode.LANDMARK)
            self._set_bbox_controls_enabled(False)
        elif self.bone_mode_radio.isChecked():
            self.modeChanged.emit(CanvasMode.BONE)
            self._set_bbox_controls_enabled(False)
        else:
            self.modeChanged.emit(CanvasMode.BBOX)
            self._set_bbox_controls_enabled(True)
            
    def _set_bbox_controls_enabled(self, enabled: bool) -> None:
        self.bbox_filter_combo.setEnabled(enabled)
        self.bbox_drag_radio.setEnabled(enabled)
        self.bbox_three_point_radio.setEnabled(enabled)
        # Optional: dim the section visually?

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
            self.index_label.setText("0 / 0")
        else:
            self.index_label.setText(f"{index + 1} / {total}")
        self.jump_spin.setMaximum(max(1, total))
        if total == 0:
            self.jump_spin.setValue(1)
        else:
            self.jump_spin.setValue(index + 1)

    def set_counts(self, cej: int, crest: int, bboxes: int) -> None:
        self.cej_label.setText(f"CEJ Points: {cej}")
        self.crest_label.setText(f"Crest Points: {crest}")
        self.bbox_label.setText(f"Objects: {bboxes}")

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
        self._slider_labels["Brightness"].setText(f"{brightness}")
        self._slider_labels["Contrast"].setText(f"{contrast}")
        self._slider_labels["Gamma"].setText(f"{gamma:.2f}")

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
        # General controls
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
            self.landmark_mode_radio,
            self.bone_mode_radio,
            self.bbox_mode_radio,
        ):
            widget.setEnabled(enabled)
            
        # Mode-specific controls state
        if enabled and self.bbox_mode_radio.isChecked():
            self._set_bbox_controls_enabled(True)
        else:
            self._set_bbox_controls_enabled(False)

    def set_navigation_state(self, has_prev: bool, has_next: bool) -> None:
        self.prev_button.setEnabled(has_prev)
        self.next_button.setEnabled(has_next)
