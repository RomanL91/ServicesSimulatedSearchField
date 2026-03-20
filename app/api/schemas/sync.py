from pydantic import BaseModel


class SyncJobResponse(BaseModel):
    provider: str
    job_id: str
    status: str = "queued"


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # queued | in_progress | complete | not_found | deferred


class ProvidersResponse(BaseModel):
    providers: list[str]
