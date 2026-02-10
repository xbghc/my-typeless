"""Stitch 设计稿 UI 工厂函数"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit
from PyQt6.QtGui import QFont


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
