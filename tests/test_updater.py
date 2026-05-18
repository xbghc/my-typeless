import pytest

from my_typeless import updater
from my_typeless.updater import _parse_version, is_newer


class _FakeThread:
    def __init__(self, target=None, args=(), daemon=None):
        self.target = target
        self.args = args
        self.daemon = daemon
        self.started = False
        self.alive = False

    def start(self):
        self.started = True
        self.alive = True

    def is_alive(self):
        return self.alive


def test_check_now_skips_duplicate_running_thread(monkeypatch):
    created_threads: list[_FakeThread] = []

    def fake_thread(*args, **kwargs):
        t = _FakeThread(*args, **kwargs)
        created_threads.append(t)
        return t

    monkeypatch.setattr(updater.threading, "Thread", fake_thread)
    checker = updater.UpdateChecker()

    checker.check_now()
    checker.check_now()

    assert len(created_threads) == 1
    assert checker._check_thread is created_threads[0]
    assert created_threads[0].started is True


def test_check_now_allows_new_thread_after_previous_finished(monkeypatch):
    created_threads: list[_FakeThread] = []

    def fake_thread(*args, **kwargs):
        t = _FakeThread(*args, **kwargs)
        created_threads.append(t)
        return t

    monkeypatch.setattr(updater.threading, "Thread", fake_thread)
    checker = updater.UpdateChecker()

    checker.check_now()
    created_threads[0].alive = False
    checker.check_now()

    assert len(created_threads) == 2
    assert checker._check_thread is created_threads[1]


def test_download_skips_duplicate_running_thread(monkeypatch):
    created_threads: list[_FakeThread] = []

    def fake_thread(*args, **kwargs):
        t = _FakeThread(*args, **kwargs)
        created_threads.append(t)
        return t

    monkeypatch.setattr(updater.threading, "Thread", fake_thread)
    checker = updater.UpdateChecker()
    release = updater.ReleaseInfo(
        tag="v1.0.0",
        version="1.0.0",
        name="v1.0.0",
        body="",
        download_url="https://example.com/setup.exe",
        asset_name="MyTypeless-Setup-v1.0.0.exe",
        size=1,
        published_at="2026-01-01T00:00:00Z",
    )

    checker.download(release)
    checker.download(release)

    assert len(created_threads) == 1
    assert checker._download_thread is created_threads[0]


class _ImmediateThread:
    def __init__(self, target=None, args=(), daemon=None):
        self._target = target
        self._args = args
        self.daemon = daemon
        self._alive = False

    def start(self):
        self._alive = True
        if self._target:
            self._target(*self._args)
        self._alive = False

    def is_alive(self):
        return self._alive


def test_check_now_clears_thread_reference_after_finish(monkeypatch):
    monkeypatch.setattr(updater, "DEV_MODE", True)
    monkeypatch.setattr(updater.threading, "Thread", _ImmediateThread)
    checker = updater.UpdateChecker()

    checker.check_now()

    assert checker._check_thread is None


def test_do_download_success_emits_path_and_keeps_file_for_installer(monkeypatch, tmp_path):
    checker = updater.UpdateChecker()
    emitted_paths: list[str] = []
    checker.events.on("update_downloaded", emitted_paths.append)

    tmp_dir = tmp_path / "download-dir"
    tmp_dir.mkdir()
    monkeypatch.setattr(updater.tempfile, "mkdtemp", lambda: str(tmp_dir))

    def fake_download_release(release, dest):
        dest.write_bytes(b"binary")
        return True

    monkeypatch.setattr(updater, "download_release", fake_download_release)

    release = updater.ReleaseInfo(
        tag="v1.0.0",
        version="1.0.0",
        name="v1.0.0",
        body="",
        download_url="https://example.com/setup.exe",
        asset_name="MyTypeless-Setup-v1.0.0.exe",
        size=1,
        published_at="2026-01-01T00:00:00Z",
    )

    checker._do_download(release)

    assert len(emitted_paths) == 1
    saved = tmp_dir / "MyTypeless-Setup-v1.0.0.exe"
    assert emitted_paths[0] == str(saved)
    assert saved.exists() is True


# ── 版本号解析与比较 ──────────────────────────────────────────────────────
# updater 是否能正确判断"已是最新版"——一旦解析错误会导致用户永远收不到更新。


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.2.3", (1, 2, 3)),
        ("v1.2.3", (1, 2, 3)),
        ("V1.2.3", (1, 2, 3)),
        ("1.2.3-rc1", (1, 2, 3)),
        ("v1.0.5-rc2", (1, 0, 5)),
        ("1.2", (1, 2)),
        ("1", (1,)),
        ("1.2.3.4", (1, 2, 3, 4)),
        ("v0.0.0.dev0", (0, 0, 0)),
        ("", ()),
        ("vinvalid", ()),
    ],
)
def test_parse_version(raw, expected):
    assert _parse_version(raw) == expected


@pytest.mark.parametrize(
    "remote,local,expected",
    [
        ("v1.2.3", "v1.2.2", True),
        ("v1.2.3", "v1.2.3", False),
        ("v1.2.3", "v1.2.4", False),
        ("v1.2.0", "v1.1.99", True),
        ("v2.0.0", "v1.99.99", True),
        ("v1.2.3", "v1.2.3-rc1", False),
        ("v1.2.3-rc2", "v1.2.3-rc1", False),
        ("v1.2.3", "0.0.0.dev0", True),
        ("v1.0.0", "v1.0", True),
    ],
)
def test_is_newer(remote, local, expected):
    assert is_newer(remote, local) is expected


def test_is_newer_uses_local_version_default():
    """不传 local 参数时回落到模块加载时的 __version__（默认参数在函数定义时绑定）。"""
    assert is_newer("") is False
    assert is_newer("v999.0.0") is True
