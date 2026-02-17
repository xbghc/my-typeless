from typing import Callable, Union

from PyQt6.QtWidgets import QApplication, QPushButton
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor

class CopyButton(QPushButton):
    """
    A button that copies text to the clipboard and provides visual feedback.

    Args:
        text_getter: A string or a callable that returns the text to be copied.
        parent: The parent widget.
    """
    def __init__(self, text_getter: Union[str, Callable[[], str]], parent=None):
        super().__init__(parent)
        self._text_getter = text_getter

        self.setFixedSize(24, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Copy")

        # Default styling matching existing buttons
        self.setStyleSheet("""
            QPushButton {
                border: none; background: transparent;
                color: #9ca3af; font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { color: #6b7280; }
        """)

        self._copy_icon = self._create_copy_icon()
        self._check_icon = self._create_check_icon()

        self.setIcon(self._copy_icon)
        self.setIconSize(QSize(16, 16))

        self.clicked.connect(self._on_click)

        self._feedback_timer = QTimer(self)
        self._feedback_timer.setSingleShot(True)
        self._feedback_timer.setInterval(2000)
        self._feedback_timer.timeout.connect(self._reset_icon)

    def _create_copy_icon(self) -> QIcon:
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = painter.pen()
        pen.setColor(QColor("#9ca3af"))
        pen.setWidthF(1.4)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Draw two overlapping rectangles
        painter.drawRoundedRect(5, 1, 10, 10, 2, 2)
        painter.drawRoundedRect(1, 5, 10, 10, 2, 2)
        painter.end()
        return QIcon(pixmap)

    def _create_check_icon(self) -> QIcon:
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = painter.pen()
        pen.setColor(QColor("#22c55e"))  # Green for success
        pen.setWidthF(1.6)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Draw checkmark
        path = [(3, 8), (7, 12), (13, 4)]
        for i in range(len(path) - 1):
            painter.drawLine(*path[i], *path[i+1])

        painter.end()
        return QIcon(pixmap)

    def _on_click(self):
        text = self._text_getter() if callable(self._text_getter) else self._text_getter
        if text:
            QApplication.clipboard().setText(text)
            self.setIcon(self._check_icon)
            self.setToolTip("Copied!")
            self._feedback_timer.start()

    def _reset_icon(self):
        self.setIcon(self._copy_icon)
        self.setToolTip("Copy")
