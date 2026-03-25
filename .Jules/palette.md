## 2026-03-25 - Semantic Navigation Buttons
**Learning:** In-page navigation items (like sidebars and tabs) that use `<a>` tags without `href` attributes are inaccessible to native keyboard navigation, as they are not focusable by default.
**Action:** Always use semantic `<button>` elements for in-page navigation items to ensure native keyboard focusability and add standardized focus states using Tailwind's `focus-visible` classes.
