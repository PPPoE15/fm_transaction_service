from fastapi import APIRouter

from .batch_endpoints import router as batch_router
from .endpoints import router as single_router

router = APIRouter()
router.include_router(batch_router)
router.include_router(single_router)

__all__ = ["router"]
