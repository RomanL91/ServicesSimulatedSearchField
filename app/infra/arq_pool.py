from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings

_pool: ArqRedis | None = None


def _redis_settings() -> RedisSettings:
    return RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        database=settings.redis_database,
    )


async def init_pool() -> ArqRedis:
    global _pool
    _pool = await create_pool(_redis_settings())
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> ArqRedis:
    if _pool is None:
        raise RuntimeError("ARQ pool is not initialized")
    return _pool
