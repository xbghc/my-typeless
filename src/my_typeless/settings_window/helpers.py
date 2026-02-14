"""Stitch 设计稿 UI 工厂函数"""

from typing import Callable
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QApplication
)
from PyQt6.QtCore import QTimer, QSize, Qt
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor


def make_section_header(title: str, description: str) -> QWidget:
    """创建区域标题 (Stitch: text-xl semibold #1a1a1a, desc text-sm #5d5d5d)"""
    w = QWidget()
    layout = QVBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 16)
    layout.setSpacing(4)
    t = QLabel(title)
    t.setFont(QFont("Inter", 15, QFont.Weight.DemiBold))
    t.setStyleSheet("color: #1a1a1a;")
    layout.addWidget(t)
    d = QLabel(description)
    d.setStyleSheet("color: #5d5d5d; font-size: 12px;")
    layout.addWidget(d)
    return w


def make_field_label(text: str) -> QLabel:
    """Stitch: text-sm font-medium #1a1a1a"""
    label = QLabel(text)
    label.setStyleSheet("color: #1a1a1a; font-size: 12px; font-weight: 500;")
    return label


def make_text_input(placeholder: str = "", text: str = "", password: bool = False) -> QLineEdit:
    """Stitch: border #d1d5db rounded-md, focus:ring primary/20 focus:border primary"""
    edit = QLineEdit(text)
    edit.setPlaceholderText(placeholder)
    if password:
        edit.setEchoMode(QLineEdit.EchoMode.Password)
    edit.setFixedHeight(34)
    edit.setStyleSheet("""
        QLineEdit {
            border: 1px solid #d1d5db; border-radius: 6px;
            padding: 4px 12px; font-size: 13px; color: #1a1a1a;
            background: #ffffff;
        }
        QLineEdit:focus {
            border-color: #2b8cee;
        }
    """)
    return edit


class CopyButton(QPushButton):
    """Button that copies text to clipboard and shows visual feedback."""

    def __init__(self, text_getter: Callable[[], str] | str, label: str = "", parent=None):
        super().__init__(label, parent)
        self._text_getter = text_getter if callable(text_getter) else lambda: text_getter
        self._original_text = label
        self._saved_icon = QIcon()

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._on_click)

        self._timer = QTimer()
        self._timer.setInterval(1500)
        self._timer.timeout.connect(self._reset)
        self._timer.setSingleShot(True)

    def _on_click(self):
        text = self._text_getter()
        if text:
            QApplication.clipboard().setText(text)

            if not self._timer.isActive():
                self._saved_icon = self.icon()

            self.setIcon(self.generate_check_icon())
            if self._original_text:
                self.setText("Copied!")
            self._timer.start()

    def _reset(self):
        self.setIcon(self._saved_icon)
        if self._original_text:
            self.setText(self._original_text)

    @staticmethod
    def generate_copy_icon() -> QIcon:
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = painter.pen()
        pen.setColor(QColor("#9ca3af"))
        pen.setWidthF(1.4)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.drawRoundedRect(5, 1, 10, 10, 2, 2)
        painter.drawRoundedRect(1, 5, 10, 10, 2, 2)
        painter.end()
        return QIcon(pixmap)

    @staticmethod
    def generate_check_icon() -> QIcon:
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = painter.pen()
        pen.setColor(QColor("#22c55e"))
        pen.setWidthF(1.5)
        painter.setPen(pen)

        painter.drawLine(3, 8, 7, 12)
        painter.drawLine(7, 12, 13, 4)
        painter.end()
        return QIcon(pixmap)
