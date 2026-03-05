## 2026-03-05 - Navigation Item Semantics
**Learning:** In a Single Page Application (SPA), using `<a>` tags for in-page navigation or view toggling can cause accessibility issues for screen readers and keyboard navigation, as links are typically expected to trigger an actual URL change or page reload.
**Action:** Use `<button>` tags with standardized focus states (e.g., `focus-visible:ring-2`) for elements that change local state or toggle views, preserving correct semantic meaning and improving keyboard navigation.
