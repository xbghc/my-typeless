## 2024-05-23 - Sequential Processing Bottleneck
**Learning:** The `Worker` class was processing audio segments sequentially (STT -> LLM -> Next Segment), which introduced unnecessary latency. By parallelizing STT and LLM into separate threads connected by queues, we can overlap the processing of subsequent segments.
**Action:** When designing data pipelines involving multiple stages with I/O or compute delays (like network calls to STT/LLM APIs), use a producer-consumer model with queues to decouple stages and maximize throughput.
