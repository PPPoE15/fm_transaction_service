from fastapi import APIRouter

from .endpoints import router as planned_router
from .errors import setup_exception_handlers
from .regular import router as regular_router

router = APIRouter()
router.include_router(planned_router)
router.include_router(regular_router)

__all__ = ["router", "setup_exception_handlers"]
