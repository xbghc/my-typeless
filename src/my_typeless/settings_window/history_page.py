"""History 页面 Mixin"""

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QMessageBox, QScrollArea,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QIcon, QPixmap, QPainter

from my_typeless.history import HistoryEntry, load_history, clear_history
from my_typeless.settings_window.helpers import make_section_header


class HistoryPageMixin:
    """History 页面的创建与交互逻辑，混入 SettingsWindow 使用。"""

    def _create_history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(make_section_header(
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
            empty_container = QWidget()
            empty_layout = QVBoxLayout(empty_container)
            empty_layout.setSpacing(6)
            empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            msg = QLabel("No history yet")
            msg.setStyleSheet("color: #1a1a1a; font-size: 14px; font-weight: 600;")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(msg)

            sub = QLabel("Use voice dictation or the Playground to generate entries.")
            sub.setStyleSheet("color: #9ca3af; font-size: 13px;")
            sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(sub)

            btn = QPushButton("Go to Playground")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedWidth(140)
            btn.setStyleSheet("""
                QPushButton {
                    background: #ffffff; border: 1px solid #d1d5db;
                    border-radius: 6px; color: #1a1a1a; font-size: 13px;
                    padding: 6px 12px; margin-top: 8px;
                }
                QPushButton:hover { background: #f9fafb; border-color: #2b8cee; color: #2b8cee; }
            """)
            btn.clicked.connect(lambda: self._nav_list.setCurrentRow(4))
            empty_layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)

            self._history_layout.addWidget(empty_container)
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
        header_layout.setContentsMargins(16, 10, 16, 2)

        ts_label = QLabel(entry.timestamp)
        ts_label.setStyleSheet("color: #9ca3af; font-size: 12px; font-weight: 500;")
        header_layout.addWidget(ts_label)
        header_layout.addStretch()
        card_layout.addWidget(header)

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
        out_text.setWordWrap(False)
        out_text.setTextFormat(Qt.TextFormat.PlainText)
        # 折叠时：单行 + 省略号
        _font_metrics = out_text.fontMetrics()
        _elided = _font_metrics.elidedText(
            entry.refined_output.replace("\n", " "), Qt.TextElideMode.ElideRight, 400
        )
        out_text.setText(_elided)
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

        # 底部行：耗时指标（左） + Playground（右）
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(16)
        _metric_ss = "color: #9ca3af; font-size: 11px; font-weight: 500; border: none;"
        stt_dur = self._calc_duration(entry.key_release_at, entry.stt_done_at)
        llm_dur = self._calc_duration(entry.stt_done_at, entry.llm_done_at)
        if stt_dur:
            lbl = QLabel(f"转录耗时 {stt_dur}")
            lbl.setStyleSheet(_metric_ss)
            bottom_row.addWidget(lbl)
        if llm_dur:
            lbl = QLabel(f"润色耗时 {llm_dur}")
            lbl.setStyleSheet(_metric_ss)
            bottom_row.addWidget(lbl)
        bottom_row.addStretch()

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
        bottom_row.addWidget(retest_btn)
        detail_layout.addLayout(bottom_row)

        card_layout.addWidget(detail_widget)

        _full_text = entry.refined_output
        _elided_text = _elided

        def _toggle():
            showing = not detail_widget.isVisible()
            detail_widget.setVisible(showing)
            toggle_btn.setText("▾" if showing else "▸")
            if showing:
                out_text.setWordWrap(True)
                out_text.setText(_full_text)
            else:
                out_text.setWordWrap(False)
                out_text.setText(_elided_text)

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
