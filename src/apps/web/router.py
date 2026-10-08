from fastapi import APIRouter

from apps.modules.category.api import router as category_router
from apps.modules.transaction.api import router as transaction_router

main_router = APIRouter()

main_router.include_router(category_router)
main_router.include_router(transaction_router)
