from app.commands.base import BaseCommand
from app.core.interfaces.indexer import AbstractIndexer
from app.domain.material import Material


class IndexRawCommand(BaseCommand):
    def __init__(
        self,
        indexer: AbstractIndexer,
        materials: list[Material],
        index_name: str,
    ) -> None:
        self._indexer = indexer
        self._materials = materials
        self._index_name = index_name

    async def execute(self) -> None:
        await self._indexer.index(self._materials, self._index_name)
