# FM-87: дневной общий остаток — план реализации

> Исполнение: implement-task, TDD в текущем чате; после зелёного CI — независимое ревью субагентом.

**Цель:** реализовать GET /transaction/balance-history по согласованному контракту.
**Архитектура:** reports: чистая доменная сборка дневных точек, запрос агрегатов и стартового остатка одним SQL statement (единый снимок), тонкий HTTP endpoint. starting_balance экспортирует ORM через публичный API модуля.
**Стек:** FastAPI, Pydantic, SQLAlchemy async, PostgreSQL, pytest.
**Спецификация:** PPPoE15/fm-auto-dev#87; contracts/transaction.openapi.yaml основной ветки fm-auto-dev, /balance-history.

## Ограничения
Даты YYYY-MM-DD 2000–2099, 1–366 дней включительно, не позже сегодня в Europe/Moscow. Момент запроса фиксируется один раз. До стартовой даты null, на неё amount, затем сумма плюс доходы минус расходы. Сегодня исключены будущие операции. Параметры проверяются раньше стартового остатка. Нет остатка — FM-409203; неверные параметры — FM-422000. Все новые функции и классы имеют русские docstring.

## Проверки рисков
- Учет операций до date_from и исключение операций стартового дня.
- Московская полночь отличается от UTC; будущие секунды сегодня исключаются.
- 366 дней допустимы, 367 нет; формат не допускает timestamp/число.
- Чужие операции не влияют на результат, включая неконсистентные ссылки на категории.
- Изменение операции в прошлом пересчитывает все последующие точки.

## Шаги
- [x] Зафиксировать зелёный baseline полным pytest.
- [x] Добавить test_balance_history_api.py с запросами к отсутствующему endpoint; получить 404 вместо ожидаемых 200/409/422.
- [x] Добавить domain/balance_history.py: модели ответа и build_balance_history(date_from, date_to, balance_date, amount, daily_changes).
- [x] Добавить application/queries/balance_history.py: GetBalanceHistory.execute(user_uid, date_from, date_to, now), один SQL SELECT с outer join стартового остатка и дневных агрегатов.
- [x] Добавить application/exceptions.py, api/balance_history.py (валидация дат/диапазона, endpoint) и deps.get_now; подключить router.
- [x] Экспортировать StartingBalanceORM; обновить ожидаемый граф зависимостей и описание архитектуры.
- [ ] Проверить целевые тесты, ruff check/format, mypy, полный pytest.
- [ ] Commit, push, PR в dev; зелёный CI, независимое ревью, исправления и повторные проверки.
