"""
自动更新模块 - 通过 GitHub Releases 检查和下载更新

工作流:
1. 启动时 / 定时 检查 GitHub Releases 最新版本
2. 若发现新版本，弹出通知提示用户
3. 用户确认后下载新版 exe 并替换当前文件
4. 提示用户重启应用
"""

import json
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import QMessageBox

from my_typeless.version import __version__

logger = logging.getLogger(__name__)

# ── 配置 ─────────────────────────────────────────────────────────────────
GITHUB_OWNER = "xbghc"
GITHUB_REPO = "my-typeless"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
CHECK_INTERVAL_MS = 4 * 60 * 60 * 1000  # 4 小时

ASSET_NAME = "MyTypeless-Setup.exe"


# ── 数据结构 ──────────────────────────────────────────────────────────────
@dataclass
class ReleaseInfo:
    """GitHub Release 信息"""
    tag: str          # e.g. "v1.2.0"
    version: str      # e.g. "1.2.0"
    name: str         # Release 标题
    body: str         # Release 描述 (Markdown)
    download_url: str # 可执行文件下载地址
    size: int         # 文件大小 (bytes)
    published_at: str


# ── 版本比较 ──────────────────────────────────────────────────────────────
def _parse_version(v: str) -> tuple[int, ...]:
    """解析版本号字符串为元组，忽略前缀 'v' 和预发布后缀（如 '-rc1'）"""
    v = v.lstrip("vV").split("-")[0]
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    return tuple(parts)


def is_newer(remote: str, local: str = __version__) -> bool:
    """判断远程版本是否比本地更新"""
    return _parse_version(remote) > _parse_version(local)


# ── GitHub API ────────────────────────────────────────────────────────────
def fetch_latest_release() -> Optional[ReleaseInfo]:
    """
    从 GitHub API 获取最新 Release 信息。
    返回 None 表示无可用更新或请求失败。
    """
    url = f"{GITHUB_API}/releases/latest"
    req = Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"MyTypeless/{__version__}",
    })
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except (URLError, OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to fetch release info: %s", e)
        return None

    tag: str = data.get("tag_name", "")
    version = tag.lstrip("vV")
    if not version:
        return None

    # 查找 exe 资产
    download_url = ""
    size = 0
    for asset in data.get("assets", []):
        if asset.get("name", "").lower() == ASSET_NAME.lower():
            download_url = asset["browser_download_url"]
            size = asset.get("size", 0)
            break

    if not download_url:
        logger.info("No matching asset '%s' found in release %s", ASSET_NAME, tag)
        return None

    return ReleaseInfo(
        tag=tag,
        version=version,
        name=data.get("name", tag),
        body=data.get("body", ""),
        download_url=download_url,
        size=size,
        published_at=data.get("published_at", ""),
    )


def download_release(release: ReleaseInfo, dest: Path,
                     progress_cb=None) -> bool:
    """
    下载 Release 资产到 dest 路径。
    progress_cb(downloaded_bytes, total_bytes) 可选进度回调。
    """
    req = Request(release.download_url, headers={
        "User-Agent": f"MyTypeless/{__version__}",
    })
    try:
        with urlopen(req, timeout=120) as resp:
            total = release.size or int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)
        return True
    except (URLError, OSError) as e:
        logger.error("Download failed: %s", e)
        if dest.exists():
            dest.unlink()
        return False


# ── 更新执行 ──────────────────────────────────────────────────────────────
def apply_update(setup_exe: Path) -> bool:
    """
    运行下载的安装程序执行静默升级。
    Inno Setup 支持 /SILENT 静默安装，/SUPPRESSMSGBOXES 抑制弹窗，
    /CLOSEAPPLICATIONS 自动关闭旧进程。
    成功启动安装程序后返回 True，由调用方负责退出当前进程。
    """
    if not setup_exe.exists():
        logger.error("Setup file not found: %s", setup_exe)
        return False

    try:
        subprocess.Popen(
            [str(setup_exe), "/SILENT", "/SUPPRESSMSGBOXES"],
            close_fds=True,
        )
        return True
    except OSError as e:
        logger.error("Failed to launch installer: %s", e)
        return False


