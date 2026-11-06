"""Частичное удаление с единой фиксацией допустимых элементов."""

from apps.modules.transaction.application.batch_models import DeleteFailure, DeleteItem, DeleteSuccess
from apps.modules.transaction.application.uow import AbstractTransactionUnitOfWork
from apps.shared import apps_types


class BatchDeleteCommandHandler:
    """Удалить доступные актуальные операции, пропустив ожидаемые ошибки строк."""

    def __init__(self, unit_of_work: AbstractTransactionUnitOfWork) -> None:
        """Сохранить единицу работы для проверок и удалений."""
        self._uow = unit_of_work

    async def handle(
        self, user_uid: apps_types.UserUID, items: list[DeleteItem]
    ) -> list[DeleteSuccess | DeleteFailure]:
        """Вернуть один результат на строку; неожиданный сбой откатывает весь запрос."""
        async with self._uow as uow:
            transactions = {}
            for item in sorted(items, key=lambda item: item.uid):
                transactions[item.uid] = await uow.transactions_repo.get_by_uid_for_update(item.uid)
            results: list[DeleteSuccess | DeleteFailure] = []
            for index, item in enumerate(items):
                transaction = transactions[item.uid]
                if transaction is None or not transaction.belongs_to(user_uid):
                    results.append(
                        DeleteFailure(
                            index=index, uid=item.uid, status=404, code="FM-404000", message="Операция не найдена"
                        )
                    )
                elif transaction.version != item.expected_version:
                    results.append(
                        DeleteFailure(
                            index=index,
                            uid=item.uid,
                            status=409,
                            code="FM-409204",
                            message="Версия операции изменилась",
                        )
                    )
                else:
                    await uow.transactions_repo.delete(item.uid)
                    results.append(DeleteSuccess(index=index, uid=item.uid))
            await uow.commit()
        return results
