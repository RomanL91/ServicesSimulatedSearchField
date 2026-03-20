from abc import ABC, abstractmethod
from typing import Any


class BaseCommand(ABC):
    @abstractmethod
    async def execute(self) -> Any:
        ...
