from typing import Annotated

from pydantic import UUID4

UserUID = Annotated[UUID4, ...]
CategoryUID = Annotated[UUID4, ...]
IncomeUID = Annotated[UUID4, ...]
OutcomeUID = Annotated[UUID4, ...]
UserName = Annotated[str, ...]
Email = Annotated[str, ...]
CategoryName = Annotated[str, ...]
MoneySum = Annotated[int, ...]
Description = Annotated[str | None, ...]
