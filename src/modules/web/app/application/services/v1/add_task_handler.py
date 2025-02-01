from modules.web.app.infrastructure.rmq.adapters.v1.tasks_adapter import TasksRMQInterface


class AddEchoMsgTaskHandler:
    def __init__(self, tasks_rmq_adapter: TasksRMQInterface):
        self._tasks_rmq_adapter = tasks_rmq_adapter

    async def handle(self, message: str) -> None:
        self._tasks_rmq_adapter.add_echo_msg_task(message)
