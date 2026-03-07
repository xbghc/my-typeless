## 2024-05-15 - Anchor Tags Without Href Break Keyboard Navigation Accessibility
**Learning:** `<a>` tags without an `href` attribute (often used for JS-driven in-page navigation or tabs) are generally not keyboard focusable by default, causing a failure in keyboard accessibility.
**Action:** Always use semantic `<button>` elements for in-page navigation (like sidebars and tabs) to ensure they receive proper tab order and keyboard focus natively.
