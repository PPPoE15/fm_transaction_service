from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from xml.etree.ElementTree import Element

from openpyxl.styles.numbers import BUILTIN_FORMATS, is_date_format
from openpyxl.utils.escape import unescape

from apps.modules.import_export.domain.errors import file_error
from apps.modules.import_export.domain.models import RawCell

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
MAX_EXCEL_SERIAL = 100000


def read_date_styles(root: Element | None) -> list[bool]:
    """Определить индексы стилей с форматом даты, включая пользовательские форматы."""
    if root is None:
        return [False]
    formats = dict(BUILTIN_FORMATS)
    for item in root.findall(f"{NS}numFmts/{NS}numFmt"):
        formats[int(item.attrib["numFmtId"])] = item.attrib["formatCode"]
    return [
        is_date_format(formats.get(int(item.get("numFmtId", "0")), "")) for item in root.findall(f"{NS}cellXfs/{NS}xf")
    ]


def text_content(element: Element) -> str:
    """Собрать обычный или rich text без фонетических подсказок."""
    parts = [element.findtext(f"{NS}t", default="")]
    parts.extend(run.findtext(f"{NS}t", default="") for run in element.findall(f"{NS}r"))
    return unescape("".join(parts))


def numeric_value(text: str, *, date_style: bool, mac_epoch: bool) -> object:
    """Прочитать точное число XML; Excel-дату переводить только при целых сутках."""
    try:
        value = Decimal(text)
    except InvalidOperation:
        return False
    if not date_style:
        return value
    if not value.is_finite() or value != value.to_integral_value() or not 0 <= value <= MAX_EXCEL_SERIAL:
        return False
    days = int(value)
    epoch = datetime.fromisoformat("1904-01-01") if mac_epoch else datetime.fromisoformat("1899-12-30")
    # Серийные даты до 2000 года всё равно отклоняет домен; ошибка Excel 29.02.1900 не влияет на диапазон.
    return epoch + timedelta(days=days)


def read_cell(
    cell: Element,
    strings: list[str],
    date_styles: list[bool],
    mac_epoch: bool,
    *,
    date_column: bool,
    default_style: int = 0,
) -> RawCell:
    """Прочитать тип ячейки, не вычисляя формулы и не округляя числовые значения."""
    if cell.find(f"{NS}f") is not None:
        return RawCell(formula=True)
    kind = cell.get("t", "n")
    text = cell.findtext(f"{NS}v")
    if kind == "inlineStr":
        inline = cell.find(f"{NS}is")
        return RawCell(text_content(inline) if inline is not None else None)
    if text is None:
        return RawCell()
    if kind == "s":
        index = int(text)
        if not 0 <= index < len(strings):
            raise file_error()
        return RawCell(strings[index])
    if kind != "n":
        return RawCell(text if kind == "str" else False)
    style = int(cell.get("s", str(default_style)))
    if not 0 <= style < len(date_styles):
        raise file_error()
    return RawCell(numeric_value(text, date_style=date_column and date_styles[style], mac_epoch=mac_epoch))
