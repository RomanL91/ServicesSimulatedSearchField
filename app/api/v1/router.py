from fastapi import APIRouter

from app.api.v1.endpoints.sync import router as sync_router

router = APIRouter(prefix="/api/v1")
router.include_router(sync_router)
