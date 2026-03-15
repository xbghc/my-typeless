
## 2024-11-13 - Stateful Icon Button and Sidebar Navigation Accessibility
**Learning:** In My Typeless, `<a>` tags without `href` attributes were used for sidebar navigation, breaking native keyboard accessibility (tab focus). Also, icon-only buttons like the password visibility toggle lacked stateful ARIA labels (Show/Hide password) limiting screen reader feedback.
**Action:** Always use semantic `<button>` elements for in-page navigation (tabs, sidebars) and apply `focus-visible` styles. For icon-only stateful buttons, ensure `aria-label` is dynamically updated along with the icon/state in JavaScript.
