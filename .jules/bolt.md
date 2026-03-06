## 2024-05-24 - [Optimize RMS calculation with math.hypot]
**Learning:** For calculating the root mean square (RMS) of audio samples packed in bytes, `math.hypot(*samples) / math.sqrt(count)` is significantly faster (~4.5x - 7.5x) than summing squares via a Python generator expression `math.sqrt(sum(s*s for s in samples) / count)` because `math.hypot` is C-optimized.
**Action:** Use `math.hypot(*samples)` instead of generator expressions when performing intensive distance or energy calculations in hot loops.
