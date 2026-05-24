"""Decorators for retry mechanics and other universal control flows."""

import time
from functools import wraps
from typing import Callable, TypeVar, Any

from src.utils.logging import logger

T = TypeVar('T')


def retry(
    max_attempts: int = 3,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Decorator to retry a function with exponential backoff on specified exceptions."""
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        sleep_time = backoff_factor ** attempt
                        logger.log(
                            f"Fallo en {func.__name__}: {e}. Reintentando en {sleep_time:.1f}s "
                            f"(intento {attempt + 1}/{max_attempts})...",
                            "WARNING"
                        )
                        time.sleep(sleep_time)
                        continue
                    # Re-raise the exception on the final attempt
                    raise
            if last_exception:
                raise last_exception
        return wrapper
    return decorator
