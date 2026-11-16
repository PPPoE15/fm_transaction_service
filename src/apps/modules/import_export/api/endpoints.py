from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from apps.modules.import_export.api.schemas import ImportResult
from apps.modules.import_export.api.uploads import read_upload
from apps.modules.import_export.application.importing import ImportCommandHandler
from apps.modules.import_export.domain.models import FileFormat, TransactionKind
from apps.modules.import_export.infrastructure.templates import CSV_MEDIA_TYPE, XLSX_MEDIA_TYPE, generate_template
from apps.modules.import_export.infrastructure.uow import ImportUnitOfWork
from apps.shared.db.session import async_session_factory
from apps.web.security import UserInfo, get_user_info

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


@router.post(
    "/imports/{transaction_type}",
    status_code=201,
    operation_id="importTransactions",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "additionalProperties": False,
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    }
                }
            },
        }
    },
)
async def import_transactions(
    transaction_type: TransactionKind,
    file_format: Annotated[FileFormat, Query(alias="format")],
    request: Request,
    user: Annotated[UserInfo, Depends(get_user_info)],
) -> ImportResult:
    """Импортировать файл в обычные операции текущего пользователя."""
    content, filename, content_type = await read_upload(request)
    count = await ImportCommandHandler(ImportUnitOfWork(async_session_factory)).handle(
        user.uid,
        content,
        transaction_type=transaction_type,
        file_format=file_format,
        filename=filename,
        content_type=content_type,
    )
    return ImportResult(transaction_type=transaction_type, imported_count=count)
