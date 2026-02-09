"""系统托盘 + 设置窗口 - 基于 Stitch 设计稿实现"""

import sys
import threading
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QStackedWidget,
    QListWidget, QListWidgetItem, QCheckBox, QSystemTrayIcon,
    QMenu, QMessageBox, QSizePolicy, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QIcon, QAction, QFont, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

from my_typeless.config import AppConfig
from my_typeless.llm_client import LLMClient
from my_typeless.history import HistoryEntry, load_history, add_history, clear_history


RESOURCES_DIR = Path(__file__).parent / "resources"
APP_VERSION = "1.0.3"


def _load_svg_icon(filename: str, size: int = 64) -> QIcon:
    """从 SVG 文件加载图标"""
    svg_path = RESOURCES_DIR / filename
    if not svg_path.exists():
        return QIcon()
    renderer = QSvgRenderer(str(svg_path))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


class HotkeyButton(QPushButton):
    """热键捕获按钮 - 点击后进入监听状态，使用 keyboard 库捕获按键以区分左右修饰键"""

    hotkey_changed = pyqtSignal(str)

    # 允许作为热键的键名集合（keyboard 库的名称）
    _ALLOWED_KEYS = {
        "left alt", "right alt", "alt",
        "left ctrl", "right ctrl", "ctrl",
        "left shift", "right shift", "shift",
        "left windows", "right windows",
        "caps lock", "tab", "space",
        "f1", "f2", "f3", "f4", "f5", "f6",
        "f7", "f8", "f9", "f10", "f11", "f12",
    }

    def __init__(self, current_hotkey: str = "right alt"):
        super().__init__()
        self._hotkey = current_hotkey
        self._listening = False
        self._kb_hook = None
        self._update_display()
        self.clicked.connect(self._start_listening)
        self.setFixedHeight(32)
        self.setMinimumWidth(100)

    @property
    def hotkey(self) -> str:
        return self._hotkey

    def _update_display(self) -> None:
        if self._listening:
            self.setText("⌨  Press a key...")
            self.setStyleSheet("""
                QPushButton {
                    background: #EFF6FF; border: 2px solid #2b8cee;
                    border-radius: 4px; padding: 4px 12px; color: #2b8cee;
                    font-size: 12px; font-weight: 500;
                }
            """)
        else:
            self.setText(f"⌨  {self._hotkey.title()}")
            self.setStyleSheet("""
                QPushButton {
                    background: #f3f4f6; border: 1px solid #d1d5db;
                    border-radius: 4px; padding: 4px 12px; color: #1a1a1a;
                    font-size: 12px; font-weight: 500;
                }
                QPushButton:hover { background: #e5e7eb; }
            """)

    def _start_listening(self) -> None:
        self._listening = True
        self._update_display()
        # 使用 keyboard 库全局 hook 捕获按键，可正确区分左右修饰键
        import keyboard as kb
        self._kb_hook = kb.hook(self._on_kb_event, suppress=False)

    def _stop_listening(self) -> None:
        if self._kb_hook is not None:
            import keyboard as kb
            kb.unhook(self._kb_hook)
            self._kb_hook = None
        self._listening = False
        self._update_display()

    def _on_kb_event(self, event) -> None:
        """keyboard 库的回调，在后台线程中执行，通过 QTimer 切回主线程"""
        import keyboard as kb
        if event.event_type != kb.KEY_DOWN:
            return

        key_name = event.name
        if not key_name:
            return

        # ESC 取消
        if key_name == "esc":
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self._stop_listening)
            return

        # 仅接受白名单中的键
        if key_name.lower() not in self._ALLOWED_KEYS:
            return

        self._hotkey = key_name.lower()
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._finish_capture)

    def _finish_capture(self) -> None:
        """主线程中完成捕获流程"""
        self._stop_listening()
        self.hotkey_changed.emit(self._hotkey)

    def keyPressEvent(self, event) -> None:
        """监听模式下吞掉 Qt 按键事件，防止 Alt 触发菜单激活"""
        if self._listening:
            event.accept()
            return
        super().keyPressEvent(event)

    def event(self, event) -> bool:
        """拦截 ShortcutOverride，防止 Alt 按下导致窗口失焦"""
        from PyQt6.QtCore import QEvent
        if self._listening and event.type() == QEvent.Type.ShortcutOverride:
            event.accept()
            return True
        return super().event(event)


