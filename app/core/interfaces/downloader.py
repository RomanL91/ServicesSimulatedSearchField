from abc import ABC, abstractmethod


class AbstractDownloader(ABC):
    @abstractmethod
    async def download(self, url: str) -> bytes:
        ...
