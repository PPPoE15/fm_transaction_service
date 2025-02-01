from typing import Dict

from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def demo() -> Dict[str, str]:
    """Демонстрационный эндпойнт"""
    return {"ping": "pong"}
