from fastapi import APIRouter

from apps.web.app.handlers.api.v1.transaction.endpoints import router as user_router

# from modules.web.app.handlers.api.v1.tasks import tasks_router

# Import your API handler router
# from apps.web.src.app.handlers.api...router import router

main_router = APIRouter()

# Include API handler router to FastAPI app
# main_router.include_router(tasks_router)
main_router.include_router(user_router)
