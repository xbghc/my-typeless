## 2026-03-25 - C-Optimized RMS Calculation
**Learning:** When calculating the root mean square (RMS) of audio chunks in Python's hot loops, using a generator expression inside `sum()` is slow. `math.hypot(*samples)` leverages C-optimized evaluation, making the calculation ~3x faster. Argument unpacking of 512 elements is well within modern Python stack limits.
**Action:** Always prefer `math.hypot(*samples)` over Python-level loops or generator expressions for RMS or euclidean distance on reasonably sized arrays.
