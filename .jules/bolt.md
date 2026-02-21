## 2025-02-21 - [Sequential Pipeline Bottleneck]
**Learning:** The existing STT -> LLM processing was serialized within a single loop, causing unnecessary wait times for the next audio segment while the previous text was being refined.
**Action:** Use a producer-consumer pipeline with separate threads for STT and LLM to overlap I/O and processing, significantly reducing latency.
