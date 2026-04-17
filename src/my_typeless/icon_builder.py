"""SVG→ICO 转换。dev 模式首次启动时生成；生产模式下 ICO 已在构建时预生成。"""

import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

RESOURCES = Path(__file__).parent / "resources"
SVG_PATH = RESOURCES / "app_icon.svg"
ICO_PATH = RESOURCES / "app_icon.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]


def ensure_app_ico() -> Path | None:
    """返回可用的 ICO 路径；不可用时返回 None（调用方静默跳过）。"""
    if ICO_PATH.exists():
        return ICO_PATH
    if not SVG_PATH.exists():
        return None
    try:
        import resvg_py
        from PIL import Image
    except ImportError:
        logger.info(
            "resvg_py/Pillow 不可用，跳过 ICO 自动生成（可运行 scripts/build.py）"
        )
        return None
    try:
        imgs = [
            Image.open(
                io.BytesIO(
                    bytes(
                        resvg_py.svg_to_bytes(
                            svg_path=str(SVG_PATH), width=s, height=s
                        )
                    )
                )
            ).convert("RGBA")
            for s in SIZES
        ]
        imgs[-1].save(
            ICO_PATH,
            format="ICO",
            sizes=[(s, s) for s in SIZES],
            append_images=imgs[:-1],
        )
        logger.info("Generated %s", ICO_PATH)
        return ICO_PATH
    except Exception as e:
        logger.warning("ICO 生成失败: %s", e)
        return None
