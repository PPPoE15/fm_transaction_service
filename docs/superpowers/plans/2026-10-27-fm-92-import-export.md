# FM-92: шаблоны и чтение файлов — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Шаги выполняются в этом worktree, финальное ревью — отдельным агентом по implement-task.

**Goal:** Выдавать CSV/XLSX-шаблоны и разбирать файлы в нормализованные записи без БД.

**Architecture:** domain содержит записи, ошибки и правила значений; infrastructure читает форматы и создаёт шаблоны; application координирует структурную и доменную проверки; api выдаёт шаблоны и переводит ошибки. Публичный API предназначен для FM-93, который добавит сопоставление категорий и атомарное сохранение.

**Tech Stack:** Python, FastAPI, csv, openpyxl, defusedxml, pytest.

**Spec:** PPPoE15/fm-auto-dev@d910b45:contracts/import-export.md и contracts/transaction.openapi.yaml (FM-91).

## Global Constraints

- Заголовки: Дата;Сумма;Категория;Описание. CSV UTF-8, шаблон с BOM и CRLF.
- XLSX: один видимый лист Доходы/Расходы, без скрытых строк/колонок, объединений, макросов и внешних ссылок.
- Дата dd.mm.yyyy, dd/mm/yyyy, dd-mm-yyyy, 2000–2099; Excel-дата без времени; сумма 1–1 000 000 000 целых рублей без округления.
- 5 МиБ файла, 10 000 операций, 1000 ZIP-элементов, 50 МиБ распакованных данных, 100 ошибок.
- Docstring на русском. Нет обращения к БД. POST импорта, категории и сохранение — FM-93.

## Review Focus

- Структурная ошибка после ошибочных значений заменяет ошибки строк.
- XLSX-числа не теряют дробную часть через float.
- Пустые строки и multiline CSV сохраняют правильную адресацию.
- Недостоверные размеры ZIP/worksheet не обходят ресурсные ограничения.
- Формулы с cached value, DTD/entities и внешние ссылки не выполняются.

### 1. Шаблоны и HTTP

Files: import_export/infrastructure/templates.py, api/endpoints.py, web/router.py, web/main.py; tests/modules/import_export/test_templates.py.
Interface: generate_template(transaction_type, file_format) -> bytes.
- [x] Тесты четырёх вариантов, заголовков, форматов колонок, JWT, обязательных параметров и CORS; увидеть 404 до реализации.
- [x] Реализовать генерацию и GET /import-export/templates/{transaction_type}?format=...
- [x] Проверить тесты.

### 2. Нормализация и CSV

Files: domain/models.py, domain/validation.py, domain/errors.py, application/parsing.py, infrastructure/csv_files.py.
Interface: parse_file(content: bytes, *, transaction_type, file_format, filename: str, content_type: str | None = None) -> list[ParsedRecord]; ImportFileError содержит code/status/errors/errors_truncated.
- [x] Тесты кириллицы, quoting/multiline, трёх форматов даты, целых сумм, category.strip, описаний, пустых записей, структуры, кодировки, лимитов и порядка ошибок; увидеть падение.
- [x] Реализовать декодирование, строгий разбор и независимые доменные проверки.
- [x] Проверить тесты.

### 3. XLSX и границы модуля

Files: infrastructure/xlsx_files.py, infrastructure/archive.py, api/errors.py, __init__.py, tests/modules/import_export/test_xlsx.py, tests/test_architecture.py, CLAUDE.md.
- [x] Тесты обоих epochs, типов ячеек, точности чисел, формул, повреждений, запрещённых конструкций, лимитов ZIP и строк; увидеть падение.
- [x] Реализовать безопасный разбор, публичный API и представление ошибок для FM-93.
- [x] Обновить архитектурные проверки и описание модуля.
- [x] Ruff, format, mypy, полный pytest; commit, push, PR в dev.
- [ ] CI; свежее ревью агентом; исправления по циклу implement-task; статус needs-review.

## Журнал

- Требования взяты из принятого FM-91; дополнительный дизайн не требуется. Реализация в текущем агенте, свежий агент — для итогового ревью.
- Основной checkout не изменяется. База origin/dev 92b9bc7.

- Реализованы шаги 1–3. RED: 8 тестов шаблонов (404), 60 тестов CSV (нет публичного API), 36 тестов XLSX (не реализован формат), 6 проверок HTTP-ошибок. GREEN: 114 тестов модуля; полный промежуточный прогон — 572 passed.
- Дополнительные регрессии RED→GREEN: поле CSV >128 КиБ, экранирование OOXML, VBA relationship. Добавлены неизменённые нормативные примеры FM-91 для проверки совместимости.

- Ревью 1: три средних замечания, все в рамках FM-92 и не покрыты отдельными задачами. LookupError XML → FM-422301 (1921ebe); формат даты не меняет сумму (03e9757); наследование форматов A от строки/колонки исправлено. Для каждого — RED→GREEN и полный прогон перед коммитом. Итог локально: 586 passed, Ruff/format/mypy зелёные.
