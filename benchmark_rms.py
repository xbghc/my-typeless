import math
import struct
import time
import statistics

def calc_rms_old(data: bytes) -> float:
    count = len(data) // 2
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", data)
    sum_sq = sum(s * s for s in samples)
    return math.sqrt(sum_sq / count)

def calc_rms_new(data: bytes) -> float:
    count = len(data) // 2
    if count == 0:
        return 0.0
    samples = struct.unpack(f"<{count}h", data)
    # Using math.hypot with batching of 512
    sum_sq = 0.0
    for i in range(0, count, 512):
        chunk = samples[i:i+512]
        hypot = math.hypot(*chunk)
        sum_sq += hypot * hypot
    return math.sqrt(sum_sq / count)

data = b'\x01\x00' * 1024

def benchmark():
    t_old = []
    t_new = []
    for _ in range(10):
        start = time.perf_counter()
        for _ in range(10000):
            calc_rms_old(data)
        t_old.append(time.perf_counter() - start)

        start = time.perf_counter()
        for _ in range(10000):
            calc_rms_new(data)
        t_new.append(time.perf_counter() - start)

    print(f"Old mean: {statistics.mean(t_old):.4f}s")
    print(f"New mean: {statistics.mean(t_new):.4f}s")
    print(f"Speedup: {statistics.mean(t_old) / statistics.mean(t_new):.2f}x")

    # Assert correctness
    assert math.isclose(calc_rms_old(data), calc_rms_new(data))

benchmark()
