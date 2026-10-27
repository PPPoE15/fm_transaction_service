from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from apps.modules.category.application.exceptions import CategoryAlreadyExistsError
from apps.modules.category.application.ports import AbstractCategoryRepo
from apps.modules.category.domain import Category
from apps.modules.category.infrastructure import orm
from apps.shared import apps_types
from apps.shared.db.base_repo import BaseSqlAlchemyRepo

from . import builders

_UNIQUE_NAME_CONSTRAINT = "uq_categories_user_uid_category_type_name"
_UNIQUE_VIOLATION = "23505"
# Пространство ключей advisory-блокировок статей: первый ключ `pg_advisory_xact_lock(int, int)`, второй — хеш
# UID пользователя. Совпадение хешей двух пользователей лишь сериализует их создания статей, на результат не влияет.
_USER_CATEGORIES_LOCK_NAMESPACE = 41


# TODO(FM-41): тот же разбор `exc.orig.__cause__` (внутренности адаптера asyncpg), что и в `starting_balance/…/repo.py`
# — две копии, которые придётся менять вместе при смене драйвера; вынести общий хелпер в `apps/shared/db`.
def _is_unique_name_violation(exc: IntegrityError) -> bool:
    """Нарушено ли ограничение уникальности названия статьи (SQLSTATE и имя ограничения из исходной ошибки asyncpg)."""
    cause = exc.orig.__cause__ if exc.orig else None
    return (
        getattr(cause, "sqlstate", None) == _UNIQUE_VIOLATION
        and getattr(cause, "constraint_name", None) == _UNIQUE_NAME_CONSTRAINT
    )


class Repo(AbstractCategoryRepo, BaseSqlAlchemyRepo):
    """Репозиторий категорий."""

    async def get_all_for_import(
        self,
        user_uid: apps_types.UserUID,
        category_type: apps_types.TransactionType,
    ) -> list[Category]:
        """Заблокировать набор и строки: имена, типы и наличие не меняются до commit."""
        await self.lock_user_categories(user_uid)
        stmt = (
            select(orm.Category)
            .where(
                orm.Category.user_uid == user_uid,
                orm.Category.category_type == category_type,
            )
            .order_by(orm.Category.uid)
            .with_for_update()
        )
        return [builders.build(category) for category in (await self._session.scalars(stmt)).all()]

    async def create(self, category: Category) -> None:
        orm_category = builders.build_orm(category)
        self._session.add(orm_category)
        # flush сразу, чтобы нарушение уникальности при гонке проявилось здесь, а не на commit.
        # TODO(FM-45): блок дословно повторяет `create` — вынести в приватный `_flush_or_conflict()`.
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if _is_unique_name_violation(exc):
                raise CategoryAlreadyExistsError from exc
            raise

    async def lock_user_categories(self, user_uid: apps_types.UserUID) -> None:
        # Advisory-блокировка, а не `SELECT … FOR UPDATE`: блокировка строк не мешает вставке новых (и у пользователя
        # без статей блокировать нечего). Снимается сама на commit/rollback.
        await self._session.execute(
            text("SELECT pg_advisory_xact_lock(:namespace, hashtext(:user_uid))"),
            {"namespace": _USER_CATEGORIES_LOCK_NAMESPACE, "user_uid": str(user_uid)},
        )

    async def count_by_user(self, user_uid: apps_types.UserUID) -> int:
        stmt = select(func.count()).select_from(orm.Category).where(orm.Category.user_uid == user_uid)
        return (await self._session.scalars(stmt)).one()

    async def get_by_name(
        self,
        user_uid: apps_types.UserUID,
        name: apps_types.CategoryName,
        category_type: apps_types.TransactionType,
    ) -> Category | None:
        stmt = select(orm.Category).where(
            orm.Category.user_uid == user_uid,
            orm.Category.category_type == category_type,
            orm.Category.name == name,
        )
        category = (await self._session.scalars(stmt)).one_or_none()
        return builders.build(category) if category else None

    async def lock_category(self, category_uid: apps_types.CategoryUID) -> None:
        # FOR UPDATE конфликтует с FOR KEY SHARE, который берёт вставка транзакции (проверка внешнего ключа): ждём её
        # завершения, и следующий запрос в READ COMMITTED уже видит закоммиченную транзакцию.
        await self._session.execute(select(orm.Category.uid).where(orm.Category.uid == category_uid).with_for_update())

    async def has_transactions(self, category_uid: apps_types.CategoryUID) -> bool:
        # Через связь статьи по имени класса: модуль статей не импортирует модуль транзакций (NOTE(FM-30) в orm.py)
        # NOTE(FM-45): видит только закоммиченные транзакции — вызывать после `lock_category`
        stmt = select(orm.Category.transactions.any()).where(orm.Category.uid == category_uid)
        return bool((await self._session.scalars(stmt)).one_or_none())

    # TODO(FM-45): старый `DELETE /category` не берёт `lock_user_categories`: если статью удалят между чтением
    # в команде и `flush`, UPDATE затронет 0 строк — `StaleDataError` и 500 вместо 404. Решать с переделкой удаления.
    async def update(self, category_agg: Category) -> None:
        orm_category = builders.build_orm(category_agg=category_agg)
        await self._session.merge(orm_category)
        # flush сразу, чтобы нарушение уникальности при гонке проявилось здесь, а не на commit.
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if _is_unique_name_violation(exc):
                raise CategoryAlreadyExistsError from exc
            raise

    async def delete(self, category_uid: apps_types.CategoryUID) -> None:
        category = await self._session.get(orm.Category, category_uid)
        await self._session.delete(category)

    async def get_by_uid_for_key_share(self, category_uid: apps_types.CategoryUID) -> Category | None:
        # FOR KEY SHARE — та же блокировка, что берёт проверка внешнего ключа при вставке транзакции: конфликтует
        # с FOR UPDATE и DELETE, но не с другими вставками транзакций в эту статью.
        stmt = select(orm.Category).where(orm.Category.uid == category_uid).with_for_update(key_share=True)
        category = (await self._session.scalars(stmt)).one_or_none()
        return builders.build(category) if category else None

    async def get_by_uid(self, category_uid: apps_types.CategoryUID) -> Category | None:
        category = await self._session.get(orm.Category, category_uid)
        return builders.build(category) if category else None
