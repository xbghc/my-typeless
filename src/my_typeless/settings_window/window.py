"""设置窗口主类 - 薄容器，组装各页面 Mixin"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget,
    QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from my_typeless.config import AppConfig
from my_typeless.icons import load_app_icon
from my_typeless.version import __version__ as APP_VERSION
from my_typeless.settings_window.config_pages import ConfigPagesMixin
from my_typeless.settings_window.test_page import TestPageMixin
from my_typeless.settings_window.history_page import HistoryPageMixin


class SettingsWindow(QMainWindow, ConfigPagesMixin, TestPageMixin, HistoryPageMixin):
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
        self.setStyleSheet("""
            QMainWindow { background: #ffffff; }
            * { font-family: 'Inter', 'Segoe UI', sans-serif; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === 左侧导航栏 ===
        sidebar = QWidget()
        sidebar.setFixedWidth(256)
        sidebar.setStyleSheet("background: #f3f3f3; border-right: 1px solid #e5e5e5;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(24, 24, 24, 16)

        title_label = QLabel("Settings")
        title_label.setFont(QFont("Inter", 14, QFont.Weight.DemiBold))
        title_label.setStyleSheet("color: #1a1a1a; border: none;")
        sidebar_layout.addWidget(title_label)

        subtitle_label = QLabel("My Typeless")
        subtitle_label.setStyleSheet("color: #5d5d5d; font-size: 11px; border: none; margin-bottom: 16px;")
        sidebar_layout.addWidget(subtitle_label)

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

        version_label = QLabel(f"ℹ  Version {APP_VERSION}")
        version_label.setStyleSheet("color: #5d5d5d; font-size: 11px; border: none;")
        sidebar_layout.addWidget(version_label)

        main_layout.addWidget(sidebar)

        # === 右侧内容区 ===
        right_panel = QWidget()
        right_panel.setStyleSheet("background: #ffffff;")
        right_outer = QVBoxLayout(right_panel)
        right_outer.setContentsMargins(0, 0, 0, 0)
        right_outer.setSpacing(0)

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

        # 底部操作栏
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

    # ── Core ──

    def _switch_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
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
