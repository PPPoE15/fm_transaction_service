import dramatiq


@dramatiq.actor()
def echo_msg_task(msg: str) -> None:
    ...


class TasksRMQInterface:
    def add_echo_msg_task(self, message: str) -> None:
        ...


class TasksRMQAdapter(TasksRMQInterface):
    def __init__(self) -> None:
        pass

    def add_echo_msg_task(self, message: str) -> None:
        echo_msg_task.send(message)
