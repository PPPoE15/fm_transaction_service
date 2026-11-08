from fastapi import Request
from fastapi.exceptions import RequestValidationError
from python_multipart.exceptions import MultipartParseError
from starlette.datastructures import FormData, UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from apps.modules.import_export.domain.errors import ImportFileError
from apps.modules.import_export.domain.models import MAX_FILE_BYTES


class LimitedMultipartParser(MultiPartParser):
    """Проверить завершённость multipart и лимит файла во время чтения потока."""

    complete = False
    file_bytes = 0

    def on_part_begin(self) -> None:
        """Начать отсчёт байтов очередной части."""
        super().on_part_begin()
        self.file_bytes = 0

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        """Остановить чтение файла немедленно при превышении 5 МиБ."""
        if self._current_part.file is not None:
            self.file_bytes += end - start
            if self.file_bytes > MAX_FILE_BYTES:
                raise ImportFileError(code="FM-413301", message="Размер файла превышает 5 МиБ")
        super().on_part_data(data, start, end)

    def on_end(self) -> None:
        """Отметить обязательную завершающую границу тела."""
        self.complete = True

    def _check_complete(self) -> None:
        """Отклонить тело без завершающей границы."""
        if not self.complete:
            message = "Незавершённое multipart-тело"
            raise MultiPartException(message)

    async def parse(self) -> FormData:
        """Закрыть все временные файлы при любой ошибке, включая незавершённое тело."""
        try:
            form = await super().parse()
            self._check_complete()
        except BaseException:
            for file in self._files_to_close_on_error:
                file.close()
            raise
        return form


def invalid_parts() -> RequestValidationError:
    """Вернуть стандартную ошибку состава запроса без содержимого загружаемого файла."""
    return RequestValidationError(
        [
            {
                "type": "value_error",
                "loc": ("body", "file"),
                "msg": "Нужен ровно один файл с непустым именем; дополнительные поля запрещены",
                "input": None,
            }
        ]
    )


async def read_upload(request: Request) -> tuple[bytes, str, str | None]:
    """Принять ровно одну file-part и освободить временный файл после чтения."""
    mime = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if mime != "multipart/form-data":
        raise ImportFileError(code="FM-415301", message="Ожидается multipart/form-data")
    parser = LimitedMultipartParser(request.headers, request.stream(), max_files=1, max_fields=0)
    try:
        form = await parser.parse()
    except MultiPartException as exc:
        if exc.message.startswith("Too many"):
            raise invalid_parts() from exc
        raise ImportFileError(code="FM-400301", message="Некорректное multipart-тело") from exc
    except MultipartParseError as exc:
        raise ImportFileError(code="FM-400301", message="Некорректное multipart-тело") from exc
    try:
        items = form.multi_items()
        if len(items) != 1 or items[0][0] != "file":
            raise invalid_parts()
        upload = items[0][1]
        if not isinstance(upload, UploadFile) or not upload.filename:
            raise invalid_parts()
        return await upload.read(MAX_FILE_BYTES + 1), upload.filename, upload.content_type
    finally:
        await form.close()
