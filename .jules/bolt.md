## 2024-03-21 - Initial Creation
**Learning:** Initializing bolt journal
**Action:** Ready to record critical learnings.

## 2024-05-20 - Math.hypot for Audio RMS Calculation
**Learning:** In hot loops computing the Root Mean Square (RMS) of audio chunks, using Python generator expressions (e.g. `sum(s * s for s in samples)`) is slow. The C-optimized `math.hypot(*samples)` function is significantly faster (~5x) for this operation.
**Action:** Use `math.hypot(*samples) / math.sqrt(count)` instead of calculating sum of squares in Python when dealing with numerical arrays where `*samples` argument unpacking is safe (e.g., chunk size 1024).
