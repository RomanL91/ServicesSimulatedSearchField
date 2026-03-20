# Инструкции для Claude

## Общие принципы

- Весь код — **асинхронный** (`async/await`). Никакого синхронного I/O.
- Следуем **SOLID**, **ООП паттернам** и **лучшим практикам**.
- Архитектура проекта — согласно `fastapi_architecture_template.md` (CQRS + Strategy + Command + UoW + Repository).

## Стек

- **Python 3.11+**
- **FastAPI** + **uvicorn**
- **httpx** — асинхронный HTTP-клиент
- **meilisearch-python-sdk** — клиент Meilisearch (async)

## Архитектурные правила (кратко)

```
api → commands, queries, schemas, domain
commands → core/interfaces, domain
queries → infra/database, schemas
domain → ничего (чистый Python)
core → ничего
infra → core, domain
```

- `core/` — конфигурация, безопасность, абстрактные интерфейсы (ABC). Самый стабильный слой.
- `domain/` — бизнес-сущности (датаклассы) и бизнес-стратегии. Без внешних зависимостей.
- `commands/` — атомарные write-операции (DB → commit → broker/tasks).
- `queries/` — read-сторона CQRS, прямо в Pydantic-схему, без UoW.
- `infra/` — реализации интерфейсов (SQLAlchemy, Redis, брокер, репозитории).
- `api/` — тонкий HTTP-слой. Только валидация и роутинг.

## Порядок команд в стратегии

```python
async with uow:
    # DB-команды
    await uow.commit()

# Broker-команды (после commit!)
# Task-команды (после commit!)
```

## Чего не делать

- Не смешивать бизнес-логику в `api/`-слое.
- Не выпускать ORM-модели за пределы `infra/`.
- Не делать синхронные вызовы в async-коде.
- Не добавлять избыточные абстракции без необходимости.
