"""图标与资源加载工具"""

import math
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer


RESOURCES_DIR = Path(__file__).parent / "resources"


def load_svg_icon(filename: str, size: int = 64, *, hidpi: bool = True) -> QIcon:
    """从 SVG 文件加载图标。

    hidpi=True（默认）时生成多倍率 pixmap 以适配高 DPI 窗口图标；
    hidpi=False 时只生成单一尺寸，适用于系统托盘等由系统管理缩放的场景。
    """
    svg_path = RESOURCES_DIR / filename
    if not svg_path.exists():
        return QIcon()
    renderer = QSvgRenderer(str(svg_path))
    icon = QIcon()
    if hidpi:
        screen = QApplication.primaryScreen()
        max_scale = max(1, math.ceil(screen.devicePixelRatio())) if screen else 2
        for scale in range(1, max_scale + 1):
            px = size * scale
            pixmap = QPixmap(px, px)
            pixmap.fill(Qt.GlobalColor.transparent)
            pixmap.setDevicePixelRatio(scale)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            icon.addPixmap(pixmap)
    else:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def load_app_icon() -> QIcon:
    """加载应用图标（优先 SVG，回退 .ico）"""
    svg_path = RESOURCES_DIR / "app_icon.svg"
    if svg_path.exists():
        return load_svg_icon("app_icon.svg", size=128)
    ico_path = RESOURCES_DIR / "app_icon.ico"
    if ico_path.exists():
        return QIcon(str(ico_path))
    return QIcon()
