"""Stitch 设计稿 UI 工厂函数"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QPushButton, QApplication
)
from PyQt6.QtGui import QFont, QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import QTimer, Qt


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
    """
    A button that copies text to clipboard and shows visual feedback (checkmark or text change).
    Reverts to original state after 2 seconds.
    """
    def __init__(self, text_getter, parent=None):
        super().__init__(parent)
        self._text_getter = text_getter
        self.clicked.connect(self._copy)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._reset)

        self._original_icon = None
        self._original_text = None
        self._check_icon = self._create_check_icon()

    def _create_check_icon(self) -> QIcon:
        pix = QPixmap(16, 16)
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = painter.pen()
        pen.setColor(QColor("#22c55e"))  # Green
        pen.setWidth(2)
        painter.setPen(pen)

        # Draw checkmark
        painter.drawLine(3, 8, 6, 11)
        painter.drawLine(6, 11, 13, 4)
        painter.end()
        return QIcon(pix)

    def _copy(self):
        text = self._text_getter() if callable(self._text_getter) else self._text_getter
        if not text:
            return

        QApplication.clipboard().setText(text)

        # Save original state if not already saved (e.g. rapid clicks)
        if self._original_icon is None:
            self._original_icon = self.icon()
            self._original_text = self.text()

        # Update UI
        if self.text():
            self.setText("✓ Copied")
        else:
            self.setIcon(self._check_icon)

        self.setToolTip("Copied!")
        self._timer.start(2000)

    def _reset(self):
        if self._original_icon is not None:
            self.setIcon(self._original_icon)
            self._original_icon = None

        if self._original_text is not None:
            self.setText(self._original_text)
            self._original_text = None
