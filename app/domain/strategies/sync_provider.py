from app.commands.sync.download_file import DownloadFileCommand
from app.commands.sync.index_raw import IndexRawCommand
from app.commands.sync.parse_file import ParseFileCommand
from app.core.interfaces.downloader import AbstractDownloader
from app.core.interfaces.indexer import AbstractIndexer
from app.core.interfaces.parser import AbstractParser
from app.domain.provider import ProviderInfo
from app.domain.strategies.base import BaseStrategy


def _get_file_ext(url: str) -> str:
    return url.rsplit(".", 1)[-1].lower().split("?")[0]


class SyncProviderStrategy(BaseStrategy):
    def __init__(
        self,
        downloader: AbstractDownloader,
        parser: AbstractParser,
        indexer: AbstractIndexer,
        provider: ProviderInfo,
    ) -> None:
        self._downloader = downloader
        self._parser = parser
        self._indexer = indexer
        self._provider = provider

    async def execute(self) -> None:
        file_bytes = await DownloadFileCommand(
            downloader=self._downloader,
            url=self._provider.url,
        ).execute()

        file_ext = _get_file_ext(self._provider.url)

        materials = await ParseFileCommand(
            parser=self._parser,
            file_bytes=file_bytes,
            file_ext=file_ext,
        ).execute()

        await IndexRawCommand(
            indexer=self._indexer,
            materials=materials,
            index_name=self._provider.raw_index_name,
        ).execute()