# ── 后台检查线程 ──────────────────────────────────────────────────────────
class _CheckWorker(QObject):
    """在子线程执行网络请求"""
    finished = pyqtSignal(object)  # ReleaseInfo | None

    def run(self):
        release = fetch_latest_release()
        if release and is_newer(release.version):
            self.finished.emit(release)
        else:
            self.finished.emit(None)


class _DownloadWorker(QObject):
    """在子线程下载更新包"""
    progress = pyqtSignal(int, int)  # downloaded, total
    finished = pyqtSignal(bool, str)  # success, file_path

    def __init__(self, release: ReleaseInfo):
        super().__init__()
        self._release = release

    def run(self):
        tmp_dir = Path(tempfile.mkdtemp())
        tmp = tmp_dir / "MyTypeless-Setup.exe"
        ok = download_release(
            self._release, tmp,
            progress_cb=lambda d, t: self.progress.emit(d, t),
        )
        if not ok:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        self.finished.emit(ok, str(tmp))


class UpdateChecker(QObject):
    """
    主线程中使用的更新管理器。

    典型用法:
        checker = UpdateChecker(parent=tray_icon)
        checker.start()
    """
    update_available = pyqtSignal(object)   # ReleaseInfo
    update_downloaded = pyqtSignal(str)       # 新 exe 路径
    update_error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.check_now)
        self._thread: QThread | None = None
        self._dl_thread: QThread | None = None
        self._prompting = False

    def start(self, immediate: bool = True):
        """启动定时检查"""
        if immediate:
            self.check_now()
        self._timer.start(CHECK_INTERVAL_MS)

    def stop(self):
        """停止定时检查"""
        self._timer.stop()

    def check_now(self):
        """立即检查一次"""
        if self._thread is not None and self._thread.isRunning():
            return
        self._thread = QThread()
        self._worker = _CheckWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_check_done)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(lambda: setattr(self, '_thread', None))
        self._thread.start()

    def download(self, release: ReleaseInfo):
        """开始下载新版本"""
        if self._dl_thread is not None and self._dl_thread.isRunning():
            return
        self._dl_thread = QThread()
        self._dl_worker = _DownloadWorker(release)
        self._dl_worker.moveToThread(self._dl_thread)
        self._dl_thread.started.connect(self._dl_worker.run)
        self._dl_worker.finished.connect(self._on_download_done)
        self._dl_worker.finished.connect(self._dl_thread.quit)
        self._dl_worker.finished.connect(self._dl_worker.deleteLater)
        self._dl_thread.finished.connect(self._dl_thread.deleteLater)
        self._dl_thread.finished.connect(lambda: setattr(self, '_dl_thread', None))
        self._dl_thread.start()

    # ── 内部槽 ────
    def _on_check_done(self, release):
        if release is not None and not self._prompting:
            self.update_available.emit(release)

    def _on_download_done(self, success: bool, path: str):
        if success:
            self.update_downloaded.emit(path)
        else:
            self.update_error.emit("下载更新失败，请稍后重试")


def prompt_and_apply_update(release: ReleaseInfo, checker: UpdateChecker):
    """
    便捷函数：弹出更新提示对话框，用户确认后开始下载。
    一般由 update_available 信号触发。
    """
    checker._prompting = True
    try:
        size_mb = release.size / (1024 * 1024) if release.size else 0
        msg = (
            f"发现新版本: {release.name} (v{release.version})\n\n"
            f"当前版本: v{__version__}\n"
            f"文件大小: {size_mb:.1f} MB\n\n"
            f"是否立即更新？"
        )

        reply = QMessageBox.question(
            None,
            "My Typeless 更新",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            checker.download(release)
    finally:
        checker._prompting = False
