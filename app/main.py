from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.config import load_all_providers
from app.core.logging import get_logger, setup_logging
from app.infra.arq_pool import close_pool, get_pool, init_pool

setup_logging()
logger = get_logger(__name__)


async def _enqueue_scheduled_sync(provider_name: str) -> None:
    """Запускается планировщиком — ставит задачу в ARQ-очередь."""
    pool = get_pool()
    job = await pool.enqueue_job(
        "sync_provider",
        provider_name,
        _job_id=f"sync_{provider_name}",
    )
    if job is None:
        logger.info("Scheduled sync skipped (already queued/running): %s", provider_name)
    else:
        logger.info("Scheduled sync enqueued: %s — job_id=%s", provider_name, job.job_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    logger.info("ARQ pool initialized")

    scheduler = AsyncIOScheduler()
    for provider in load_all_providers():
        scheduler.add_job(
            _enqueue_scheduled_sync,
            trigger="interval",
            minutes=provider.sync_period_minutes,
            args=[provider.provider_name],
            id=f"sync_{provider.provider_name}",
            max_instances=1,
            coalesce=True,
        )
        logger.info(
            "Scheduled sync for '%s' every %d min",
            provider.provider_name,
            provider.sync_period_minutes,
        )

    scheduler.start()
    logger.info("Scheduler started with %d job(s)", len(scheduler.get_jobs()))

    yield

    scheduler.shutdown()
    await close_pool()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Simulated Search Field — Provider Sync",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(v1_router)
