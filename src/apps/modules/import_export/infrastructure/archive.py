import zlib
from io import BytesIO
from xml.etree.ElementTree import Element, ParseError
from zipfile import BadZipFile, ZipFile

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring

from apps.modules.import_export.domain.errors import ImportFileError, file_error

MAX_ZIP_ENTRIES = 1000
MAX_UNPACKED_BYTES = 50 * 1024 * 1024
CHUNK_BYTES = 64 * 1024


def read_archive(content: bytes) -> dict[str, bytes]:
    """Распаковать ограниченный ZIP в память, проверяя реально прочитанный объём."""
    try:
        with ZipFile(BytesIO(content)) as archive:
            return _read_entries(archive)
    except (BadZipFile, OSError, EOFError, ValueError, NotImplementedError, zlib.error) as exc:
        raise file_error() from exc


def _read_entries(archive: ZipFile) -> dict[str, bytes]:
    """Проверить метаданные и накопить только разрешённое количество байтов."""
    entries = archive.infolist()
    if len(entries) > MAX_ZIP_ENTRIES or sum(item.file_size for item in entries) > MAX_UNPACKED_BYTES:
        raise ImportFileError(code="FM-413302", message="Превышены ограничения распакованного XLSX")
    result: dict[str, bytes] = {}
    total = 0
    for item in entries:
        if item.flag_bits & 1:
            raise ImportFileError(code="FM-415301", message="Зашифрованные файлы не поддерживаются")
        if item.filename in result:
            raise file_error()
        data = bytearray()
        with archive.open(item) as source:
            while chunk := source.read(min(CHUNK_BYTES, MAX_UNPACKED_BYTES - total + 1)):
                total += len(chunk)
                if total > MAX_UNPACKED_BYTES:
                    raise ImportFileError(code="FM-413302", message="Превышены ограничения распакованного XLSX")
                data.extend(chunk)
        result[item.filename] = bytes(data)
    return result


def parse_xml(content: bytes) -> Element:
    """Прочитать XML без DTD, сущностей и обращений к внешним ресурсам."""
    try:
        return fromstring(content, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except (ParseError, DefusedXmlException, ValueError) as exc:
        raise file_error() from exc
