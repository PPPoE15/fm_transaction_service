# FM-99: редактирование транзакций — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Реализовать backend согласованного контракта FM-102: список, одиночные изменения, атомарное сохранение и частичное удаление пакетов.

**Architecture:** Сохранить модули и слои сервиса. Команды принимают решения внутри UoW, репозитории обеспечивают блокировки и хранение; ответы сохранения строятся из проверенного состояния до commit и возвращаются после успешного commit. Список читается одним SQL-запросом с общей выборкой фильтров, подсчётом и пагинацией, включая пустую страницу.

**Tech Stack:** FastAPI, Pydantic 2, SQLAlchemy async, PostgreSQL, Alembic, pytest, Poetry.

**Spec:** PPPoE15/fm-auto-dev#99; contracts/transaction.openapi.yaml и contracts/README.md в fm-auto-dev, merge FM-102 b051fc7. Согласованный объём этого прохода: только fm_transaction_service; proxy в fm_devops отдельно.

## Global Constraints

- База origin/dev, ветка feature/fm-99-transaction-editing, отдельный worktree fm-99-transactions/fm_transaction_service.
- Новые и существующие операции получают version=1; каждый успешный PATCH увеличивает её, включая запись тех же значений. Конфликт FM-409204.
- Пакеты: 1–100 уникальных UID; expected_version обязателен; неизвестные поля запрещены.
- PATCH batch атомарен; порядок приоритета ошибок 404, 409, 400. POST batch-delete возвращает HTTP 200 и результаты 204/404/409 по порядку входа; неожиданная ошибка до commit откатывает все удаления.
- Сумма — целое JSON-число 1–1000000000, описание до 500 символов; только description допускает null. Даты 2000–2099; массовая дата сохраняет время и микросекунды.
- Пакетные тела до 524288 байт включительно; остальные до 16384, кроме существующего импорта 6 МиБ. Считать фактические байты независимо от Content-Length.
- Не добавлять Idempotency-Key или кеш повторных ответов. Повтор со старой версией не повторяет успешную запись.
- Русские docstring у всех новых классов, функций, методов, включая тесты.
- Перед каждым коммитом полный ruff check, ruff format --check, mypy и pytest. PR в dev, без слияния.

## Review Focus

- Одновременные PATCH/DELETE с одинаковой версией: один победитель, остальные конфликт/отсутствие; блокировки в порядке UID без взаимных блокировок с импортом и категориями (задачи 1, 3).
- Пустая страница при ненулевом total и конкурентные записи: один согласованный снимок, next_skip=null (задача 2).
- Неправильный Content-Length и поток без него: фактический лимит сохраняется (задача 4).
- Ошибка позднего элемента пакета или сбой записи: отсутствие скрытых частичных сохранений и неожиданных частичных удалений (задача 3).
- Перенос между месяцами и категориями: отчёты меняются, стартовый остаток и планы нет (задача 5).

## 1. Версии и одиночные операции

**Files:** transaction/domain/transaction.py, application/{ports.py,exceptions.py,commands/update.py,commands/delete.py}, infrastructure/{orm.py,builders.py,repo.py}, api/{schemas.py,endpoints.py,deps.py}, application/queries/schemas.py под src/apps/modules/; новая миграция src/migrations/versions/2026_11_06_1200_add_transaction_version.py; src/tests/modules/transaction/{fakes.py,test_commands.py,test_update_api.py,test_delete_api.py,test_version_migration.py}.

**Interfaces:** Transaction.version: int; Repo.get_by_uid_for_update(transaction_uid) -> Transaction | None; типизированный TransactionChanges с учётом пропущенных полей; UpdateTransactionCommandHandler.handle(user_uid, transaction_uid, changes, expected_version=None) -> TransactionSchema; DeleteTransactionCommandHandler.handle(user_uid, transaction_uid, expected_version=None) -> None. Одиночные пути /transactions/{transaction_uid}.

- [x] Добавить тесты: частичное изменение, очистка описания, пустой PATCH, expected_version без изменений, чужая операция, чужая/несовместимая категория, невалидные поля; 200 с объектом и 204 без тела; одинаковые значения увеличивают версию.
- [x] Запустить тесты и зафиксировать ожидаемые падения из-за отсутствующего поведения.
- [x] Добавить миграцию с default=1 и ограничением положительности, перенести версию через ORM/builders/ответы, блокировать строку до проверки версии и записи. Проверять итоговые тип и категорию под блокировкой категории. Сохранить совместимость внутренних вызовов импорта и создания.
- [x] Проверить миграцию на существующей строке, downgrade/upgrade и конкурентные одиночные изменения на Postgres. Прогнать набор проверок и закоммитить.

## 2. Согласованный список

**Files:** src/apps/modules/transaction/application/queries/{get.py,schemas.py}, api/endpoints.py; src/tests/modules/transaction/test_list.py.

