"""General / STT / LLM / Glossary 配置页面 Mixin"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit,
    QListWidget, QListWidgetItem, QCheckBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from my_typeless.settings_window.helpers import make_section_header, make_field_label, make_text_input
from my_typeless.settings_window.hotkey_button import HotkeyButton


class ConfigPagesMixin:
    """General / STT / LLM / Glossary 四个配置页面，混入 SettingsWindow 使用。"""

    # ---- General 页 ----
    def _create_general_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(make_section_header("General", "Configure basic application behavior."))

        # Hotkey card
        hk_card = QWidget()
        hk_card.setStyleSheet("""
            QWidget#hkCard {
                background: #ffffff; border: 1px solid #e5e5e5;
                border-radius: 8px;
            }
        """)
        hk_card.setObjectName("hkCard")
        hk_row = QHBoxLayout(hk_card)
        hk_row.setContentsMargins(16, 12, 16, 12)
        hk_left = QVBoxLayout()
        hk_label = QLabel("Global Hotkey")
        hk_label.setStyleSheet("color: #1a1a1a; font-size: 13px; font-weight: 500; border: none;")
        hk_left.addWidget(hk_label)
        hk_desc = QLabel("Press to start/stop dictation")
        hk_desc.setStyleSheet("color: #5d5d5d; font-size: 11px; border: none;")
        hk_left.addWidget(hk_desc)
        hk_row.addLayout(hk_left)
        hk_row.addStretch()
        self._hotkey_btn = HotkeyButton(self._config.hotkey)
        hk_row.addWidget(self._hotkey_btn)
        layout.addWidget(hk_card)

        # Start with Windows card
        sw_card = QWidget()
        sw_card.setStyleSheet("""
            QWidget#swCard {
                background: #ffffff; border: 1px solid #e5e5e5;
                border-radius: 8px;
            }
        """)
        sw_card.setObjectName("swCard")
        sw_row = QHBoxLayout(sw_card)
        sw_row.setContentsMargins(16, 12, 16, 12)
        sw_left = QVBoxLayout()
        sw_label = QLabel("Start with Windows")
        sw_label.setStyleSheet("color: #1a1a1a; font-size: 13px; font-weight: 500; border: none;")
        sw_left.addWidget(sw_label)
        sw_desc = QLabel("Launch automatically on login")
        sw_desc.setStyleSheet("color: #5d5d5d; font-size: 11px; border: none;")
        sw_left.addWidget(sw_desc)
        sw_row.addLayout(sw_left)
        sw_row.addStretch()
        self._autostart_cb = QCheckBox()
        self._autostart_cb.setChecked(self._config.start_with_windows)
        self._autostart_cb.setStyleSheet("""
            QCheckBox::indicator { width: 44px; height: 24px; }
            QCheckBox::indicator:unchecked {
                border-radius: 12px; background: #d1d5db;
            }
            QCheckBox::indicator:checked {
                border-radius: 12px; background: #2b8cee;
            }
        """)
        sw_row.addWidget(self._autostart_cb)
        layout.addWidget(sw_card)

        layout.addStretch()
        return page

    # ---- Speech-to-Text 页 ----
    def _create_stt_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        stt_title = QLabel("Speech-to-Text API")
        stt_title.setFont(QFont("Inter", 13, QFont.Weight.DemiBold))
        stt_title.setStyleSheet("color: #1a1a1a;")
        header_row.addWidget(stt_title)
        header_row.addStretch()
        active_badge = QLabel("ACTIVE")
        active_badge.setStyleSheet("""
            background: rgba(43, 140, 238, 0.1); color: #2b8cee;
            font-size: 9px; font-weight: 700; letter-spacing: 1px;
            padding: 2px 8px; border-radius: 4px;
        """)
        header_row.addWidget(active_badge)
        layout.addLayout(header_row)
        layout.addSpacing(12)

        layout.addWidget(make_field_label("API Base URL"))
        self._stt_url = make_text_input("https://api.example.com/v1", self._config.stt.base_url)
        layout.addWidget(self._stt_url)
        layout.addSpacing(4)

        layout.addWidget(make_field_label("API Key"))
        self._stt_key = make_text_input("sk-...", self._config.stt.api_key, password=True)
        layout.addWidget(self._stt_key)
        layout.addSpacing(4)

        layout.addWidget(make_field_label("Model Name"))
        self._stt_model = make_text_input("whisper-large-v3", self._config.stt.model)
        layout.addWidget(self._stt_model)

        layout.addStretch()
        return page

    # ---- Text Refinement 页 ----
    def _create_llm_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        llm_title = QLabel("Text Refinement API")
        llm_title.setFont(QFont("Inter", 13, QFont.Weight.DemiBold))
        llm_title.setStyleSheet("color: #1a1a1a;")
        header_row.addWidget(llm_title)
        header_row.addStretch()
        active_badge = QLabel("ACTIVE")
        active_badge.setStyleSheet("""
            background: rgba(43, 140, 238, 0.1); color: #2b8cee;
            font-size: 9px; font-weight: 700; letter-spacing: 1px;
            padding: 2px 8px; border-radius: 4px;
        """)
        header_row.addWidget(active_badge)
        layout.addLayout(header_row)
        layout.addSpacing(12)

        layout.addWidget(make_field_label("API Base URL"))
        self._llm_url = make_text_input("https://api.deepseek.com/v1", self._config.llm.base_url)
        layout.addWidget(self._llm_url)
        layout.addSpacing(4)

        layout.addWidget(make_field_label("API Key"))
        self._llm_key = make_text_input("sk-...", self._config.llm.api_key, password=True)
        layout.addWidget(self._llm_key)
        layout.addSpacing(4)

        layout.addWidget(make_field_label("Model Name"))
        self._llm_model = make_text_input("deepseek-chat", self._config.llm.model)
        layout.addWidget(self._llm_model)
        layout.addSpacing(4)

        layout.addWidget(make_field_label("System Prompt"))
        self._llm_prompt = QTextEdit()
        self._llm_prompt.setPlainText(self._config.llm.prompt)
        self._llm_prompt.setFixedHeight(90)
        self._llm_prompt.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d1d5db; border-radius: 6px;
                padding: 8px; font-size: 13px; color: #1a1a1a;
                background: #ffffff;
            }
            QTextEdit:focus { border-color: #2b8cee; }
        """)
        layout.addWidget(self._llm_prompt)

        layout.addStretch()
        return page

    # ---- Glossary 页 ----
    def _create_glossary_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(make_section_header(
            "Glossary",
            "Terminology for accurate speech recognition and text refinement."
        ))

        add_row = QHBoxLayout()
        self._glossary_input = QLineEdit()
        self._glossary_input.setPlaceholderText("Enter a term, e.g. gRPC")
        self._glossary_input.setFixedHeight(34)
        self._glossary_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #d1d5db; border-radius: 6px;
                padding: 4px 12px; font-size: 13px; color: #1a1a1a;
                background: #ffffff;
            }
            QLineEdit:focus { border-color: #2b8cee; }
        """)
        self._glossary_input.returnPressed.connect(self._add_glossary_term)
        add_row.addWidget(self._glossary_input)

        add_btn = QPushButton("+ Add")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setFixedSize(72, 34)
        add_btn.setStyleSheet("""
            QPushButton {
                background: #2b8cee; border: none; border-radius: 6px;
                color: white; font-size: 13px; font-weight: 500;
            }
            QPushButton:hover { background: #2563eb; }
            QPushButton:pressed { background: #1d4ed8; }
        """)
        add_btn.clicked.connect(self._add_glossary_term)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        self._glossary_list = QListWidget()
        self._glossary_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._glossary_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e5e5e5; border-radius: 8px;
                background: #ffffff; font-size: 13px;
                font-family: 'Consolas', 'SF Mono', monospace;
                outline: none;
            }
            QListWidget::item {
                padding: 6px 12px; border-bottom: 1px solid #f3f4f6;
                color: #1a1a1a;
            }
            QListWidget::item:selected {
                background: #eff6ff; color: #1a1a1a;
            }
            QListWidget::item:hover:!selected {
                background: #f9fafb;
            }
        """)
        for term in self._config.glossary:
            self._glossary_list.addItem(term)
        layout.addWidget(self._glossary_list, 1)

        bottom_row = QHBoxLayout()
        self._glossary_count = QLabel(f"{self._glossary_list.count()} term(s)")
        self._glossary_count.setStyleSheet("color: #9ca3af; font-size: 11px;")
        bottom_row.addWidget(self._glossary_count)
        bottom_row.addStretch()

        del_btn = QPushButton("🗑  Delete Selected")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet("""
            QPushButton {
                border: none; background: transparent;
                color: #ef4444; font-size: 12px; font-weight: 600;
                padding: 4px 8px; border-radius: 6px;
            }
            QPushButton:hover { background: rgba(239, 68, 68, 0.08); }
        """)
        del_btn.clicked.connect(self._delete_glossary_terms)
        bottom_row.addWidget(del_btn)
        layout.addLayout(bottom_row)

        return page

    def _add_glossary_term(self) -> None:
        term = self._glossary_input.text().strip()
        if not term:
            return
        existing = [self._glossary_list.item(i).text() for i in range(self._glossary_list.count())]
        if term in existing:
            self._glossary_input.clear()
            return
        self._glossary_list.addItem(term)
        self._glossary_input.clear()
        self._glossary_count.setText(f"{self._glossary_list.count()} term(s)")

    def _delete_glossary_terms(self) -> None:
        for item in reversed(self._glossary_list.selectedItems()):
            self._glossary_list.takeItem(self._glossary_list.row(item))
        self._glossary_count.setText(f"{self._glossary_list.count()} term(s)")

    def _get_glossary(self) -> list:
        """从列表控件读取所有术语"""
        return [self._glossary_list.item(i).text() for i in range(self._glossary_list.count())]
