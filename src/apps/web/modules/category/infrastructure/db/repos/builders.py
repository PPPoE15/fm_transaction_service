from apps import db_models
from apps.web.modules.category.aggregators.category import Category


def build_orm(category_agg: Category) -> db_models.Category:
    """
    Конвертировать агрегатор в orm-модель.

    Args:
       category_agg : Агрегатор пользователя с транзакциями.
    """
    return db_models.Category(
        uid=category_agg.uid,
        user_uid=category_agg.user_uid,
        name=category_agg.name,
        money_plan=category_agg.money_plan,
        category_type=category_agg.category_type,
        description=category_agg.description,
    )


def build(orm_category: db_models.Category) -> Category:
    """
    Конвертировать orm-модель в агрегатор.

    Args:
        orm_category: Результаты запроса.
    """
    return Category(
        uid=orm_category.uid,
        user_uid=orm_category.user_uid,
        name=orm_category.name,
        money_plan=orm_category.money_plan,
        category_type=orm_category.category_type,
        description=orm_category.description,
    )
