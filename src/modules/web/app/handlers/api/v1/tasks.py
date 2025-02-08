from fastapi import APIRouter

from modules.web.app.application.services.v1.add_task_handler import AddEchoMsgTaskHandler
from modules.web.app.infrastructure.rmq.adapters.v1.tasks_adapter import TasksRMQAdapter

tasks_router = APIRouter(tags=["Tasks"], prefix="/api/v1/tasks")


def build_echo_msg_handler() -> AddEchoMsgTaskHandler:
    """Simple docs"""
    return AddEchoMsgTaskHandler(
        tasks_rmq_adapter=TasksRMQAdapter(),
    )


@tasks_router.post("/task")
async def add_echo_msg_task(msg: str) -> None:
    """
    Add a task

    Args:
        msg: The message to add
    """
    handler = build_echo_msg_handler()
    await handler.handle(msg)
