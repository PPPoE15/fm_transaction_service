from fastapi import APIRouter

from apps.web.modules.category.endpoints import router as category_router
from apps.web.modules.transaction.endpoints import router as transaction_router

main_router = APIRouter()

main_router.include_router(category_router)
main_router.include_router(transaction_router)
