from abc import ABC, abstractmethod

from app.domain.material import Material


class AbstractParser(ABC):
    @abstractmethod
    async def parse(self, file_bytes: bytes, file_ext: str) -> list[Material]:
        ...
