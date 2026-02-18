"""Clipboard copy button with visual feedback."""

from typing import Callable, Union
from PyQt6.QtWidgets import QApplication, QPushButton
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPainterPath


class CopyButton(QPushButton):
    """A button that copies text to clipboard and shows a checkmark briefly."""

    def __init__(
        self,
        text_getter: Union[str, Callable[[], str]],
        parent=None
    ):
        super().__init__(parent)
        self._text_getter = text_getter

        # Configure basic appearance
        self.setFixedSize(24, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Copy")

        # Default style
        self.setStyleSheet("""
            QPushButton {
                border: none; background: transparent;
                color: #9ca3af; font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { color: #6b7280; }
        """)

        # Generate icons
        self._icon_copy = self._make_copy_icon()
        self._icon_check = self._make_check_icon()

        self.setIcon(self._icon_copy)
        self.setIconSize(QSize(16, 16))

        self.clicked.connect(self._on_click)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._reset_icon)

    def _make_copy_icon(self) -> QIcon:
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
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
        return QIcon(pix)

    def _make_check_icon(self) -> QIcon:
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = painter.pen()
        pen.setColor(QColor("#22c55e"))  # Green color
        pen.setWidthF(1.8)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Draw checkmark
        path = QPainterPath()
        path.moveTo(3, 8)
        path.lineTo(7, 12)
        path.lineTo(13, 4)
        painter.drawPath(path)
        painter.end()
        return QIcon(pix)

    def _on_click(self):
        if callable(self._text_getter):
            text = self._text_getter()
        else:
            text = self._text_getter

        if text:
            QApplication.clipboard().setText(text)
            self.setIcon(self._icon_check)
            self._timer.start(2000)

    def _reset_icon(self):
        self.setIcon(self._icon_copy)
