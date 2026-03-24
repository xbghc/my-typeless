## 2026-03-24 - Accessible State Toggles
**Learning:** Icon-only buttons that toggle state (like visibility toggles) must explicitly update their `aria-label` and `title` attributes using JavaScript to reflect the new state for screen readers, instead of just changing their visual icon.
**Action:** Always add dynamic `aria-label` and `title` updates to JavaScript handlers that toggle visual states on icon buttons.
