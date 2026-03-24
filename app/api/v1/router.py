from fastapi import APIRouter

from app.api.v1.endpoints.search import router as search_router
from app.api.v1.endpoints.sync import router as sync_router

router = APIRouter(prefix="/api/v1")
router.include_router(sync_router)
router.include_router(search_router)
