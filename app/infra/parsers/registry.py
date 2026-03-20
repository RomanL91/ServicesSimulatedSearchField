from app.infra.parsers.base import BaseXLSParser
from app.infra.parsers.elektrokabel import ElektrokabelParser
from app.infra.parsers.elkab_ural import ElkabUralParser

# Реестр парсеров: provider_name → класс парсера.
# Добавлять сюда при каждом новом провайдере.
PARSER_REGISTRY: dict[str, type[BaseXLSParser]] = {
    "ELKAB_URAL": ElkabUralParser,
    "ELEKTROKABEL": ElektrokabelParser,
}
