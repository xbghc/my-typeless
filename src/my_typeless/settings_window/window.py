"""设置窗口主类 - 基于 Stitch 设计稿 (左侧导航 + 右侧配置面板)"""

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QStackedWidget,
    QListWidget, QListWidgetItem, QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from my_typeless.config import AppConfig
from my_typeless.icons import load_app_icon
from my_typeless.version import __version__ as APP_VERSION
from my_typeless.settings_window.hotkey_button import HotkeyButton
from my_typeless.settings_window.test_page import TestPageMixin
from my_typeless.settings_window.history_page import HistoryPageMixin


class SettingsWindow(QMainWindow, TestPageMixin, HistoryPageMixin):
    """设置窗口 - 基于 Stitch 设计稿 (左侧导航 + 右侧配置面板)"""

    settings_saved = pyqtSignal(object)  # 发送 AppConfig
    _test_done = pyqtSignal(str, bool)    # (result_text, is_error)

    def __init__(self, config: AppConfig):
        super().__init__()
        self._config = config
        self._test_done.connect(self._on_test_done)
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle("Settings")
        self.setFixedSize(820, 540)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setWindowIcon(load_app_icon())
        # Stitch: font-family Inter, Segoe UI
        self.setStyleSheet("""
            QMainWindow { background: #ffffff; }
            * { font-family: 'Inter', 'Segoe UI', sans-serif; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === 左侧导航栏 (Stitch: bg #f3f3f3, border #e5e5e5, w-64=256px) ===
        sidebar = QWidget()
        sidebar.setFixedWidth(256)
        sidebar.setStyleSheet("background: #f3f3f3; border-right: 1px solid #e5e5e5;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(24, 24, 24, 16)

        # Logo / 标题 (Stitch: text-lg semibold #1a1a1a)
        title_label = QLabel("Settings")
        title_label.setFont(QFont("Inter", 14, QFont.Weight.DemiBold))
        title_label.setStyleSheet("color: #1a1a1a; border: none;")
        sidebar_layout.addWidget(title_label)

        subtitle_label = QLabel("My Typeless")
        subtitle_label.setStyleSheet("color: #5d5d5d; font-size: 11px; border: none; margin-bottom: 16px;")
        sidebar_layout.addWidget(subtitle_label)

        # 导航列表 (Stitch: active=white bg+shadow, inactive=#5d5d5d hover:bg black/5%)
        self._nav_list = QListWidget()
        self._nav_list.setStyleSheet("""
            QListWidget {
                border: none; background: transparent; font-size: 13px;
                outline: none;
            }
            QListWidget::item {
                padding: 8px 12px; border-radius: 8px; margin-bottom: 2px;
                color: #5d5d5d;
            }
            QListWidget::item:selected {
                background: #ffffff; color: #1a1a1a; font-weight: 500;
            }
            QListWidget::item:hover:!selected {
                background: rgba(0, 0, 0, 0.05);
            }
        """)
        for label, icon_char in [("General", "⚙"), ("Speech-to-Text", "🎤"), ("Text Refinement", "✏"), ("Glossary", "📖"), ("Playground", "🧪"), ("History", "📝")]:
            item = QListWidgetItem(f"{icon_char}  {label}")
            self._nav_list.addItem(item)
        self._nav_list.setCurrentRow(0)
        self._nav_list.currentRowChanged.connect(self._switch_page)
        sidebar_layout.addWidget(self._nav_list, 1)

        # 版本号 (Stitch: info icon + Version 1.2.0, #5d5d5d)
        version_label = QLabel(f"ℹ  Version {APP_VERSION}")
        version_label.setStyleSheet("color: #5d5d5d; font-size: 11px; border: none;")
        sidebar_layout.addWidget(version_label)

        main_layout.addWidget(sidebar)

        # === 右侧内容区 (Stitch: bg #ffffff) ===
        right_panel = QWidget()
        right_panel.setStyleSheet("background: #ffffff;")
        right_outer = QVBoxLayout(right_panel)
        right_outer.setContentsMargins(0, 0, 0, 0)
        right_outer.setSpacing(0)

        # 可滚动内容区域
        content_widget = QWidget()
        content_widget.setStyleSheet("background: #ffffff;")
        right_content = QVBoxLayout(content_widget)
        right_content.setContentsMargins(24, 28, 24, 16)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._create_general_page())    # 0
        self._stack.addWidget(self._create_stt_page())        # 1
        self._stack.addWidget(self._create_llm_page())        # 2
        self._stack.addWidget(self._create_glossary_page())   # 3
        self._stack.addWidget(self._create_test_page())       # 4
        self._stack.addWidget(self._create_history_page())    # 5
        right_content.addWidget(self._stack)

        right_outer.addWidget(content_widget, 1)

        # 底部操作栏 (Stitch: bg-win-bg/50, border-t, py-4 px-8)
        footer = QWidget()
        footer.setFixedHeight(56)
        footer.setStyleSheet("background: rgba(243, 243, 243, 0.5); border-top: 1px solid #e5e5e5;")
        btn_layout = QHBoxLayout(footer)
        btn_layout.setContentsMargins(32, 0, 32, 0)
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(80, 34)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #ffffff; border: 1px solid #d1d5db;
                border-radius: 6px; color: #1a1a1a; font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background: #f9fafb; }
            QPushButton:pressed { background: #f3f4f6; }
        """)
        cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setFixedSize(80, 34)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #2b8cee; border: none; border-radius: 6px;
                color: white; font-size: 13px; font-weight: 500;
            }
            QPushButton:hover { background: #2563eb; }
            QPushButton:pressed { background: #1d4ed8; }
        """)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        right_outer.addWidget(footer)
        main_layout.addWidget(right_panel)

    # ── UI helpers ──

    def _make_section_header(self, title: str, description: str) -> QWidget:
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

    def _make_field_label(self, text: str) -> QLabel:
        """Stitch: text-sm font-medium #1a1a1a"""
        label = QLabel(text)
        label.setStyleSheet("color: #1a1a1a; font-size: 12px; font-weight: 500;")
        return label

    def _make_text_input(self, placeholder: str = "", text: str = "", password: bool = False) -> QLineEdit:
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

    def _make_setting_card(self) -> QWidget:
        """Stitch: card with border #e5e5e5, bg white, rounded-lg, shadow-win-card, p-4"""
        card = QWidget()
        card.setStyleSheet("""
            QWidget {
                background: #ffffff;
                border: 1px solid #e5e5e5;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        return card

    # ---- General 页 (Stitch: card-style settings) ----
    def _create_general_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._make_section_header("General", "Configure basic application behavior."))

        # Hotkey card (Stitch: p-4 rounded-lg border #e5e5e5 bg white shadow)
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
        # Stitch: toggle w-11 h-6, bg-gray-200, checked bg-primary #2b8cee
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

    # ---- Speech-to-Text 页 (Stitch: section with Active badge) ----
    def _create_stt_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header with "Active" badge (from Stitch)
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

        layout.addWidget(self._make_field_label("API Base URL"))
        self._stt_url = self._make_text_input("https://api.example.com/v1", self._config.stt.base_url)
        layout.addWidget(self._stt_url)
        layout.addSpacing(4)

        layout.addWidget(self._make_field_label("API Key"))
        self._stt_key = self._make_text_input("sk-...", self._config.stt.api_key, password=True)
        layout.addWidget(self._stt_key)
        layout.addSpacing(4)

        layout.addWidget(self._make_field_label("Model Name"))
        self._stt_model = self._make_text_input("whisper-large-v3", self._config.stt.model)
        layout.addWidget(self._stt_model)

        layout.addStretch()
        return page

    # ---- Text Refinement 页 ----
    def _create_llm_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header with "Active" badge
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

        layout.addWidget(self._make_field_label("API Base URL"))
        self._llm_url = self._make_text_input("https://api.deepseek.com/v1", self._config.llm.base_url)
        layout.addWidget(self._llm_url)
        layout.addSpacing(4)

        layout.addWidget(self._make_field_label("API Key"))
        self._llm_key = self._make_text_input("sk-...", self._config.llm.api_key, password=True)
        layout.addWidget(self._llm_key)
        layout.addSpacing(4)

        layout.addWidget(self._make_field_label("Model Name"))
        self._llm_model = self._make_text_input("deepseek-chat", self._config.llm.model)
        layout.addWidget(self._llm_model)
        layout.addSpacing(4)

        layout.addWidget(self._make_field_label("System Prompt"))
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

        layout.addWidget(self._make_section_header(
            "Glossary",
            "Terminology for accurate speech recognition and text refinement."
        ))

        # 添加术语行：输入框 + 按钮
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

        # 术语列表
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

        # 底部：计数 + 删除按钮
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
        # 去重
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

    # ── Core ──

    def _switch_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        # 切换到历史页时刷新
        if index == 5:
            self._refresh_history()

    def _save(self) -> None:
        """收集表单数据并保存配置"""
        self._config.hotkey = self._hotkey_btn.hotkey
        self._config.start_with_windows = self._autostart_cb.isChecked()

        self._config.stt.base_url = self._stt_url.text().strip()
        self._config.stt.api_key = self._stt_key.text().strip()
        self._config.stt.model = self._stt_model.text().strip()

        self._config.llm.base_url = self._llm_url.text().strip()
        self._config.llm.api_key = self._llm_key.text().strip()
        self._config.llm.model = self._llm_model.text().strip()
        self._config.llm.prompt = self._llm_prompt.toPlainText().strip()

        self._config.glossary = self._get_glossary()

        self._config.save()
        self.settings_saved.emit(self._config)
        self.close()

    def update_config(self, config: AppConfig) -> None:
        """用新的配置更新界面"""
        self._config = config
