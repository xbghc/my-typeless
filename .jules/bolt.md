
## 2024-03-04 - Optimize Audio RMS Calculation
**Learning:** When optimizing Python hot loops in the codebase (e.g., audio chunk processing), using the C-optimized `math.hypot(*samples)` function is significantly faster (~7.5x) than using Python generator expressions for computing the root mean square (RMS) of audio samples.
**Action:** Replace `math.sqrt(sum(s * s for s in samples) / count)` with `math.hypot(*samples) / math.sqrt(count)` for audio RMS calculation to reduce CPU usage during audio recording.
