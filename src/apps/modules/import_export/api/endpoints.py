from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from apps.modules.import_export.domain.models import FileFormat, TransactionKind
from apps.modules.import_export.infrastructure.templates import CSV_MEDIA_TYPE, XLSX_MEDIA_TYPE, generate_template
from apps.web.security import get_user_info

router = APIRouter(prefix="/import-export", tags=["Импорт"], dependencies=[Depends(get_user_info)])


@router.get("/templates/{transaction_type}", response_class=Response)
def download_template(
    transaction_type: TransactionKind, file_format: Annotated[FileFormat, Query(alias="format")]
) -> Response:
    """Скачать шаблон расходов или доходов в явно выбранном формате."""
    return Response(
        content=generate_template(transaction_type, file_format),
        media_type=CSV_MEDIA_TYPE if file_format == "csv" else XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{transaction_type}-template.{file_format}"'},
    )
