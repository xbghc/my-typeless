## 2024-03-19 - Optimize Audio RMS Calculation with `math.hypot`
**Learning:** When calculating the root mean square (RMS) of audio samples (or similar hot loops), using the C-optimized `math.hypot(*samples)` is significantly faster (~3x) than using a Python generator expression combined with `sum()` and `math.sqrt()`.
**Action:** Replace generator expressions computing sum of squares with `math.hypot` where unpacking overhead is acceptable (e.g. `count=512`).
