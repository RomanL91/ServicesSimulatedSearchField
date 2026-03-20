from arq.connections import RedisSettings

from app.core.config import settings
from app.workers.tasks import sync_provider


class WorkerSettings:
    functions = [sync_provider]

    redis_settings = RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        database=settings.redis_database,
    )

    # Максимум одновременно выполняемых задач воркером
    max_jobs = 10

    # Таймаут одной задачи (секунды). Синхронизация большого файла может занять время.
    job_timeout = 3600

    # Хранить результат задачи 24 часа
    keep_result = 86400
