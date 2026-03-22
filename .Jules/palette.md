## 2024-05-24 - Semantic Buttons for Navigation
**Learning:** Using `<a>` tags without `href` attributes for in-page navigation (like sidebars and tabs) breaks keyboard accessibility because they are not natively focusable or operable via keyboard without additional scripting.
**Action:** Use semantic `<button>` elements instead of `<a>` tags for in-page navigation to ensure native keyboard focusability and accessibility. Apply classes like `w-full text-left focus-visible:ring-2 focus-visible:ring-primary focus-visible:outline-none` for standardized focus states.
