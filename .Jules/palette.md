## 2025-02-14 - Clear Buttons and Copy Feedback
**Learning:** `QLineEdit.setClearButtonEnabled(True)` is a one-line "micro-UX" win that significantly reduces friction when editing long fields like API keys.
**Action:** Always check if text inputs should have clear buttons, especially for "paste-heavy" fields.

**Learning:** Temporary button state changes (text/icon + disable) via `QTimer.singleShot` provide immediate, non-blocking feedback for actions like "Copy to Clipboard", resolving "did it work?" uncertainty.
**Action:** Use this pattern for all non-visual actions (copy, save, submit) where a full toast notification might be overkill.
