from app.commands.base import BaseCommand
from app.core.interfaces.downloader import AbstractDownloader


class DownloadFileCommand(BaseCommand):
    def __init__(self, downloader: AbstractDownloader, url: str) -> None:
        self._downloader = downloader
        self._url = url

    async def execute(self) -> bytes:
        return await self._downloader.download(self._url)
