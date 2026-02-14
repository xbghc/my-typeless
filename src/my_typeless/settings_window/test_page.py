"""Playground (Test) 页面 Mixin"""

import threading
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit,
)
from PyQt6.QtCore import Qt, QSize

from my_typeless.llm_client import LLMClient
from my_typeless.history import add_history
from my_typeless.settings_window.helpers import make_section_header, make_field_label, CopyButton


class TestPageMixin:
    """Playground 页面的创建与交互逻辑，混入 SettingsWindow 使用。"""

    def _create_test_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(make_section_header(
            "Prompt Playground",
            "Test text refinement with current prompt settings. No microphone needed."
        ))

        # -- Raw Input --
        input_label_row = QHBoxLayout()
        input_label = make_field_label("Raw Input")
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
        output_label = make_field_label("Refined Output")
        output_label_row.addWidget(output_label)
        output_label_row.addStretch()
        self._test_copy_btn = CopyButton(
            text_getter=self._test_output.toPlainText,
            label="Copy"
        )
        self._test_copy_btn.setIcon(CopyButton.generate_copy_icon())
        self._test_copy_btn.setIconSize(QSize(14, 14))
        self._test_copy_btn.setStyleSheet("""
            QPushButton {
                border: none; background: transparent;
                color: #2b8cee; font-size: 12px; font-weight: 500;
                padding: 0 4px;
                text-align: left;
            }
            QPushButton:hover { color: #1a7bd9; }
        """)
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
