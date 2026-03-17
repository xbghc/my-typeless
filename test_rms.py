import timeit
import math
import struct
import random
import sys

SAMPLE_WIDTH = 2
CHUNK_SIZE = 1024
# Generate random audio data (1024 bytes = 512 samples)
data = struct.pack(f"<{CHUNK_SIZE//SAMPLE_WIDTH}h", *[random.randint(-32768, 32767) for _ in range(CHUNK_SIZE//SAMPLE_WIDTH)])

def calculate_rms_old(data: bytes) -> float:
    count = len(data) // SAMPLE_WIDTH
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", data)
    sum_sq = sum(s * s for s in samples)
    return math.sqrt(sum_sq / count)

def calculate_rms_hypot(data: bytes) -> float:
    count = len(data) // SAMPLE_WIDTH
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", data)
    return math.hypot(*samples) / math.sqrt(count)

print("Old time:", timeit.timeit(lambda: calculate_rms_old(data), number=100000))
print("New time:", timeit.timeit(lambda: calculate_rms_hypot(data), number=100000))