**Interfaces:** TransactionFilters.category_uid; TransactionList(content: list[TransactionSchema], total: int, next_skip: int | None). Сохранить интерфейс get_transactions -> tuple[list[TransactionSchema], int] для внутренних потребителей.

- [x] Добавить падающие тесты: AND-фильтры category/category_uid/type/date, литеральный поиск названия, одинаковые даты при обоих направлениях сортировки, страницы 1/500, skip>=total и пустой результат, next_skip, version.
- [x] В одном SQL-снимке получить count и страницу, присоединив данные категории; пустая страница не теряет total. Исправить существующий фильтр category, сравнивающий relationship со строкой.
- [x] Проверить согласованность списка при конкурентном изменении, изоляцию чужих категорий и включительность дат. Выполнить проверки и коммит.

## 3. Пакетные команды и ошибки

**Files:** новые src/apps/modules/transaction/application/{commands/batch_update.py,commands/batch_delete.py,batch_models.py}, api/{batch_schemas.py,batch_endpoints.py,batch_errors.py}; правки api/deps.py, application/exceptions.py, infrastructure/repo.py и сборки router/exception handlers; новые src/tests/modules/transaction/{test_batch_update.py,test_batch_delete.py,test_batch_concurrency.py}.

**Interfaces:** BatchUpdateCommandHandler.handle(user_uid, items) -> list[TransactionSchema]; BatchDeleteCommandHandler.handle(user_uid, items) -> list[DeleteResult]; DeleteResult — отдельные типы успеха (index,uid,status=204) и ошибки (index,uid,status=404|409,code,message). BatchError содержит status и errors с code/message и доступными index/uid/field.

- [x] Добавить падающие тесты успешного пакета, сохранения времени, порядка ответа и ошибок 404>409>400; отката ранних элементов при ошибке позднего. Добавить смешанное удаление, все ошибки, повтор, невалидный пакет без удалений.
- [x] Валидировать весь вход до команд. Реализовать стабильный порядок блокировок UID, совместимый с категориями/импортом, с проверками внутри UoW; отдельно сбор ошибок и запись. Регистрация статических batch-маршрутов до UUID-пути.
- [x] Добавить tests на 0/1/100/101 элементов, дубликаты UID, null/лишние поля/некорректную дату/сумму, обязательную версию; RFC7807 и errors для структурных ошибок пакета.
- [x] Добавить реальные конкурентные тесты перекрывающихся пакетов, одиночного и пакетного изменения; тест неожиданной ошибки до commit с полным rollback. Выполнить проверки и коммит.

## 4. Лимиты тела

**Files:** src/apps/web/body_size.py; src/tests/web/test_body_size.py и существующие тесты middleware/import.

**Interfaces:** MAX_BATCH_BODY_SIZE=524288; выбор лимита по точному маршруту и методу; _reject передаёт актуальный лимит, сохраняя FM-413000 и import-коды.

- [x] Добавить падающие тесты границы и +1 байт обоих лимитов, обоих пакетных методов, отсутствующего/заниженного Content-Length и потоковых сообщений; валидный JSON дополнять пробелами.
- [x] Считать реальные байты для всех запросов, сохранить раннее отклонение заведомо большого Content-Length и лимит импорта; 413 application/problem+json до доменной обработки.
- [x] Проверить 100 элементов с длинными комментариями и регрессию импорта. Выполнить проверки и коммит. Проверки через внешний proxy явно оставить следующему проходу fm_devops.

## 5. Итоги и завершение

**Files:** src/tests/modules/transaction/test_edit_reports.py, CLAUDE.md; при обнаружении ошибки расчёта — соответствующий модуль reports в пределах сценария задачи.

**Interfaces:** существующие GET budget-structure и balance-history; новые методы операций, перечисленные выше.

- [ ] Добавить интеграционные проверки изменения суммы, даты/месяца, категории, одиночного/массового удаления и отката. Проверять фактические ответы отчётов, неизменность стартового остатка и планов, изоляцию пользователей.
- [ ] При падении из-за ошибки расчёта исправить её в рамках задачи; повторить тесты. Обновить описание API, версий и блокировок в CLAUDE.md.
- [ ] Выполнить poetry run ruff check --config=pyproject.toml src/, poetry run ruff format --config=pyproject.toml src/ --check, poetry run mypy --config-file=pyproject.toml src/, poetry run pytest. Коммит и push.
- [ ] Создать PR в dev с названием задачи, проверками и явной оговоркой о proxy. Дождаться CI, провести ревью свежим субагентом локально в worktree. Исправлять критичные/средние замечания по implement-task, максимум три раунда.
- [ ] После успешного ревью поставить needs-review и добавить ссылку на PR в задачу; не закрывать задачу и не сливать PR.
