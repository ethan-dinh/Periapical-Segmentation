"""
Main entry point for the segmentation tool application.
"""

from __future__ import annotations

import os
import sys

from PyQt5.QtWidgets import QApplication

if __package__ is None:
    PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
    PARENT_DIR = os.path.dirname(PACKAGE_DIR)
    if PARENT_DIR not in sys.path:
        sys.path.insert(0, PARENT_DIR)
    from DentAnX.features.window.main_window import AnnotationMainWindow
else:
    from .features.window.main_window import AnnotationMainWindow

def main() -> None:
    """
    This function is the main entry point for the application.
    """
    app = QApplication([])
    app.setApplicationName("Bitewing Landmark Annotator")
    window = AnnotationMainWindow()
    window.show()
    app.exec_()

if __name__ == "__main__":
    """
    This is the main entry point for the application.
    """
    main()
