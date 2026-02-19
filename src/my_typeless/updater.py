"""
自动更新模块 - 通过 GitHub Releases 检查和下载更新

工作流:
1. 启动时 / 定时 检查 GitHub Releases 最新版本
2. 若发现新版本，通过事件通知应用
3. 用户确认后下载新版安装程序
4. 启动安装程序并退出当前实例
"""

import json
import logging
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

from my_typeless.events import EventEmitter
from my_typeless.version import __version__

logger = logging.getLogger(__name__)

# ── 配置 ─────────────────────────────────────────────────────────────────
GITHUB_OWNER = "xbghc"
GITHUB_REPO = "my-typeless"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
CHECK_INTERVAL_S = 4 * 60 * 60  # 4 小时

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


# ── 后台检查器 ────────────────────────────────────────────────────────────
class UpdateChecker:
    """
    更新管理器，使用 threading.Timer 定时检查。

    Events:
        update_available(ReleaseInfo): 发现新版本
        update_downloaded(str): 下载完成，参数为安装程序路径
        update_error(str): 更新错误信息
    """

    def __init__(self):
        self.events = EventEmitter()
        self._timer: threading.Timer | None = None
        self._running = False

    def start(self, immediate: bool = True):
        """启动定时检查"""
        self._running = True
        if immediate:
            self.check_now()
        self._schedule_next()

    def stop(self):
        """停止定时检查"""
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _schedule_next(self):
        """安排下一次检查"""
        if not self._running:
            return
        self._timer = threading.Timer(CHECK_INTERVAL_S, self._timer_tick)
        self._timer.daemon = True
        self._timer.start()

    def _timer_tick(self):
        """定时器触发"""
        self.check_now()
        self._schedule_next()

    def check_now(self):
        """在后台线程立即检查一次"""
        threading.Thread(target=self._do_check, daemon=True).start()

    def download(self, release: ReleaseInfo):
        """在后台线程开始下载新版本"""
        threading.Thread(
            target=self._do_download, args=(release,), daemon=True
        ).start()

    def _do_check(self):
        if ".dev" in __version__:
            logger.debug("Skip update check in dev mode (version=%s)", __version__)
            return
        release = fetch_latest_release()
        if release and is_newer(release.version):
            self.events.emit("update_available", release)

    def _do_download(self, release: ReleaseInfo):
        tmp_dir = Path(tempfile.mkdtemp())
        tmp = tmp_dir / "MyTypeless-Setup.exe"
        ok = download_release(release, tmp)
        if ok:
            self.events.emit("update_downloaded", str(tmp))
        else:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            self.events.emit("update_error", "下载更新失败，请稍后重试")
