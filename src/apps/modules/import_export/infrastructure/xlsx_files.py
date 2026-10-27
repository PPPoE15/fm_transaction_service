import posixpath
import re
from collections.abc import Iterator
from dataclasses import dataclass
from xml.etree.ElementTree import Element

from apps.modules.import_export.domain.errors import ImportFileError, file_error
from apps.modules.import_export.domain.models import HEADERS, SHEET_NAMES, RawCell, RawRecord, TransactionKind
from apps.modules.import_export.infrastructure.archive import parse_xml, read_archive
from apps.modules.import_export.infrastructure.xlsx_cells import NS, read_cell, read_date_styles, text_content

REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
DOC_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
CELL_REFERENCE = re.compile(r"([A-Z]+)([1-9][0-9]*)")
MAX_SHEET_ROW = 1048576
MAX_SHEET_COLUMN = 16384
WORKBOOK_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"


@dataclass
class WorkbookParts:
    """Проверенные XML-части книги и таблицы преобразования значений."""

    sheet: Element
    strings: list[str]
    date_styles: list[bool]
    mac_epoch: bool


def _relationships(root: Element, owner: str) -> dict[str, tuple[str, str]]:
    """Разрешить только внутренние отношения OOXML без выхода за корень контейнера."""
    result = {}
    for relation in root.findall(f"{REL_NS}Relationship"):
        if relation.get("TargetMode", "Internal") != "Internal":
            raise file_error()
        relation_type = relation.attrib["Type"].lower()
        if "vba" in relation_type or "externallink" in relation_type:
            raise file_error()
        target = relation.attrib["Target"]
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(owner), target))
        if resolved.startswith("../") or "\\" in resolved or ":" in resolved:
            raise file_error()
        result[relation.attrib["Id"]] = (relation.attrib["Type"].rsplit("/", 1)[-1], resolved.lstrip("/"))
    return result


def _part_by_type(relations: dict[str, tuple[str, str]], kind: str) -> str | None:
    """Найти необязательную часть книги по типу связи, отклоняя неоднозначность."""
    targets = [target for rel_kind, target in relations.values() if rel_kind == kind]
    if len(targets) > 1:
        raise file_error()
    return targets[0] if targets else None


def _load_parts(content: bytes, transaction_type: TransactionKind) -> WorkbookParts:
    """Проверить контейнер, корневые части, листы и запрещённые конструкции книги."""
    archive = read_archive(content)
    xml = {name: parse_xml(data) for name, data in archive.items() if name.endswith((".xml", ".rels"))}
    for name, root in xml.items():
        if name.endswith(".rels"):
            _relationships(root, "")
    types = xml["[Content_Types].xml"]
    content_types = {node.get("ContentType", "") for node in types}
    if any("macroEnabled.main" in value for value in content_types):
        raise ImportFileError(code="FM-415301", message="XLSM не поддерживается")
    if WORKBOOK_CONTENT_TYPE not in content_types:
        raise file_error()
    if any("vba" in name.lower() or "externallinks/" in name.lower() for name in archive):
        raise file_error()
    if any("vba" in value.lower() or "externallink" in value.lower() for value in content_types):
        raise file_error()
    root_relations = _relationships(xml["_rels/.rels"], "")
    workbook_path = _part_by_type(root_relations, "officeDocument")
    if workbook_path is None:
        raise file_error()
    workbook = xml[workbook_path]
    sheets = workbook.findall(f"{NS}sheets/{NS}sheet")
    if (
        len(sheets) != 1
        or sheets[0].get("name") != SHEET_NAMES[transaction_type]
        or sheets[0].get("state", "visible") != "visible"
    ):
        raise file_error()
    rel_path = posixpath.join(posixpath.dirname(workbook_path), "_rels", posixpath.basename(workbook_path) + ".rels")
    relations = _relationships(xml[rel_path], workbook_path)
    kind, sheet_path = relations[sheets[0].attrib[f"{DOC_REL_NS}id"]]
    if kind != "worksheet":
        raise file_error()
    strings_path = _part_by_type(relations, "sharedStrings")
    styles_path = _part_by_type(relations, "styles")
    properties = workbook.find(f"{NS}workbookPr")
    return WorkbookParts(
        sheet=xml[sheet_path],
        strings=[text_content(item) for item in xml[strings_path].findall(f"{NS}si")] if strings_path else [],
        date_styles=read_date_styles(xml[styles_path] if styles_path else None),
        mac_epoch=properties is not None and properties.get("date1904") in {"1", "true"},
    )


def _read_row(row: Element, parts: WorkbookParts, number: int) -> RawRecord:
    """Прочитать редкую строку без обхода огромного прямоугольника из dimension."""
    cells = [RawCell() for _ in HEADERS]
    seen = set()
    for cell in row.findall(f"{NS}c"):
        match = CELL_REFERENCE.fullmatch(cell.attrib["r"])
        if match is None or int(match[2]) != number or match[1] in seen:
            raise file_error()
        column = match[1]
        seen.add(column)
        value = read_cell(cell, parts.strings, parts.date_styles, parts.mac_epoch)
        if column not in "ABCD" or len(column) != 1:
            if value.value not in (None, "") or value.formula:
                raise file_error()
        else:
            cells[ord(column) - ord("A")] = value
    return RawRecord(number, tuple(cells))


def _rows(parts: WorkbookParts) -> Iterator[RawRecord]:
    """Проверить структуру листа и заголовки, затем передать записи в доменную проверку."""
    sheet = parts.sheet
    if sheet.tag != f"{NS}worksheet" or sheet.find(f"{NS}mergeCells/{NS}mergeCell") is not None:
        raise file_error()
    dimensions = list(sheet.findall(f"{NS}cols/{NS}col")) + list(sheet.findall(f"{NS}sheetData/{NS}row"))
    if any(item.get("hidden") in {"1", "true"} for item in dimensions):
        raise file_error()
    previous = 0
    for row in sheet.findall(f"{NS}sheetData/{NS}row"):
        number = int(row.attrib["r"])
        if not previous < number <= MAX_SHEET_ROW:
            raise file_error()
        raw = _read_row(row, parts, number)
        if previous == 0:
            if (
                number != 1
                or tuple(cell.value for cell in raw.cells) != HEADERS
                or any(cell.formula for cell in raw.cells)
            ):
                raise file_error()
        else:
            yield raw
        previous = number
    if previous == 0:
        raise file_error()


def read_xlsx(content: bytes, transaction_type: TransactionKind) -> Iterator[RawRecord]:
    """Разобрать разрешённый поднабор XLSX, переводя повреждения в ошибку файла."""
    try:
        yield from _rows(_load_parts(content, transaction_type))
    except (KeyError, ValueError, IndexError, OverflowError) as exc:
        raise file_error() from exc
