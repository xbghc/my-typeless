from typing import Callable, Optional

from PyQt6.QtWidgets import QPushButton, QApplication, QWidget
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor


class CopyButton(QPushButton):
    """
    A reusable Copy button component that handles clipboard operations and provides visual feedback.

    Args:
        text_getter (Callable[[], str] | str): The text to copy or a function returning it.
        label (Optional[str]): If provided, the button displays this text (e.g., "📋 Copy").
                               If None (default), it displays a drawn copy icon.
        parent (Optional[QWidget]): The parent widget.
    """
    def __init__(
        self,
        text_getter: Callable[[], str] | str,
        label: Optional[str] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._text_getter = text_getter
        self._original_label = label

        # Feedback timer
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._reset_state)

        # Basic setup
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._handle_click)

        # Initial state
        self._reset_state()

    def _get_text(self) -> str:
        if callable(self._text_getter):
            return self._text_getter()
        return str(self._text_getter)

    def _handle_click(self) -> None:
        text = self._get_text()
        if text:
            QApplication.clipboard().setText(text)
            self._show_feedback()

    def _show_feedback(self) -> None:
        """Shows success feedback (checkmark icon or 'Copied!' text)."""
        if self._original_label:
            # Text mode: Change text to "✅ Copied!"
            self.setText("✅ Copied!")
        else:
            # Icon mode: Change icon to checkmark
            self._set_check_icon()

        self.setToolTip("Copied!")
        self._timer.start(2000)

    def _reset_state(self) -> None:
        """Resets the button to its initial state."""
        if self._original_label:
            self.setText(self._original_label)
        else:
            self._set_copy_icon()

        self.setToolTip("Copy to clipboard")

    def _set_copy_icon(self) -> None:
        """Draws the default copy icon (two overlapping squares)."""
        size = 16
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = painter.pen()
        pen.setColor(QColor("#9ca3af"))  # Gray
        pen.setWidthF(1.4)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Back square
        painter.drawRoundedRect(5, 1, 10, 10, 2, 2)
        # Front square
        painter.drawRoundedRect(1, 5, 10, 10, 2, 2)

        painter.end()
        self.setIcon(QIcon(pixmap))
        self.setIconSize(QSize(size, size))

    def _set_check_icon(self) -> None:
        """Draws a success checkmark icon."""
        size = 16
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = painter.pen()
        pen.setColor(QColor("#10b981"))  # Green
        pen.setWidthF(1.8)
        painter.setPen(pen)

        # Checkmark path
        path = [(3, 8), (7, 12), (13, 4)]
        for i in range(len(path) - 1):
            painter.drawLine(*path[i], *path[i+1])

        painter.end()
        self.setIcon(QIcon(pixmap))
        self.setIconSize(QSize(size, size))
