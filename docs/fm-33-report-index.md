# FM-33: индекс операций и факты бюджета

Неуникальный B-tree `ix_transactions_user_uid_transaction_date` по `(user_uid, transaction_date)` объявлен в ORM и миграции `a33b00000001` после `a99b102c0001`.

Прошлый год читается полностью; текущий — до начала следующего месяца исключительно, включая будущие дни текущего месяца. Для будущего года запрос фактов не выполняется; категории и планы сохраняются. Контракт API не меняется.

Обычный транзакционный CREATE INDEX блокирует записи в transactions на время построения: применять с учётом окна обслуживания. Downgrade удаляет только индекс. Пользовательский стенд при проверке не затрагивался.

## Проверка PostgreSQL

PostgreSQL 16, отдельный testcontainers-контейнер, 100000 операций, 100 пользователей, 100 категорий. После ANALYZE выполнен EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) реального запроса GetBudgetStructure за март 2026, без изменения настроек планировщика.

```sql
SELECT transactions.category_uid, CAST(EXTRACT(month FROM transactions.transaction_date) AS INTEGER) AS month, sum(CAST(transactions.money_sum AS BIGINT)) AS money_total 
FROM transactions JOIN categories ON categories.uid = transactions.category_uid 
WHERE transactions.user_uid = 'dc98b5ec-530e-4360-98b7-b5ca7f377896' AND categories.user_uid = 'dc98b5ec-530e-4360-98b7-b5ca7f377896' AND categories.category_type = 'outcome' AND transactions.transaction_date >= '2026-01-01 00:00:00' AND transactions.transaction_date < '2026-04-01 00:00:00' GROUP BY transactions.category_uid, CAST(EXTRACT(month FROM transactions.transaction_date) AS INTEGER)
```

План: Aggregate → Sort → Nested Loop; категории — Seq Scan (100 строк), операции — Bitmap Heap Scan → Bitmap Index Scan по `ix_transactions_user_uid_transaction_date`. Index Cond включает владельца и обе границы дат; прочитано 270 операций. В одном локальном прогоне planning = 0.248 ms, execution = 0.252 ms. Это подтверждение выбора индекса, не сравнительный бенчмарк. Полный результат: [fm-33-explain.json](fm-33-explain.json).

Воспроизведение:

```sh
poetry run pytest src/tests/modules/reports/test_budget_structure_index.py -o log_cli=true --log-cli-level=INFO
make test_downgrade_migrations_compose
```

Историческое имя make-цели сохранено. Теперь она запускает миграционные pytest-тесты с отдельным Docker Postgres через testcontainers: полный downgrade/upgrade, сохранность данных при откате индекса, отсутствие autogenerate drift. Ошибки больше не маскируются.
