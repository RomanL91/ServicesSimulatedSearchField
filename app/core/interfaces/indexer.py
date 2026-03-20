from abc import ABC, abstractmethod

from app.domain.material import Material


class AbstractIndexer(ABC):
    @abstractmethod
    async def index(self, materials: list[Material], index_name: str) -> None:
        ...
