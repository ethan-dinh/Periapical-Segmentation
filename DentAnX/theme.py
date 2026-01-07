from __future__ import annotations


def app_stylesheet() -> str:
    return """
    QWidget {
        background-color: #1E1E1E;
        color: #D0D0D0;
        font-family: "Segoe UI", "Roboto", "Helvetica Neue", sans-serif;
        font-size: 13px;
    }

    QMainWindow {
        background-color: #1E1E1E;
    }

    #SidePanel {
        background-color: #2C2C2C;
        border: 1px solid #3A3A3A;
        border-radius: 8px;
        padding: 16px;
    }

    QPushButton {
        background-color: #2C2C2C;
        border: 1px solid #3A3A3A;
        border-radius: 5px;
        padding: 6px 12px;
        color: #D0D0D0;
    }

    QPushButton:hover {
        background-color: #333333;
    }

    QPushButton:pressed {
        background-color: #3A3A3A;
    }

    QPushButton:disabled {
        color: #6A6A6A;
        border-color: #2A2A2A;
        background-color: #232323;
    }

    QPushButton#PrimaryButton {
        background-color: #4DA3FF;
        color: #1E1E1E;
        border: none;
    }

    QPushButton#PrimaryButton:hover {
        background-color: #72B7FF;
    }

    QPushButton#PrimaryButton:disabled {
        background-color: #3A6C9E;
        color: #1E1E1E;
    }

    QLabel#FilenameLabel {
        font-size: 14px;
        font-weight: 500;
    }

    QStatusBar {
        background-color: #2C2C2C;
        border-top: 1px solid #3A3A3A;
    }

    QSpinBox, QLineEdit {
        background-color: #1F1F1F;
        border: 1px solid #3A3A3A;
        border-radius: 5px;
        padding: 4px 6px;
        selection-background-color: #4DA3FF;
    }

    QMenu {
        background-color: #2C2C2C;
        color: #D0D0D0;
        border: 1px solid #3A3A3A;
    }

    QMenu::item:selected {
        background-color: #4DA3FF;
        color: #1E1E1E;
    }

    QToolTip {
        background-color: #2C2C2C;
        color: #D0D0D0;
        border: 1px solid #4DA3FF;
        border-radius: 4px;
    }
    """
