# FM-108: атомарное подтверждение плана

## Требования и границы

Контракт FM-106: POST /planned-operations/{uid}/confirm возвращает {plan,transaction};
GET /transactions/{uid} читает собственный актуальный факт. Повтор completed —409401,
устаревшая версия pending —409402. Снимок плановых полей сохраняется; дата факта может быть
прошлой или будущей. Нет ключей повторов, повторных COMMIT и новых CHECK в БД.
Модель остаётся PlannedTransaction / planned_transactions.

## Реализация и проверки

1. Домен: Plan.complete фиксирует связь, UTC-время и имя исходной категории,
   увеличивает версию; не изменяет плановые значения. Тесты перехода/повтора/версии.
2. Приложение: ConfirmPlanCommand и общий валидатор создания транзакции через публичный
   API transaction. PlanUnitOfWork получает репозиторий фактов той же SQLAlchemy-сессии.
   Порядок блокировок: план -> advisory 52 (квота) -> обе категории по UID ASC.
   Все изменения и ответ собираются до commit. Часы читаются после блокировок.
3. API: строгая схема полного набора фактических значений, отдельный маршрут confirm,
   GET факта через существующий запрос с владельцем. Привязка ошибок категории подтверждения к полю.
4. PostgreSQL/API: баланс и сохранение исходных значений, прошлые/будущие факты, чужие данные,
   валидация, лимит, конкурентные confirm/PATCH/DELETE и обычное создание, rollback после
   вставки, потеря ответа commit и явный повтор, изменение/удаление факта, удаление плана.
5. Ruff/format/mypy, полный pytest и SSH-тесты. PR в dev, CI, независимое ревью.

## Изменяемые файлы

planning/domain/model.py; application/{confirmation.py,schemas.py,uow.py};
infrastructure/uow.py; api/{schemas.py,deps.py,endpoints.py,errors.py};
transaction/application/creation_rules.py и commands/create.py; transaction/__init__.py;
transaction/api/endpoints.py; тесты planning и архитектурный граф; CLAUDE.md.

Миграции и HTTP-контракт не меняются. UI — FM-109/110.