class SettingsWindow(QMainWindow):
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
        self.setFixedSize(700, 500)  # Stitch: 700x500
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
        )
        # 设置窗口图标
        ico_path = RESOURCES_DIR / "app_icon.ico"
        if ico_path.exists():
            self.setWindowIcon(QIcon(str(ico_path)))
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
        right_content.setContentsMargins(32, 32, 32, 16)

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

    # ---- Test 页 ----
    def _create_test_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._make_section_header(
            "Prompt Playground",
            "Test text refinement with current prompt settings. No microphone needed."
        ))

        # -- Raw Input --
        input_label_row = QHBoxLayout()
        input_label = self._make_field_label("Raw Input")
        input_label_row.addWidget(input_label)
        input_label_row.addStretch()
        input_hint = QLabel("Simulate transcription")
        input_hint.setStyleSheet("color: #9ca3af; font-size: 12px;")
        input_label_row.addWidget(input_hint)
        layout.addLayout(input_label_row)

        self._test_input = QTextEdit()
        self._test_input.setPlaceholderText("在这里输入模拟的语音转录文本…")
        self._test_input.setMinimumHeight(100)
        self._test_input.setMaximumHeight(120)
        self._test_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d1d5db; border-radius: 8px;
                padding: 10px 12px; font-size: 13px; color: #1a1a1a;
                background: #ffffff; line-height: 1.5;
            }
            QTextEdit:focus { border-color: #2b8cee; }
        """)
        layout.addWidget(self._test_input)

        # -- Run button --
        run_row = QHBoxLayout()
        run_row.addStretch()
        self._test_run_btn = QPushButton("  ▶  Run  ")
        self._test_run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._test_run_btn.setFixedHeight(32)
        self._test_run_btn.setStyleSheet("""
            QPushButton {
                background: #2b8cee; border: none; border-radius: 6px;
                color: white; font-size: 13px; font-weight: 500;
                padding: 0 16px;
            }
            QPushButton:hover { background: #1a7bd9; }
            QPushButton:pressed { background: #1565c0; }
            QPushButton:disabled { background: #93c5fd; color: rgba(255,255,255,0.8); }
        """)
        self._test_run_btn.clicked.connect(self._run_test)
        run_row.addWidget(self._test_run_btn)
        layout.addLayout(run_row)

        # -- Refined Output --
        output_label_row = QHBoxLayout()
        output_label = self._make_field_label("Refined Output")
        output_label_row.addWidget(output_label)
        output_label_row.addStretch()
        self._test_copy_btn = QPushButton("📋 Copy")
        self._test_copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._test_copy_btn.setStyleSheet("""
            QPushButton {
                border: none; background: transparent;
                color: #2b8cee; font-size: 12px; font-weight: 500;
                padding: 0 4px;
            }
            QPushButton:hover { color: #1a7bd9; }
        """)
        self._test_copy_btn.clicked.connect(self._copy_test_output)
        output_label_row.addWidget(self._test_copy_btn)
        layout.addLayout(output_label_row)

        self._test_output = QTextEdit()
        self._test_output.setReadOnly(True)
        self._test_output.setPlaceholderText("精修结果将显示在这里…")
        self._test_output.setMinimumHeight(100)
        self._test_output.setMaximumHeight(120)
        self._test_output.setStyleSheet("""
            QTextEdit {
                border: 1px solid transparent; border-radius: 8px;
                padding: 10px 12px; font-size: 13px; color: #1a1a1a;
                background: #f9fafb; line-height: 1.5;
            }
        """)
        layout.addWidget(self._test_output)

        # -- Status bar --
        status_row = QHBoxLayout()
        self._test_status_dot = QLabel("●")
        self._test_status_dot.setFixedWidth(12)
        self._test_status_dot.setStyleSheet("color: #22c55e; font-size: 8px;")
        status_row.addWidget(self._test_status_dot)
        self._test_status = QLabel("System Ready")
        self._test_status.setStyleSheet("color: #5d5d5d; font-size: 11px; font-weight: 500;")
        status_row.addWidget(self._test_status)
        status_row.addStretch()
        layout.addLayout(status_row)

        layout.addStretch()
        return page

    def _copy_test_output(self) -> None:
        """复制精修结果到剪贴板"""
        text = self._test_output.toPlainText()
        if text:
            QApplication.clipboard().setText(text)

    # ---- History 页 (Stitch 设计) ----
    def _create_history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._make_section_header(
            "History",
            "Review past refinement results to optimize your prompt."
        ))

        # ── Scrollable list ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: #ffffff; }
            QScrollBar:vertical {
                width: 6px; background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #d1d5db; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self._history_container = QWidget()
        self._history_container.setStyleSheet("background: #ffffff;")
        self._history_layout = QVBoxLayout(self._history_container)
        self._history_layout.setContentsMargins(0, 0, 0, 0)
        self._history_layout.setSpacing(12)
        self._history_layout.addStretch()

        scroll.setWidget(self._history_container)
        layout.addWidget(scroll, 1)

        # ── Clear button ──
        clear_row = QHBoxLayout()
        clear_row.addStretch()
        clear_btn = QPushButton("🗑  Clear History")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet("""
            QPushButton {
                border: none; background: transparent;
                color: #ef4444; font-size: 13px; font-weight: 600;
                padding: 6px 16px; border-radius: 8px;
            }
            QPushButton:hover { background: rgba(239, 68, 68, 0.08); }
        """)
        clear_btn.clicked.connect(self._clear_history)
        clear_row.addWidget(clear_btn)
        clear_row.addStretch()
        layout.addLayout(clear_row)

        return page

    def _refresh_history(self) -> None:
        """重新加载历史记录并渲染卡片"""
        # 清空现有内容
        while self._history_layout.count():
            item = self._history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        entries = load_history()

        if not entries:
            empty = QLabel("No history yet. Use voice dictation or the Test page to generate entries.")
            empty.setStyleSheet("color: #9ca3af; font-size: 13px;")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._history_layout.addWidget(empty)
            self._history_layout.addStretch()
            return

        for entry in entries:
            card = self._make_history_card(entry)
            self._history_layout.addWidget(card)

        self._history_layout.addStretch()

    @staticmethod
    def _calc_duration(t_start: str | None, t_end: str | None) -> str | None:
        """从两个 HH:MM:SS.ffffff 时间字符串计算耗时，返回可读文本"""
        if not t_start or not t_end:
            return None
        try:
            from datetime import datetime as _dt
            fmt = "%H:%M:%S.%f"
            delta = _dt.strptime(t_end, fmt) - _dt.strptime(t_start, fmt)
            ms = int(delta.total_seconds() * 1000)
            if ms < 1000:
                return f"{ms}ms"
            return f"{ms / 1000:.1f}s"
        except (ValueError, TypeError):
            return None

    def _make_history_card(self, entry: HistoryEntry) -> QWidget:
        """创建单条历史记录卡片（极简模式 + 可展开详情）"""
        card = QWidget()
        card.setObjectName("hCard")
        card.setStyleSheet("""
            QWidget#hCard {
                background: #ffffff;
                border: 1px solid #e5e5e5;
                border-radius: 8px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # ── Header row: timestamp only ──
        header = QWidget()
        header.setStyleSheet("border: none;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 10, 16, 10)

        ts_label = QLabel(entry.timestamp)
        ts_label.setStyleSheet("color: #9ca3af; font-size: 12px; font-weight: 500;")
        header_layout.addWidget(ts_label)
        header_layout.addStretch()
        card_layout.addWidget(header)

        # ── Divider ──
        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: #f3f4f6; border: none;")
        card_layout.addWidget(divider)

        _small_btn_ss = """
            QPushButton {
                border: none; background: transparent;
                color: #9ca3af; font-size: 13px; font-weight: 600;
            }
            QPushButton:hover { color: #6b7280; }
        """

        # ── Refined output + copy + toggle (same row) ──
        body = QWidget()
        body.setStyleSheet("border: none;")
        body_row = QHBoxLayout(body)
        body_row.setContentsMargins(16, 12, 16, 8)
        body_row.setSpacing(4)

        out_text = QLabel(entry.refined_output)
        out_text.setStyleSheet("color: #1a1a1a; font-size: 13px;")
        out_text.setWordWrap(True)
        body_row.addWidget(out_text, 1)

        copy_btn = QPushButton()
        copy_btn.setFixedSize(24, 24)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setToolTip("Copy")
        copy_btn.setStyleSheet(_small_btn_ss)
        # 绘制极简 copy 图标（两个重叠方块）
        _cp = QPixmap(16, 16)
        _cp.fill(Qt.GlobalColor.transparent)
        _cpainter = QPainter(_cp)
        _cpainter.setRenderHint(QPainter.RenderHint.Antialiasing)
        _cpen = _cpainter.pen()
        _cpen.setColor(QColor("#9ca3af"))
        _cpen.setWidthF(1.4)
        _cpainter.setPen(_cpen)
        _cpainter.setBrush(Qt.BrushStyle.NoBrush)
        _cpainter.drawRoundedRect(5, 1, 10, 10, 2, 2)
        _cpainter.drawRoundedRect(1, 5, 10, 10, 2, 2)
        _cpainter.end()
        copy_btn.setIcon(QIcon(_cp))
        copy_btn.setIconSize(QSize(16, 16))
        _output = entry.refined_output
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(_output))
        body_row.addWidget(copy_btn, 0, Qt.AlignmentFlag.AlignTop)

        toggle_btn = QPushButton("▸")
        toggle_btn.setFixedSize(24, 24)
        toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle_btn.setStyleSheet(_small_btn_ss)
        body_row.addWidget(toggle_btn, 0, Qt.AlignmentFlag.AlignTop)
        card_layout.addWidget(body)

        # ── Expandable detail section ──
        detail_widget = QWidget()
        detail_widget.setStyleSheet("border: none;")
        detail_widget.setVisible(False)
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(16, 10, 16, 4)
        detail_layout.setSpacing(8)

        # 原始转录
        raw_label = QLabel("原始转录")
        raw_label.setStyleSheet(
            "color: #9ca3af; font-size: 11px; font-weight: 700;"
            "letter-spacing: 0.5px;"
        )
        detail_layout.addWidget(raw_label)

        raw_text = QLabel(entry.raw_input)
        raw_text.setStyleSheet(
            "color: #6b7280; font-size: 13px;"
            "background: #f9fafb; border-radius: 4px; padding: 8px;"
        )
        raw_text.setWordWrap(True)
        detail_layout.addWidget(raw_text)

        # 耗时指标
        stt_dur = self._calc_duration(entry.key_release_at, entry.stt_done_at)
        llm_dur = self._calc_duration(entry.stt_done_at, entry.llm_done_at)
        if stt_dur or llm_dur:
            metrics_layout = QHBoxLayout()
            metrics_layout.setSpacing(16)
            _metric_ss = "color: #9ca3af; font-size: 11px; font-weight: 500; border: none;"
            if stt_dur:
                metrics_layout.addWidget(QLabel(f"转录耗时 {stt_dur}"))
                metrics_layout.itemAt(metrics_layout.count() - 1).widget().setStyleSheet(_metric_ss)
            if llm_dur:
                metrics_layout.addWidget(QLabel(f"润色耗时 {llm_dur}"))
                metrics_layout.itemAt(metrics_layout.count() - 1).widget().setStyleSheet(_metric_ss)
            metrics_layout.addStretch()
            detail_layout.addLayout(metrics_layout)

        # Playground 按钮
        _action_link_ss = """
            QPushButton {
                border: none; background: transparent;
                color: #2b8cee; font-size: 12px; font-weight: 600;
            }
            QPushButton:hover { color: #1a7bd9; }
        """
        retest_btn = QPushButton("🧪 Playground")
        retest_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        retest_btn.setStyleSheet(_action_link_ss)
        retest_btn.clicked.connect(lambda _checked=False, txt=entry.raw_input: self._retest_with(txt))
        detail_layout.addWidget(retest_btn, 0, Qt.AlignmentFlag.AlignLeft)

        card_layout.addWidget(detail_widget)

        def _toggle():
            showing = not detail_widget.isVisible()
            detail_widget.setVisible(showing)
            toggle_btn.setText("▾" if showing else "▸")

        toggle_btn.clicked.connect(_toggle)

        return card

    def _clear_history(self) -> None:
        """清空历史记录"""
        reply = QMessageBox.question(
            self, "Clear History",
            "Are you sure you want to clear all history?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            clear_history()
            self._refresh_history()

    def _retest_with(self, raw_input: str) -> None:
        """跳转到 Test 页面并预填入历史输入文本"""
        self._test_input.setPlainText(raw_input)
        self._test_output.setPlainText("")
        self._test_status_dot.setStyleSheet("color: #22c55e; font-size: 8px;")
        self._test_status.setText("System Ready")
        self._test_status.setStyleSheet("color: #5d5d5d; font-size: 11px; font-weight: 500;")
        # 切换到 Test 页 (index 4)
        self._nav_list.setCurrentRow(4)

    def _run_test(self) -> None:
        """使用当前配置调用 LLM 精修测试文本"""
        raw_text = self._test_input.toPlainText().strip()
        if not raw_text:
            self._test_status_dot.setStyleSheet("color: #ef4444; font-size: 8px;")
            self._test_status.setText("Please enter some text.")
            self._test_status.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: 500;")
            return

        # 读取当前表单中的配置（可能尚未保存）
        from my_typeless.config import LLMConfig, AppConfig
        llm_config = LLMConfig(
            base_url=self._llm_url.text().strip() or self._config.llm.base_url,
            api_key=self._llm_key.text().strip() or self._config.llm.api_key,
            model=self._llm_model.text().strip() or self._config.llm.model,
            prompt=self._llm_prompt.toPlainText().strip() or self._config.llm.prompt,
        )
        glossary = self._get_glossary()
        temp_config = AppConfig(llm=llm_config, glossary=glossary)
        full_system_prompt = temp_config.build_llm_system_prompt()

        self._test_run_btn.setEnabled(False)
        self._test_run_btn.setText("…")
        self._test_output.setPlainText("")
        self._test_status_dot.setStyleSheet("color: #2b8cee; font-size: 8px;")
        self._test_status.setText("Calling LLM…")
        self._test_status.setStyleSheet("color: #2b8cee; font-size: 11px; font-weight: 500;")

        def _call():
            try:
                client = LLMClient(llm_config)
                result = client.refine(raw_text, system_prompt=full_system_prompt)
                self._test_done.emit(result, False)
            except Exception as e:
                self._test_done.emit(str(e), True)

        threading.Thread(target=_call, daemon=True).start()

    def _on_test_done(self, text: str, is_error: bool) -> None:
        self._test_run_btn.setEnabled(True)
        self._test_run_btn.setText("  ▶  Run  ")
        if is_error:
            self._test_output.setPlainText("")
            self._test_status_dot.setStyleSheet("color: #ef4444; font-size: 8px;")
            self._test_status.setText(f"Error: {text}")
            self._test_status.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: 500;")
        else:
            self._test_output.setPlainText(text)
            self._test_status_dot.setStyleSheet("color: #22c55e; font-size: 8px;")
            self._test_status.setText("Done")
            self._test_status.setStyleSheet("color: #22c55e; font-size: 11px; font-weight: 500;")
            # 记录到历史
            raw = self._test_input.toPlainText().strip()
            if raw and text:
                add_history(raw, text)

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


class TrayIcon(QSystemTrayIcon):
    """系统托盘图标 - 三种状态切换 + 右键菜单"""

    show_settings = pyqtSignal()
    quit_app = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icons = {
            "idle": _load_svg_icon("icon_idle.svg"),
            "recording": _load_svg_icon("icon_recording.svg"),
            "processing": _load_svg_icon("icon_processing.svg"),
        }
        self.setIcon(self._icons["idle"])
        self.setToolTip("My Typeless - Ready")

        # 右键菜单
        menu = QMenu()
        settings_action = QAction("Settings...", menu)
        settings_action.triggered.connect(self.show_settings.emit)
        menu.addAction(settings_action)

        menu.addSeparator()

        about_action = QAction("About", menu)
        about_action.triggered.connect(self._show_about)
        menu.addAction(about_action)

        menu.addSeparator()

        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit_app.emit)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

        # 双击托盘图标打开设置
        self.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_settings.emit()

    def set_state(self, state: str) -> None:
        """切换托盘图标状态 (idle / recording / processing)"""
        tooltips = {
            "idle": "My Typeless - Ready",
            "recording": "My Typeless - Recording...",
            "processing": "My Typeless - Processing...",
        }
        if state in self._icons:
            self.setIcon(self._icons[state])
            self.setToolTip(tooltips.get(state, "My Typeless"))

    def _show_about(self) -> None:
        QMessageBox.information(
            None,
            "About My Typeless",
            f"My Typeless v{APP_VERSION}\n\n"
            "AI-powered voice dictation for Windows.\n"
            "Hold hotkey to speak, release to get polished text.",
        )
