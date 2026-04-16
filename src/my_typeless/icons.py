"""图标与资源加载工具 - 使用 Pillow"""

from pathlib import Path

from PIL import Image

RESOURCES_DIR = Path(__file__).parent / "resources"


def load_tray_icon(name: str, size: int = 64) -> Image.Image:
    """加载托盘图标为 PIL Image（pystray 使用）

    优先加载预渲染的 PNG，回退到 ICO。
    """
    png_path = RESOURCES_DIR / f"{name}.png"
    if png_path.exists():
        img = Image.open(png_path)
        if img.size != (size, size):
            img = img.resize((size, size), Image.Resampling.LANCZOS)
        return img

    ico_path = RESOURCES_DIR / f"{name}.ico"
    if ico_path.exists():
        img = Image.open(ico_path)
        img = img.resize((size, size), Image.Resampling.LANCZOS)
        return img

    # 回退：生成纯色方块
    return Image.new("RGBA", (size, size), (100, 100, 100, 255))


def load_app_icon() -> Image.Image:
    """加载应用图标为 PIL Image"""
    ico_path = RESOURCES_DIR / "app_icon.ico"
    if ico_path.exists():
        return Image.open(ico_path)
    return Image.new("RGBA", (256, 256), (59, 157, 245, 255))
