## 2025-02-18 - PyQt6 Headless Testing
**Learning:** PyQt6 unit testing in CI/headless environments requires `QT_QPA_PLATFORM=offscreen`. Heavy dependencies (`pywin32`, `openai`) dragged in by package imports must be mocked before importing GUI components.
**Action:** Always set `QT_QPA_PLATFORM=offscreen` and mock dependencies before importing GUI components.
