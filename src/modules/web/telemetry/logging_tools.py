import logging

from typing_extensions import ParamSpec

P = ParamSpec("P")


class ReplicaIDFilter(logging.Filter):
    """
    Фильтр, который будет добавлять в логи UUID сгенеророванный при инициализации.

    Это позволит в логах различать логи разных реплик одного и того же сервиса.
    """

    def __init__(self, replica_uid: str) -> None:
        """Конструктор класса."""
        self._replica_uid = replica_uid

    def filter(self, record: logging.LogRecord) -> bool:
        record.replica_uid = self._replica_uid
        return True


class ServiceNameFilter(logging.Filter):
    """Фильтр, который добавит в логи наименование сервиса."""

    def __init__(self, service_name: str) -> None:
        """Конструктор класса."""
        self.service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.service_name = self.service_name
        return True


class SegmentUIDFilter(logging.Filter):
    """Фильтр, который добавит в логи uid сегмента."""

    def __init__(self, segment_uid: str) -> None:
        """Конструктор класса."""
        self.segment_uid = segment_uid

    def filter(self, record: logging.LogRecord) -> bool:
        record.segment_uid = self.segment_uid
        return True


class TraceIDFilter(logging.Filter):
    """Фильтр, который добавит в логи ID трассировки"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = None
        return True
