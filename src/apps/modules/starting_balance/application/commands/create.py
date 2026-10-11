from datetime import date

from apps.modules.starting_balance.application.exceptions import StartingBalanceAlreadyExistsError
from apps.modules.starting_balance.application.uow import AbstractStartingBalanceUnitOfWork
from apps.modules.starting_balance.domain import StartingBalance
from apps.shared import apps_types


class CreateStartingBalanceCommandHandler:
    """Класс обработчика команды задания стартового остатка."""

    def __init__(
        self,
        unit_of_work: AbstractStartingBalanceUnitOfWork,
    ) -> None:
        """
        Конструктор обработчика команды задания стартового остатка.

        Args:
            unit_of_work: Объект шаблона Единица работы.
        """
        self._uow = unit_of_work

    async def handle(
        self,
        user_uid: apps_types.UserUID,
        amount: int,
        balance_date: date | None,
        today: date,
    ) -> StartingBalance:
        """
        Задать стартовый остаток пользователя. Задаётся один раз, транзакцию не создаёт.

        Args:
            user_uid: UID пользователя.
            amount: Сумма в целых рублях.
            balance_date: День, на конец которого задан остаток; не передан — вчера.
            today: Текущая дата.

        Raises:
            InvalidBalanceDateError: Если дата вне 2000–2099 годов или позже сегодняшнего дня.
            StartingBalanceAlreadyExistsError: Если остаток у пользователя уже задан.
        """
        starting_balance = StartingBalance.create(
            user_uid=user_uid,
            amount=amount,
            balance_date=balance_date,
            today=today,
        )
        async with self._uow as uow:
            if await uow.starting_balances_repo.get_by_user_uid(user_uid) is not None:
                raise StartingBalanceAlreadyExistsError
            await uow.starting_balances_repo.create(starting_balance)
            await uow.commit()
        return starting_balance
