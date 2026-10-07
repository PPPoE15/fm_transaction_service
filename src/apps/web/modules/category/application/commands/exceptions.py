from apps.web.utils.exceptions import BaseNotFoundError


class CategoryNotFoundError(BaseNotFoundError):
    """
    Статья не найдена.

    Чужая статья для пользователя тоже «не найдена»: ответ не раскрывает, что запись с таким UID существует.
    """

    msg = "Статья с данным UID не найдена"
