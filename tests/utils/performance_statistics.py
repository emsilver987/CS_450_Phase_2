"""
Performance statistics calculation utilities.
Shared helper functions for both unit and integration tests.
"""
import math
from typing import List


def calculate_mean(values: List[float]) -> float:
    """Calculate mean of values"""
    return sum(values) / len(values) if values else 0.0


def calculate_median(values: List[float]) -> float:
    """Calculate median of values"""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    n = len(sorted_values)
    if n % 2 == 0:
        return (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2
    else:
        return sorted_values[n // 2]


def calculate_percentile(values: List[float], percentile: float) -> float:
    """Calculate percentile of values (0-100)"""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    n = len(sorted_values)
    index = int(math.ceil(n * percentile / 100)) - 1
    index = max(0, min(index, n - 1))
    return sorted_values[index]


def calculate_throughput(total_bytes: int, total_time_seconds: float) -> float:
    """Calculate throughput in bytes per second"""
    if total_time_seconds <= 0:
        return 0.0
    return total_bytes / total_time_seconds


def calculate_error_rate(total_requests: int, successful_requests: int) -> float:
    """Calculate error rate as percentage"""
    if total_requests == 0:
        return 0.0
    return (total_requests - successful_requests) / total_requests * 100

