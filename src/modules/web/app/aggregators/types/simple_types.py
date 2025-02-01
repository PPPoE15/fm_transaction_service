from pydantic import UUID4
from typing_extensions import Annotated

TestUID = Annotated[UUID4, ...]
