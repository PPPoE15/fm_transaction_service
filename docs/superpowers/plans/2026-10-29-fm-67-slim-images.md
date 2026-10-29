# FM-67: облегчение transaction-service — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Уменьшить dev/master образы transaction-service минимум на 50%.
**Architecture:** Python 3.13 slim-bookworm; отдельное окружение Poetry в builder, перенос /opt/venv в runtime. Локальная development-env сохраняет /opt/financial_manager и debugpy.
**Tech Stack:** Docker, Poetry 2.1, pytest, Postgres.
**Spec:** PPPoE15/fm-auto-dev#67; текущий запуск ограничен fm_transaction_service.

## Global Constraints
- Не менять lock-файл, API, миграции и зависимости приложения.
- Сохранить dev/master/development-env, команды запуска и пути Compose.
- Сравнивать исходную и новую сборки на linux/arm64 через docker image inspect Size.
- Не сливать PR. Общая задача остаётся незавершённой до реализации auth-service.

## Review Focus
- Нативные расширения загружаются без libpq/compiler: проверить импорты в контейнере.
- Poetry не попадает в venv приложения: проверить importlib и PATH.
- В master отсутствуют dev-пакеты: проверить установленные distributions.
- Bind mount исходников работает с development-env: проверить Alembic и debugpy.
- Очистка кэша не маскируется слоями: проверить filesystem и docker history.

## Task 1: образы и регрессии
- [x] Собрать исходные dev/master и записать Size, image/base IDs.
- [x] Добавить исполняемый в контейнере scripts/check-image.py: импорты runtime, отсутствие Poetry/compiler/cache; наличие debugpy только в dev.
- [x] Запустить проверку на исходном образе, получить ожидаемый FAIL.
- [x] Изменить Dockerfile и docker/Dockerfile, добавить .dockerignore.
- [x] Собрать все цели, повторить проверку (PASS), измерить размеры.
- [x] Выполнить ruff check/format, mypy, полный pytest и Compose smoke с миграциями/JWT/созданием-чтением транзакции.
- [x] Описать сборку и результаты в README.md и CLAUDE.md.
- [x] Проверить diff, закоммитить, push и PR в dev.
- [ ] Дождаться CI, выполнить независимое ревью, исправить замечания по implement-task.

Ревью 1: три средних замечания (конфиг dev-инструментов, default-стадии,
VIRTUAL_ENV) подтверждены и исправлены; каждое покрыто CI-сценарием.
