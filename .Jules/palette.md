## 2024-05-14 - Dynamic ARIA Labels on Toggle Buttons
**Learning:** For icon-only toggle buttons (like "Show/Hide Password" or a visibility eye icon), simply setting `aria-label` once is not sufficient. Screen readers will misreport the button's action if its state changes.
**Action:** When creating toggle buttons, use JavaScript event handlers to dynamically update both the `aria-label` and `title` attributes simultaneously (e.g., from "Show password" to "Hide password") to ensure the visual state perfectly matches the screen reader read-out.
