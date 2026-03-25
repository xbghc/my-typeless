## 2026-03-25 - Optimize RMS calculation using math.hypot
**Learning:** When calculating the root mean square (RMS) of audio samples, using the C-optimized `math.hypot(*samples)` with chunking (to prevent stack exhaustion) is significantly faster (~5x) than using a Python generator expression.
**Action:** Replace generator expressions computing sum of squares with `math.hypot` where applicable for performance optimization in Python hot loops.
