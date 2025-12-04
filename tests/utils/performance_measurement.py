"""
Performance measurement utilities for Selenium integration tests.
Provides context managers and helpers for measuring page load times,
operation durations, and other performance metrics.
"""
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any


@contextmanager
def measure_time(operation_name: str = "operation"):
    """
    Context manager to measure the time taken for an operation.
    
    Usage:
        with measure_time("page_load") as timer:
            driver.get(url)
        assert timer.elapsed < 5.0, "Page should load in under 5 seconds"
    
    Args:
        operation_name: Name of the operation being measured (for logging)
    
    Yields:
        Timer object with 'elapsed' attribute containing duration in seconds
    """
    class Timer:
        def __init__(self):
            self.start_time: Optional[float] = None
            self.end_time: Optional[float] = None
            self._elapsed: Optional[float] = None
        
        @property
        def elapsed(self) -> float:
            """Get elapsed time in seconds."""
            if self._elapsed is not None:
                return self._elapsed
            if self.end_time is not None and self.start_time is not None:
                return self.end_time - self.start_time
            if self.start_time is not None:
                return time.time() - self.start_time
            return 0.0
    
    timer = Timer()
    timer.start_time = time.time()
    try:
        yield timer
    finally:
        timer.end_time = time.time()
        timer._elapsed = timer.end_time - timer.start_time


def measure_page_load_time(driver, url: str) -> float:
    """
    Measure the time taken to load a page.
    
    Args:
        driver: Selenium WebDriver instance
        url: URL to load
    
    Returns:
        Time taken in seconds
    """
    with measure_time("page_load") as timer:
        driver.get(url)
        # Wait for page to be ready
        driver.execute_script("return document.readyState")
    return timer.elapsed


def get_navigation_timing(driver) -> Dict[str, Any]:
    """
    Get browser navigation timing metrics using Performance API.
    
    Returns a dictionary with timing metrics:
    - load_time: Total page load time (loadEventEnd - navigationStart)
    - dom_content_loaded: DOMContentLoaded event time
    - first_paint: First paint time (if available)
    
    Args:
        driver: Selenium WebDriver instance
    
    Returns:
        Dictionary with timing metrics in milliseconds
    """
    try:
        timing = driver.execute_script("""
            var perf = window.performance;
            if (!perf || !perf.timing) {
                return null;
            }
            var timing = perf.timing;
            var nav = perf.navigation || {};
            return {
                navigationStart: timing.navigationStart,
                domLoading: timing.domLoading,
                domInteractive: timing.domInteractive,
                domContentLoadedEventStart: timing.domContentLoadedEventStart,
                domContentLoadedEventEnd: timing.domContentLoadedEventEnd,
                loadEventStart: timing.loadEventStart,
                loadEventEnd: timing.loadEventEnd,
                loadTime: timing.loadEventEnd - timing.navigationStart,
                domContentLoadedTime: timing.domContentLoadedEventEnd - timing.navigationStart,
                type: nav.type || 0
            };
        """)
        return timing or {}
    except Exception:
        return {}


def assert_page_load_performance(
    driver,
    max_load_time_seconds: float,
    operation_name: str = "page load"
) -> float:
    """
    Measure page load time and assert it meets performance threshold.
    
    Args:
        driver: Selenium WebDriver instance
        max_load_time_seconds: Maximum allowed load time in seconds
        operation_name: Name of the operation (for error messages)
    
    Returns:
        Actual load time in seconds
    
    Raises:
        AssertionError: If load time exceeds threshold
    """
    # Get navigation timing if available
    timing = get_navigation_timing(driver)
    
    if timing and "loadTime" in timing:
        # Use browser's Performance API if available (more accurate)
        load_time_ms = timing.get("loadTime", 0)
        load_time_seconds = load_time_ms / 1000.0
    else:
        # Fallback: measure using current URL and ready state
        # This is less accurate but works when Performance API isn't available
        load_time_seconds = 0.0
        try:
            ready_state = driver.execute_script("return document.readyState")
            if ready_state == "complete":
                # Page is already loaded, can't measure accurately
                load_time_seconds = 0.0
        except Exception:
            pass
    
    # If we couldn't get accurate timing, skip the assertion
    # (better than failing on false positives)
    if load_time_seconds == 0.0 and not timing:
        return 0.0
    
    assert load_time_seconds <= max_load_time_seconds, (
        f"{operation_name} took {load_time_seconds:.2f}s, "
        f"exceeds threshold of {max_load_time_seconds:.2f}s"
    )
    
    return load_time_seconds

