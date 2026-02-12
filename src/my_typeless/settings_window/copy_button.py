"""Copy button component with visual feedback"""

from typing import Optional, Callable, Union
from PyQt6.QtWidgets import QPushButton, QApplication
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor


class CopyButton(QPushButton):
    def __init__(
        self,
        text_source: Union[str, Callable[[], str]],
        label: Optional[str] = None,
        style_sheet: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._text_source = text_source
        self._original_label = label
        self._original_style = style_sheet

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if style_sheet:
            self.setStyleSheet(style_sheet)

        if label:
            self.setText(label)
        else:
            self.setFixedSize(24, 24)
            self._set_copy_icon()
            self.setToolTip("Copy")

        self.clicked.connect(self._on_click)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._reset)

    def _set_copy_icon(self):
        # Draw the copy icon (two overlapping squares)
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = painter.pen()
        pen.setColor(QColor("#9ca3af"))
        pen.setWidthF(1.4)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Back square
        painter.drawRoundedRect(5, 1, 10, 10, 2, 2)
        # Front square
        painter.drawRoundedRect(1, 5, 10, 10, 2, 2)

        painter.end()
        self.setIcon(QIcon(pixmap))
        self.setIconSize(QSize(16, 16))

    def _set_check_icon(self):
        # Draw a checkmark icon
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = painter.pen()
        pen.setColor(QColor("#22c55e"))  # Green color
        pen.setWidthF(2.0)
        painter.setPen(pen)

        # Checkmark
        path = [(3, 8), (6, 11), (13, 4)]
        for i in range(len(path) - 1):
            painter.drawLine(path[i][0], path[i][1], path[i+1][0], path[i+1][1])

        painter.end()
        self.setIcon(QIcon(pixmap))
        self.setIconSize(QSize(16, 16))

    def _on_click(self):
        text = self._text_source() if callable(self._text_source) else self._text_source
        if text:
            QApplication.clipboard().setText(text)

            if self._original_label:
                self.setText("✔ Copied")
                # Temporarily change color for visibility?
                # For now just text change is safer to avoid clashing with custom stylesheets.
            else:
                self._set_check_icon()
                self.setToolTip("Copied!")

            self._timer.start(2000)

    def _reset(self):
        if self._original_label:
            self.setText(self._original_label)
        else:
            self._set_copy_icon()
            self.setToolTip("Copy")
