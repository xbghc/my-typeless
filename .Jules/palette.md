## 2025-02-12 - [Accessibility] Icon-Only Buttons
**Learning:** The application uses icon-only buttons (e.g., password visibility toggle) without `aria-label` attributes, making them inaccessible to screen readers.
**Action:** Systematically check all icon-only buttons for `aria-label` or `title` attributes.

## 2025-02-12 - [UX] Action Feedback
**Learning:** Instantaneous actions like "Copy" lack visual feedback, leaving users unsure if the action succeeded.
**Action:** Implement temporary state changes (e.g., button text change to "Copied!") for immediate feedback.
