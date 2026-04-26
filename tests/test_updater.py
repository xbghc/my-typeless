from my_typeless import updater


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
