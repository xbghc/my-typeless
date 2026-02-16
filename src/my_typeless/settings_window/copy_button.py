"""Copy button component with visual feedback"""

from typing import Callable, Optional, Union
from PyQt6.QtWidgets import QPushButton, QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor


class CopyButton(QPushButton):
    """
    A button that copies text to clipboard and shows temporary visual feedback.
    Can be icon-only or text-based.
    """
    def __init__(self, text_getter: Union[str, Callable[[], str]], success_text: str = "Copied!", parent=None):
        super().__init__(parent)
        self._text_getter = text_getter
        self._success_text = success_text

        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._reset)

        self.clicked.connect(self._copy)

        # Default style
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Store original state
        self._original_icon: Optional[QIcon] = None
        self._original_text: str = ""
        self._original_tooltip: str = ""
        self._state_captured = False

        # Default tooltip
        self.setToolTip("Copy")

    def showEvent(self, event):
        super().showEvent(event)
        if not self._state_captured:
            self._capture_state()

    def _capture_state(self):
        self._original_icon = self.icon()
        self._original_text = self.text()
        self._original_tooltip = self.toolTip()
        self._state_captured = True

    def _copy(self):
        if not self._state_captured:
            self._capture_state()

        if callable(self._text_getter):
            text = self._text_getter()
        else:
            text = self._text_getter

        if not text:
            return

        QApplication.clipboard().setText(text)

        # Visual feedback
        self.setIcon(self._make_check_icon())

        # If button has text, change it too
        if self.text():
            self.setText(self._success_text)

        self.setToolTip(self._success_text)
        self.setEnabled(False) # Prevent double clicks during feedback
        self._timer.start()

    def _reset(self):
        if self._original_icon:
            self.setIcon(self._original_icon)
        self.setText(self._original_text)
        self.setToolTip(self._original_tooltip)
        self.setEnabled(True)

    def _make_check_icon(self) -> QIcon:
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = painter.pen()
        pen.setColor(QColor("#22c55e")) # Green
        pen.setWidthF(2)
        painter.setPen(pen)

        # Draw checkmark
        painter.drawLine(3, 8, 7, 12)
        painter.drawLine(7, 12, 13, 4)

        painter.end()
        return QIcon(pixmap)

    @staticmethod
    def make_copy_icon(color: str = "#9ca3af") -> QIcon:
        """Helper to create the standard copy icon used in history page"""
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = painter.pen()
        pen.setColor(QColor(color))
        pen.setWidthF(1.4)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawRoundedRect(5, 1, 10, 10, 2, 2)
        painter.drawRoundedRect(1, 5, 10, 10, 2, 2)

        painter.end()
        return QIcon(pixmap)
