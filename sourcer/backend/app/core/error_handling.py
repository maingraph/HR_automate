"""Unified error handling decorators for consistent error management across the codebase.

This module provides decorators for:
- Graceful degradation with fallback values
- Retry logic with exponential backoff
- Consistent logging of exceptions
"""
from __future__ import annotations

import functools
from typing import Any, Callable, TypeVar

from tenacity import retry, stop_after_attempt, wait_exponential, RetryCallState

from app.core.logging import get_logger

T = TypeVar("T")


def with_fallback(
    fallback_value: T,
    log_message: str = "Operation failed",
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for graceful degradation with logging.
    
    Catches all exceptions, logs them with full traceback, and returns fallback value.
    Use this when operation failure should not stop the entire pipeline.
    
    Args:
        fallback_value: Value to return if function raises exception
        log_message: Custom message to log (exception details appended automatically)
        
    Returns:
        Decorated function that never raises, always returns T
        
    Example:
        >>> @with_fallback(fallback_value=[], log_message="Telegram scrape failed")
        ... def scrape_telegram(channels: list[str]) -> list[dict]:
        ...     return scrape_channels(channels)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            log = get_logger(func.__module__)
            try:
                return func(*args, **kwargs)
            except Exception as e:  # noqa: BLE001
                log.exception(f"{log_message}: {e}")
                return fallback_value
        return wrapper
    return decorator


def with_retry(
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 30.0,
    before_sleep: Callable[[RetryCallState], None] | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retry with exponential backoff.
    
    Retries function on any exception with exponential backoff.
    Use this for operations that may fail transiently (API calls, network requests).
    
    Args:
        max_attempts: Maximum number of attempts before giving up
        min_wait: Minimum wait time between retries (seconds)
        max_wait: Maximum wait time between retries (seconds)
        before_sleep: Optional callback before each retry sleep
        
    Returns:
        Decorated function with retry logic
        
    Example:
        >>> @with_retry(max_attempts=5, min_wait=2, max_wait=60)
        ... def call_external_api() -> dict:
        ...     return requests.get("https://api.example.com").json()
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(min=min_wait, max=max_wait),
        before_sleep=before_sleep,
        reraise=True,
    )


def log_errors(
    log_message: str = "Error in function",
    reraise: bool = True,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to log exceptions without suppressing them.
    
    Logs exception with full traceback, then optionally re-raises.
    Use this when you want visibility into errors but still want them to propagate.
    
    Args:
        log_message: Custom message to log
        reraise: Whether to re-raise exception after logging (default: True)
        
    Returns:
        Decorated function that logs exceptions
        
    Example:
        >>> @log_errors(log_message="Failed to process candidate", reraise=True)
        ... def process_candidate(candidate: dict) -> dict:
        ...     return transform(candidate)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            log = get_logger(func.__module__)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log.exception(f"{log_message}: {e}")
                if reraise:
                    raise
                return None  # type: ignore
        return wrapper
    return decorator
