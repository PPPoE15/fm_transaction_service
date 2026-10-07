from apps.modules.category.domain import Category
from apps.modules.category.infrastructure import orm


def build_orm(category_agg: Category) -> orm.Category:
    """
    Конвертировать агрегатор в orm-модель.

    Args:
       category_agg : Агрегатор пользователя с транзакциями.
    """
    return orm.Category(
        uid=category_agg.uid,
        user_uid=category_agg.user_uid,
        name=category_agg.name,
        money_plan=category_agg.money_plan,
        category_type=category_agg.category_type,
        description=category_agg.description,
    )


def build(orm_category: orm.Category) -> Category:
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
