"""
构建脚本 - 生成 PyInstaller 可执行文件 + 版本信息
用法: python scripts/build.py [--version X.Y.Z]
"""

import argparse
import io
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "src" / "my_typeless" / "version.py"
SPEC_FILE = ROOT / "my_typeless.spec"
VERSION_INFO_FILE = ROOT / "file_version_info.txt"
RESOURCES_DIR = ROOT / "src" / "my_typeless" / "resources"


def _normalize_version(version: str) -> str:
    """去掉可能的 'v'/'V' 前缀，兼容 'v1.2.3' 与 '1.2.3' 两种写法"""
    return version.lstrip("vV") if version else version


def read_version() -> str:
    """从 version.py 读取当前版本号"""
    ns: dict = {}
    exec(VERSION_FILE.read_text(encoding="utf-8"), ns)
    return ns["__version__"]


def write_version(version: str) -> None:
    """将版本号注入 version.py（由 CI 在发布构建时调用）"""
    version = _normalize_version(version)
    VERSION_FILE.write_text(
        '"""Version module -- injected at build time by scripts/build.py."""\n\n'
        f'__version__ = "{version}"\n',
        encoding="utf-8",
    )
    print(f"[build] Version updated to {version}")


def generate_version_info(version: str) -> None:
    """生成 Windows 版本信息文件"""
    version = _normalize_version(version)
    base_version = re.split(r"[-+]", version, maxsplit=1)[0]
    parts = [int(x) for x in base_version.split(".")]
    while len(parts) < 4:
        parts.append(0)
    major, minor, patch, build = parts[:4]

    info = f"""\
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, {build}),
    prodvers=({major}, {minor}, {patch}, {build}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0),
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'xbghc'),
          StringStruct('FileDescription', 'My Typeless - AI Voice Dictation'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', 'MyTypeless'),
          StringStruct('OriginalFilename', 'MyTypeless.exe'),
          StringStruct('ProductName', 'My Typeless'),
          StringStruct('ProductVersion', '{version}'),
        ],
      )
    ]),
    VarFileInfo([VarStruct('Translation', [0x0409, 1200])])
  ],
)
"""
    VERSION_INFO_FILE.write_text(info, encoding="utf-8")
    print(f"[build] Version info file generated: {VERSION_INFO_FILE}")


def generate_ico() -> None:
    """从 app_icon.svg 生成包含多分辨率层的 app_icon.ico"""
    svg_path = RESOURCES_DIR / "app_icon.svg"
    ico_path = RESOURCES_DIR / "app_icon.ico"
    if not svg_path.exists():
        print(f"[build] SVG not found: {svg_path}, skipping ICO generation")
        return

    try:
        import resvg_py
        from PIL import Image
    except ImportError:
        if ico_path.exists():
            print("[build] resvg_py/Pillow not installed, using existing ICO file")
            return
        print("[build] ERROR: resvg_py/Pillow required for ICO generation but not installed", file=sys.stderr)
        sys.exit(1)

    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = []
    for size in sizes:
        png_data = bytes(resvg_py.svg_to_bytes(svg_path=str(svg_path), width=size, height=size))
        images.append(Image.open(io.BytesIO(png_data)).convert("RGBA"))

    # 以最大尺寸为基础保存，附带所有较小尺寸
    images[-1].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[:-1],
    )
    print(f"[build] ICO generated: {ico_path} ({len(sizes)} sizes)")


def generate_tray_pngs() -> None:
    """从 SVG 生成托盘图标 PNG（pystray 使用 Pillow Image，需要 PNG 格式）"""
    tray_icons = ["icon_idle", "icon_recording", "icon_processing"]
    try:
        import resvg_py
    except ImportError:
        # 检查 PNG 是否已存在
        all_exist = all((RESOURCES_DIR / f"{name}.png").exists() for name in tray_icons)
        if all_exist:
            print("[build] resvg_py not installed, using existing PNG files")
            return
        print("[build] WARNING: resvg_py not installed, cannot generate tray PNGs", file=sys.stderr)
        return

    size = 64
    for name in tray_icons:
        svg_path = RESOURCES_DIR / f"{name}.svg"
        png_path = RESOURCES_DIR / f"{name}.png"
        if not svg_path.exists():
            print(f"[build] SVG not found: {svg_path}, skipping")
            continue
        png_data = bytes(resvg_py.svg_to_bytes(svg_path=str(svg_path), width=size, height=size))
        png_path.write_bytes(png_data)

    print(f"[build] Tray PNGs generated: {', '.join(tray_icons)}")


def run_pyinstaller() -> None:
    """执行 PyInstaller 构建"""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(SPEC_FILE),
        "--clean",
        "--noconfirm",
    ]
    print(f"[build] Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print("[build] PyInstaller build failed!", file=sys.stderr)
        sys.exit(1)
    print("[build] Build completed successfully!")
    print(f"[build] Output: {ROOT / 'dist' / 'MyTypeless.exe'}")


def main():
    parser = argparse.ArgumentParser(description="Build My Typeless executable")
    parser.add_argument(
        "--version", "-v",
        help="Set version before building (e.g. 1.2.0)",
    )
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Only update version, skip PyInstaller build",
    )
    args = parser.parse_args()

    if args.version:
        write_version(args.version)
    
    version = read_version()
    print(f"[build] Building version {version}")

    generate_version_info(version)
    generate_ico()
    generate_tray_pngs()

    if not args.no_build:
        run_pyinstaller()


if __name__ == "__main__":
    main()
