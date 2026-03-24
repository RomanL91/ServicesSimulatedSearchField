# Simulated Search Field

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Meilisearch-v1.12-FF5CAA?style=for-the-badge&logo=meilisearch&logoColor=white" alt="Meilisearch">
  <img src="https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis">
  <img src="https://img.shields.io/badge/ARQ-0.26-000000?style=for-the-badge" alt="ARQ">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/Poetry-2.x-60A5FA?style=for-the-badge&logo=poetry&logoColor=white" alt="Poetry">
</p>

<p align="center">
  Микросервис для агрегации прайс-листов поставщиков кабельной продукции,<br>
  полнотекстовой индексации в Meilisearch и единого поискового API.
</p>

---

## Навигация

- [Обзор](#обзор)
- [Архитектура](#архитектура)
- [Механика работы](#механика-работы)
  - [Пайплайн синхронизации](#пайплайн-синхронизации)
  - [Планировщик](#планировщик)
  - [Очередь задач ARQ](#очередь-задач-arq)
  - [Поиск](#поиск)
- [Структура проекта](#структура-проекта)
- [API](#api)
  - [Поиск](#post-apiv1search)
  - [Запуск синхронизации](#post-apiv1syncprovider_name)
  - [Статус задачи](#get-apiv1syncjobsjob_id)
  - [Список провайдеров](#get-apiv1sync)
- [Провайдеры](#провайдеры)
- [Конфигурация](#конфигурация)
- [Запуск](#запуск)
  - [Docker](#docker-рекомендуется)
  - [Локально](#локально)
- [Добавление провайдера](#добавление-провайдера)

---

## Обзор

Сервис решает задачу агрегации актуальных прайс-листов от нескольких поставщиков:

1. **Скачивает** XLS/XLSX-файлы с сайтов поставщиков по расписанию или по запросу
2. **Парсит** и нормализует данные (наименование, цена, единица измерения, НДС)
3. **Индексирует** в Meilisearch для мгновенного полнотекстового поиска
4. **Отдаёт** унифицированный поисковый API — один запрос покрывает всех поставщиков одновременно

---

## Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                        Docker Network                   │
│  ┌───────────────────┐        ┌────────────────────┐    │
│  │  simulated_search  │        │ simulated_search   │    │
│  │    _field_api      │        │   _field_worker    │    │
│  │                   │        │                    │    │
│  │  FastAPI :7899    │        │  ARQ Worker        │    │
│  │  APScheduler      │──ARQ──▶│  sync_provider()   │    │
│  └────────┬──────────┘        └────────┬───────────┘    │
│           │                            │                 │
│     REST API                    Download → Parse         │
│           │                            │                 │
│  ┌────────▼──────────────────────────▼───────────┐      │
│  │              metiz_network (external)          │      │
│  │   ┌─────────────────┐   ┌──────────────────┐  │      │
│  │   │   Meilisearch   │   │      Redis       │  │      │
│  │   │  :7700          │   │      :6379       │  │      │
│  │   └─────────────────┘   └──────────────────┘  │      │
│  └────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────┘
```

Сервис состоит из **двух контейнеров** на базе одного образа:

| Контейнер | Команда | Роль |
|-----------|---------|------|
| `simulated_search_field_api` | `uvicorn app.main:app` | REST API + планировщик APScheduler |
| `simulated_search_field_worker` | `arq app.workers.settings.WorkerSettings` | Фоновое выполнение задач синхронизации |

---

## Механика работы

### Пайплайн синхронизации

Каждая синхронизация проходит три этапа, реализованных как команды (Command Pattern):

```
POST /api/v1/sync/{provider}
        │
        ▼
[ARQ Queue] ──▶ sync_provider(ctx, provider_name)
                        │
                        ▼
              SyncProviderStrategy.execute()
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
   DownloadFile    ParseFile      IndexRaw
   Command        Command        Command
          │             │             │
          ▼             ▼             ▼
   HttpxDownloader  XLS Parser   MeilisearchIndexer
   (httpx async)   (pandas +     (batches of 1000,
                   xlrd/openpyxl  5 concurrent)
                   /calamine)
                        │
                        ▼
              list[Material]  ──▶  RAW_{PROVIDER_NAME}
                                   (Meilisearch index)
```

**Шаг 1 — Download**: `HttpxDownloader` делает async GET-запрос к URL провайдера (timeout 120s, follow_redirects=True), возвращает `bytes`.

**Шаг 2 — Parse**: Парсер читает XLS/XLSX через цепочку fallback-движков:
1. Нативный движок (xlrd для `.xls`, openpyxl для `.xlsx`)
2. Альтернативный нативный движок
3. python-calamine (Rust, справляется с битыми файлами)
4. HTML-парсер (файл маскируется под XLS, но является HTML — как у Элкаб-Урал)

Каждая строка превращается в `Material` с детерминированным `id = SHA256(provider:name)[:24]`. Цены нормализуются: если файл содержит цены **с НДС** — применяется `_reverse_vat()`, если **без НДС** — `_calculate_vat()`.

**Шаг 3 — Index**: `MeilisearchIndexer` загружает документы батчами по **1000** штук с параллелизмом до **5 потоков** (semaphore). Индекс `RAW_{PROVIDER_NAME}` создаётся автоматически, primary key = `id`.

---

### Планировщик

При старте API-контейнера `APScheduler` регистрирует interval-задачу для каждого провайдера из `providers/env.*`:

```python
scheduler.add_job(
    _enqueue_scheduled_sync,
    trigger="interval",
    minutes=provider.sync_period_minutes,  # по умолчанию 60 мин
    id=f"sync_{provider.provider_name}",
    max_instances=1,
    coalesce=True,                          # пропускает пропущенные запуски
)
```

Планировщик **не выполняет синхронизацию сам** — он только ставит задачу в ARQ-очередь Redis. Если задача уже висит в очереди или выполняется, новый enqueue вернёт `None` и запуск будет пропущен.

---

### Очередь задач ARQ

ARQ использует Redis как брокер. Job ID формируется как `sync_{PROVIDER_NAME}` — это гарантирует **идемпотентность**: одновременно может быть только одна задача синхронизации для каждого провайдера.

| Параметр | Значение |
|----------|----------|
| `max_jobs` | 10 одновременных задач |
| `job_timeout` | 3600 секунд (1 час) |
| `keep_result` | 86400 секунд (24 часа) |

Статусы задачи: `queued` → `in_progress` → `complete`.

---

### Поиск

`SearchMaterialsQuery` опрашивает индексы `RAW_{PROVIDER}` в Meilisearch **параллельно** через `asyncio.gather()`:

```
POST /api/v1/search  {"query": "кабель ввгнг", "limit": 20}
        │
        ▼
  Resolve providers  ──▶  [RAW_ELEKTROKABEL, RAW_ELKAB_URAL]
        │
        ├──▶ search(RAW_ELEKTROKABEL, "кабель ввгнг") ─┐
        │                                               ├──▶ merge & sort by _rankingScore
        └──▶ search(RAW_ELKAB_URAL, "кабель ввгнг")   ─┘
                                                         │
                                                         ▼
                                                   top N results
```

Результаты мерджатся, сортируются по `_rankingScore` Meilisearch и обрезаются до `limit`.

---

## Структура проекта

```
ServicesSimulatedSearchField/
├── app/
│   ├── main.py                          # Точка входа FastAPI + APScheduler lifespan
│   ├── api/
│   │   ├── v1/
│   │   │   ├── router.py               # Подключение всех роутеров v1
│   │   │   └── endpoints/
│   │   │       ├── search.py           # POST /api/v1/search
│   │   │       └── sync.py             # POST/GET /api/v1/sync/*
│   │   ├── schemas/
│   │   │   ├── search.py               # SearchRequest, SearchResponse, MaterialResult
│   │   │   └── sync.py                 # SyncJobResponse, JobStatusResponse, ProvidersResponse
│   │   └── dependencies/
│   │       ├── commands.py             # DI для sync-стратегии
│   │       └── queries.py              # DI для search-хендлера
│   ├── core/
│   │   ├── config.py                   # AppSettings + ProviderSettings (pydantic-settings)
│   │   ├── logging.py                  # Настройка логирования
│   │   └── interfaces/
│   │       ├── downloader.py           # AbstractDownloader
│   │       ├── parser.py               # AbstractParser
│   │       └── indexer.py              # AbstractIndexer
│   ├── domain/
│   │   ├── material.py                 # Доменная модель Material (dataclass)
│   │   ├── provider.py                 # ProviderInfo (dataclass)
│   │   └── strategies/
│   │       ├── base.py                 # BaseStrategy ABC
│   │       └── sync_provider.py        # SyncProviderStrategy (оркестратор)
│   ├── commands/
│   │   ├── base.py                     # BaseCommand ABC
│   │   └── sync/
│   │       ├── download_file.py        # DownloadFileCommand
│   │       ├── parse_file.py           # ParseFileCommand
│   │       └── index_raw.py            # IndexRawCommand
│   ├── infra/
│   │   ├── downloader.py               # HttpxDownloader
│   │   ├── meilisearch.py              # MeilisearchIndexer
│   │   ├── arq_pool.py                 # Управление ARQ-пулом
│   │   ├── strategy_factory.py         # SyncStrategyFactory (сборка зависимостей)
│   │   └── parsers/
│   │       ├── base.py                 # BaseXLSParser (pandas + fallback-цепочка)
│   │       ├── elektrokabel.py         # Парсер Электрокабель
│   │       ├── elkab_ural.py           # Парсер Элкаб-Урал
│   │       └── registry.py             # PARSER_REGISTRY {name → class}
│   ├── queries/
│   │   └── search/
│   │       └── search_materials.py     # SearchMaterialsQuery (CQRS read-side)
│   └── workers/
│       ├── settings.py                 # WorkerSettings (ARQ конфиг)
│       └── tasks.py                    # sync_provider() — ARQ task function
├── providers/
│   ├── env.elektrokabel                # Конфиг провайдера Электрокабель
│   └── env.elkab_ural                  # Конфиг провайдера Элкаб-Урал
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── pyproject.toml
```

---

## API

Документация Swagger доступна по адресу: `http://localhost:7899/docs`

### `POST /api/v1/search`

Полнотекстовый поиск по всем (или выбранным) провайдерам одновременно.

**Request body:**
```json
{
  "query": "кабель ввгнг 3х2.5",
  "limit": 10,
  "providers": ["ELEKTROKABEL"]
}
```

| Поле | Тип | По умолчанию | Описание |
|------|-----|-------------|----------|
| `query` | `string` | — | Поисковый запрос |
| `limit` | `int` | `10` | Количество результатов (1–100) |
| `providers` | `list[string] \| null` | `null` | Фильтр по провайдерам. `null` = все |

**Response `200`:**
```json
{
  "query": "кабель ввгнг 3х2.5",
  "total": 42,
  "providers_searched": ["ELEKTROKABEL", "ELKAB_URAL"],
  "results": [
    {
      "id": "a3f1c9b2e8d4...",
      "name": "Кабель ВВГнг(А)-LS 3х2,5",
      "price": 83.25,
      "price_with_vat": 99.90,
      "vat_rate": 20,
      "vat_amount": 16.65,
      "currency": "RUR",
      "unit": "м",
      "is_active": true,
      "provider": "ELEKTROKABEL",
      "supplier_full_name": "Группа компаний Электрокабель",
      "supplier_short_name": "ООО ГК Электрокабель",
      "supplier_inn": "7733814660",
      "url": "https://elektrokable.ru/...",
      "ranking_score": 0.9873
    }
  ]
}
```

---

### `POST /api/v1/sync/{provider_name}`

Постановка задачи синхронизации в очередь. Возвращает `202 Accepted` немедленно.

```http
POST /api/v1/sync/ELEKTROKABEL
```

**Response `202`:**
```json
{
  "provider": "ELEKTROKABEL",
  "job_id": "sync_ELEKTROKABEL",
  "status": "queued"
}
```

**Response `409`** — синхронизация уже выполняется или стоит в очереди.

---

### `GET /api/v1/sync/jobs/{job_id}`

Проверка статуса задачи.

```http
GET /api/v1/sync/jobs/sync_ELEKTROKABEL
```

**Response `200`:**
```json
{
  "job_id": "sync_ELEKTROKABEL",
  "status": "in_progress"
}
```

Возможные статусы: `queued` | `in_progress` | `complete` | `deferred` | `not_found`

---

### `GET /api/v1/sync/`

Список всех зарегистрированных провайдеров.

**Response `200`:**
```json
{
  "providers": ["ELEKTROKABEL", "ELKAB_URAL"]
}
```

---

## Провайдеры

Каждый провайдер описывается файлом `providers/env.<name>`:

```ini
# providers/env.elektrokabel
PROVIDER_NAME=ELEKTROKABEL
PROVIDER_URL=https://elektrokabel.ru/Prais_kabel/Prais-list_kabel.xls
SUPPLIER_FULL_NAME=Группа компаний Электрокабель
SUPPLIER_SHORT_NAME=ООО ГК Электрокабель
SUPPLIER_INN=7733814660
SYNC_PERIOD_MINUTES=60
CURRENCY=RUR
VAT_RATE=20
```

| Параметр | Описание |
|----------|----------|
| `PROVIDER_NAME` | Уникальный идентификатор (используется как имя индекса `RAW_{NAME}`) |
| `PROVIDER_URL` | URL XLS/XLSX-файла для скачивания |
| `SUPPLIER_FULL_NAME` | Полное наименование поставщика |
| `SUPPLIER_SHORT_NAME` | Краткое наименование |
| `SUPPLIER_INN` | ИНН поставщика |
| `SYNC_PERIOD_MINUTES` | Интервал автосинхронизации в минутах (по умолчанию: 60) |
| `CURRENCY` | Валюта (по умолчанию: `RUR`) |
| `VAT_RATE` | Ставка НДС в процентах (по умолчанию: 20) |

### Текущие провайдеры

| Провайдер | Поставщик | Формат файла | Особенности |
|-----------|-----------|-------------|-------------|
| `ELEKTROKABEL` | ООО ГК Электрокабель (ИНН 7733814660) | `.xls` (xlrd) | Цены **с НДС**, числа формата `62 164,92` |
| `ELKAB_URAL` | ООО Элкаб-Урал | `.xls` (HTML внутри) | Цены **без НДС**, файл — HTML с расширением XLS, двухколоночная таблица |

---

## Конфигурация

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `MEILI_URL` | `http://meilisearch:7700` | URL Meilisearch |
| `MEILI_MASTER_KEY` | `YOUR_MASTER_KEY` | Мастер-ключ Meilisearch |
| `REDIS_HOST` | `redis` | Хост Redis |
| `REDIS_PORT` | `6379` | Порт Redis |
| `REDIS_PASSWORD` | _(пусто)_ | Пароль Redis (опционально) |
| `REDIS_DATABASE` | `0` | Номер базы данных Redis |
| `LOG_LEVEL` | `INFO` | Уровень логирования (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

> **Важно:** `MEILI_URL` и `REDIS_HOST` должны указывать на имена контейнеров внутри `metiz_network`, а не на `localhost`.

---

## Запуск

### Docker (рекомендуется)

Сервис подключается к внешней сети `metiz_network`, в которой уже запущены Meilisearch и Redis.

**1. Убедитесь, что сеть существует:**
```bash
docker network ls | grep metiz_network
# если нет:
docker network create metiz_network
```

**2. Подготовьте `.env`:**
```bash
cp .env.example .env
# Отредактируйте MEILI_MASTER_KEY и при необходимости REDIS_PASSWORD
```

**3. Запустите сервисы:**
```bash
docker compose up --build -d
```

**4. Проверьте статус:**
```bash
docker compose ps
docker compose logs -f
```

**5. Откройте Swagger UI:**
```
http://localhost:7899/docs
```

**Остановка:**
```bash
docker compose down
```

---

### Локально

**Требования:** Python 3.11+, Poetry, запущенные Redis и Meilisearch.

**1. Установите зависимости:**
```bash
poetry install
```

**2. Создайте `.env`:**
```bash
cp .env.example .env
# Для локального запуска:
# MEILI_URL=http://localhost:7700
# REDIS_HOST=localhost
```

**3. Запустите API:**
```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 7899 --reload
```

**4. Запустите воркер (в отдельном терминале):**
```bash
poetry run arq app.workers.settings.WorkerSettings
```

---

## Добавление провайдера

Для подключения нового поставщика достаточно двух шагов:

**1. Создайте конфиг-файл** `providers/env.<name>`:
```ini
PROVIDER_NAME=NEW_PROVIDER
PROVIDER_URL=https://example.com/price.xlsx
SUPPLIER_FULL_NAME=ООО Новый Поставщик
SUPPLIER_SHORT_NAME=ООО НП
SUPPLIER_INN=1234567890
SYNC_PERIOD_MINUTES=120
CURRENCY=RUR
VAT_RATE=20
```

**2. Реализуйте парсер** `app/infra/parsers/new_provider.py`:
```python
from app.infra.parsers.base import BaseXLSParser
from app.domain.material import Material

class NewProviderParser(BaseXLSParser):
    HEADER_ROW = 0  # номер строки с заголовками

    _COL_NAME = "Наименование"
    _COL_PRICE = "Цена"
    _COL_UNIT = "Ед. изм."

    def _build_material(self, row, ...) -> Material | None:
        # маппинг колонок → Material
        ...
```

**3. Зарегистрируйте парсер** в `app/infra/parsers/registry.py`:
```python
PARSER_REGISTRY: dict[str, type[BaseXLSParser]] = {
    "ELKAB_URAL": ElkabUralParser,
    "ELEKTROKABEL": ElektrokabelParser,
    "NEW_PROVIDER": NewProviderParser,   # добавить
}
```

После перезапуска сервиса новый провайдер автоматически появится в расписании синхронизации и станет доступен через API.
