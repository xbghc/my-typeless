## 2024-05-24 - math.hypot for Audio RMS Calculation
**Learning:** When calculating the root mean square (RMS) of audio sample streams unpacking using struct, using the C-optimized `math.hypot(*samples)` is significantly faster (around ~4-5x) than using a Python generator expression `math.sqrt(sum(s * s for s in samples) / count)`.
**Action:** Use `math.hypot` for unpacking arrays and computing norms whenever possible in hot loops, being mindful of argument limits on older Python versions (modern limits safely allow unpacking chunks like 512 or 1024 frames).
