"""Abstract LLM client interface."""
import abc
import logging
from typing import Type, TypeVar

from pydantic import BaseModel

log = logging.getLogger("processor.llm.base")

T = TypeVar("T", bound=BaseModel)


class LLMClient(abc.ABC):
    """Interface for text generation. Implementations may call cloud or local APIs."""

    @abc.abstractmethod
    def generate(self, system: str, user: str, output_model: Type[T]) -> T:
        """Generate structured output that conforms to the given Pydantic model."""
        ...
