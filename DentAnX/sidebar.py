from __future__ import annotations

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class SidePanel(QWidget):
    openFolderRequested = pyqtSignal()
    prevRequested = pyqtSignal()
    nextRequested = pyqtSignal()
    exportRequested = pyqtSignal()
    jumpRequested = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("SidePanel")
        self.setMinimumWidth(220)
        layout = QVBoxLayout()
        layout.setSpacing(16)

        self.open_button = QPushButton("Open Folder")
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

        layout.addStretch(1)
        self.setLayout(layout)

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

    def set_counts(self, cej: int, crest: int) -> None:
        self.cej_label.setText(f"CEJ points: {cej}")
        self.crest_label.setText(f"Crest points: {crest}")

    def set_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.prev_button,
            self.next_button,
            self.jump_button,
            self.jump_spin,
            self.export_button,
        ):
            widget.setEnabled(enabled)

    def set_navigation_state(self, has_prev: bool, has_next: bool) -> None:
        self.prev_button.setEnabled(has_prev)
        self.next_button.setEnabled(has_next)
