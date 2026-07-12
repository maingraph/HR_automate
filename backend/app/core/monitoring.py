"""Performance monitoring utilities for tracking pipeline metrics."""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Generator

from app.core.logging import get_logger

log = get_logger(__name__)


class PerformanceMonitor:
    """Track and log performance metrics for pipeline operations."""
    
    def __init__(self):
        self.metrics: dict[str, list[float]] = {}
    
    @contextmanager
    def track(self, operation: str) -> Generator[None, None, None]:
        """Context manager to track operation duration.
        
        Usage:
            monitor = PerformanceMonitor()
            with monitor.track("scrape_linkedin"):
                # ... operation code ...
        """
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            if operation not in self.metrics:
                self.metrics[operation] = []
            self.metrics[operation].append(duration)
            log.info(f"⏱️  {operation}: {duration:.2f}s")
    
    def get_stats(self, operation: str) -> dict[str, float]:
        """Get statistics for a tracked operation.
        
        Returns:
            Dictionary with min, max, avg, total duration
        """
        if operation not in self.metrics or not self.metrics[operation]:
            return {"min": 0, "max": 0, "avg": 0, "total": 0, "count": 0}
        
        durations = self.metrics[operation]
        return {
            "min": min(durations),
            "max": max(durations),
            "avg": sum(durations) / len(durations),
            "total": sum(durations),
            "count": len(durations),
        }
    
    def log_summary(self) -> None:
        """Log summary of all tracked operations."""
        if not self.metrics:
            log.info("No performance metrics tracked")
            return
        
        log.info("=" * 60)
        log.info("Performance Summary")
        log.info("=" * 60)
        
        for operation in sorted(self.metrics.keys()):
            stats = self.get_stats(operation)
            log.info(
                f"{operation:30s} | "
                f"count: {stats['count']:3.0f} | "
                f"avg: {stats['avg']:6.2f}s | "
                f"min: {stats['min']:6.2f}s | "
                f"max: {stats['max']:6.2f}s | "
                f"total: {stats['total']:7.2f}s"
            )
        
        log.info("=" * 60)


# Global monitor instance
_monitor = PerformanceMonitor()


def get_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    return _monitor


@contextmanager
def track_performance(operation: str) -> Generator[None, None, None]:
    """Convenience function to track operation performance.
    
    Usage:
        with track_performance("embed_candidates"):
            # ... operation code ...
    """
    with _monitor.track(operation):
        yield


def log_performance_summary() -> None:
    """Log summary of all tracked operations."""
    _monitor.log_summary()
