## 2024-05-24 - Dynamic ARIA labels for toggle buttons
**Learning:** For icon-only buttons that toggle state (like visibility toggles), JavaScript handlers must explicitly update the `aria-label` and `title` attributes to reflect the new state for screen reader accessibility, rather than relying solely on static HTML attributes.
**Action:** When implementing toggle functionality, ensure JS updates both visual indicators (icons) and semantic attributes (`aria-label`, `title`) simultaneously.
