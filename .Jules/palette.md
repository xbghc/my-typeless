## 2024-05-24 - Dynamic ARIA Labels for Stateful Icon Buttons
**Learning:** For icon-only buttons that toggle state (like showing/hiding a password), adding an initial `aria-label` and `title` is not enough for accessibility. When the visual state (the icon) changes, the accessible name must also change dynamically, or screen reader users will receive contradictory information.
**Action:** Always ensure that JavaScript handlers that update the visual state of a button also explicitly update its `aria-label` and `title` attributes to reflect the new state.
