from typing import Annotated

from pydantic import UUID4

UserUID = Annotated[UUID4, ...]
CategoryUID = Annotated[UUID4, ...]
TransactionUID = Annotated[UUID4, ...]
UserName = Annotated[str, ...]
Email = Annotated[str, ...]
CategoryName = Annotated[str, ...]
MoneySum = Annotated[int, ...]
# Агрегат по многим операциям (итог, среднее) — может превышать лимит одной суммы и int32.
MoneyTotal = Annotated[int, ...]
Description = Annotated[str | None, ...]
