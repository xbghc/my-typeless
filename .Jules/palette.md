# Palette's Journal

This journal tracks critical UX and accessibility learnings from the my-typeless project.

## 2024-05-22 - [Sidebar Navigation Accessibility]
**Learning:** Anchor tags (`<a>`) used for in-app navigation without `href` attributes are not keyboard focusable by default, breaking accessibility for keyboard users.
**Action:** Replace such anchors with `<button>` elements, ensuring they have `type='button'`, full width styling, and proper focus indicators (`focus-visible`).
