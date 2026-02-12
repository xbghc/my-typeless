## 2024-05-22 - Reusable Feedback Pattern for Copy Actions
**Learning:** Centralizing micro-interactions (like "Copy" -> "Copied!" -> "Copy") in a dedicated widget (`CopyButton`) prevents code duplication and ensures consistent visual feedback across different UI contexts (icon-only vs text buttons).
**Action:** Use `CopyButton` for any future copy-to-clipboard actions instead of manual `QClipboard` calls.
