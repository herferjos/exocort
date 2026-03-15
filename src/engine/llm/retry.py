"""Generic retry wrapper for LLM generate calls."""
import logging
import time
from typing import Callable, Type, TypeVar

from . import base

log = logging.getLogger("processor.llm.retry")

T = TypeVar("T")


def _is_retriable(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "503" in msg or "500" in msg


def with_retry(
    fn: Callable[[], T],
    max_retries: int = 3,
    is_retriable: Callable[[BaseException], bool] = _is_retriable,
) -> T:
    """Run fn(); on retriable exception, wait and retry up to max_retries times."""
    last: BaseException | None = None
    for attempt in range(max_retries):
        try:
            return fn()
        except BaseException as e:
            last = e
            if attempt < max_retries - 1 and is_retriable(e):
                delay = 2**attempt
                log.warning("LLM call failed, retrying in %ds: %s", delay, e)
                time.sleep(delay)
                continue
            raise
    if last is not None:
        raise last
    raise RuntimeError("Max retries exceeded")


class RetryingLLMClient(base.LLMClient):
    """Wraps an LLMClient and retries generate() on 429/503/500."""

    def __init__(self, client: base.LLMClient, max_retries: int = 3):
        self._client = client
        self._max_retries = max_retries

    def generate(self, system: str, user: str, output_model: Type[base.T]) -> base.T:
        def do() -> base.T:
            return self._client.generate(system, user, output_model)

        return with_retry(do, max_retries=self._max_retries)
