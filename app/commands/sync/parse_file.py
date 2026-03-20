from app.commands.base import BaseCommand
from app.core.interfaces.parser import AbstractParser
from app.domain.material import Material


class ParseFileCommand(BaseCommand):
    def __init__(
        self,
        parser: AbstractParser,
        file_bytes: bytes,
        file_ext: str,
    ) -> None:
        self._parser = parser
        self._file_bytes = file_bytes
        self._file_ext = file_ext

    async def execute(self) -> list[Material]:
        return await self._parser.parse(self._file_bytes, self._file_ext)
