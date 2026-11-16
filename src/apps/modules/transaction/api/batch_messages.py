"""Русские сообщения форматных ошибок пакетного API без отражения входных значений."""

from typing import Any

_MESSAGES = {
    "missing": "Обязательное поле не передано",
    "extra_forbidden": "Неизвестное поле",
    "int_type": "Ожидается целое число",
    "int_parsing": "Ожидается целое число",
    "int_from_float": "Ожидается целое число",
    "string_type": "Ожидается строка",
    "string_pattern_mismatch": "Строка содержит недопустимые символы",
    "uuid_parsing": "Ожидается корректный UUID",
    "uuid_type": "Ожидается корректный UUID",
    "list_type": "Ожидается список операций",
    "model_type": "Ожидается объект",
    "model_attributes_type": "Ожидается объект",
    "dict_type": "Ожидается объект",
    "json_invalid": "Некорректный JSON",
    "too_long": "Список должен содержать от 1 до 100 операций",
    "too_short": "Список должен содержать от 1 до 100 операций",
}
_TEMPLATES = {
    "greater_than_equal": ("Значение должно быть не меньше {bound}", "ge"),
    "less_than_equal": ("Значение должно быть не больше {bound}", "le"),
    "string_too_long": ("Строка должна содержать не больше {bound} символов", "max_length"),
}


def validation_message(error: dict[str, Any]) -> str:
    """Перевести тип ошибки Pydantic, сохранив русские сообщения собственных валидаторов."""
    kind = error["type"]
    context = error.get("ctx", {})
    location = error.get("loc", ())
    if location and location[-1] == "date":
        return "Укажите существующую дату в формате YYYY-MM-DD, годы 2000–2099"
    if kind in _TEMPLATES:
        template, bound = _TEMPLATES[kind]
        return template.format(bound=context[bound])
    if kind == "value_error":
        message = str(context.get("error", ""))
        if any("А" <= character <= "я" or character in "Ёё" for character in message):
            return message
    return _MESSAGES.get(kind, "Некорректное значение")
