from abc import ABC, abstractmethod
from typing import Any


class BaseQuery(ABC):
    @abstractmethod
    async def handle(self, *args: Any, **kwargs: Any) -> Any:
        ...
