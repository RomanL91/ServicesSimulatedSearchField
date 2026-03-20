from arq.jobs import Job, JobStatus
from fastapi import APIRouter, HTTPException

from app.api.dependencies.commands import get_available_providers, validate_provider
from app.api.schemas.sync import JobStatusResponse, ProvidersResponse, SyncJobResponse
from app.infra.arq_pool import get_pool

router = APIRouter(prefix="/sync", tags=["sync"])

_ACTIVE_STATUSES = {JobStatus.queued, JobStatus.in_progress, JobStatus.deferred}

# ARQ хранит результат завершённой задачи под этим ключом.
# Удаляем его чтобы разрешить повторный запуск с тем же _job_id.
_ARQ_RESULT_KEY = "arq:result:{job_id}"


@router.post("/{provider_name}", response_model=SyncJobResponse, status_code=202)
async def trigger_sync(provider_name: str) -> SyncJobResponse:
    """Поставить синхронизацию провайдера в очередь. Возвращает job_id мгновенно."""
    validate_provider(provider_name)

    pool = get_pool()
    job_id = f"sync_{provider_name.upper()}"

    existing = Job(job_id, pool)
    status = await existing.status()

    if status in _ACTIVE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Sync for '{provider_name.upper()}' is already {status.value}",
        )

    # Задача завершена или не найдена — удаляем старый результат из Redis,
    # чтобы ARQ позволил создать новую задачу с тем же job_id.
    await pool.delete(_ARQ_RESULT_KEY.format(job_id=job_id))

    job = await pool.enqueue_job(
        "sync_provider",
        provider_name.upper(),
        _job_id=job_id,
    )

    if job is None:
        # Race condition: кто-то успел поставить задачу между нашей проверкой и enqueue
        raise HTTPException(
            status_code=409,
            detail=f"Sync for '{provider_name.upper()}' is already queued or running",
        )

    return SyncJobResponse(provider=provider_name.upper(), job_id=job.job_id)


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Статус задачи синхронизации."""
    pool = get_pool()
    job = Job(job_id, pool)
    status = await job.status()
    return JobStatusResponse(job_id=job_id, status=status.value)


@router.get("/", response_model=ProvidersResponse)
async def list_providers() -> ProvidersResponse:
    """Список зарегистрированных провайдеров."""
    return ProvidersResponse(providers=get_available_providers())
