# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

`fm_transaction_service` (package name `financial_manager`) is an async FastAPI service for managing personal finance transactions and categories. Python 3.11+ (Docker image uses 3.13), SQLAlchemy 2.0 async ORM + asyncpg, Alembic migrations, Pydantic v2 / pydantic-settings. Code comments and docstrings in this repo are written in Russian — match that convention when editing existing files.

This is an early-stage codebase (see recent commit "Преждевременный коммит для сохранения наработок" — "premature commit to save progress in-progress work"); some pieces (e.g. a pytest dependency) referenced by tooling are not yet wired up.

## Commands

Dependencies are managed with Poetry (`poetry install --all-groups`). All app code lives under `src/`, so most tools need `--app-dir src` / `PYTHONPATH=src` context (see `scripts/uvicorn_up.sh`).

```bash
# Lint (ruff check --fix, ruff format check, mypy) — run from repo root
make run_linters

# Or individually, as CI does it (scripts/linters.sh):
ruff check --config=pyproject.toml src/
mypy --config-file=pyproject.toml src/

# Tests (run from repo root; pytest config lives in pyproject.toml: pythonpath=src, asyncio_mode=auto)
poetry run pytest                      # full run; tests marked `db` start postgres:16 via testcontainers (needs Docker)
poetry run pytest -m "not db"          # quick run without Docker
poetry run pytest src/tests/web/test_security.py -v

# Coverage
make pytest_coverage

# Alembic migrations (must run from src/, where alembic.ini lives)
make migrate              # applies migrations for the DB set in the active env file
make generate_migration   # prompts for a title, runs `alembic revision --autogenerate`

# Local dev stack (Postgres + hot-reloading web app with debugpy on :5678)
make build      # docker compose build (docker/docker-compose.yml)
make up_all     # start the `web` service (applies migrations first via _init-migrations)
make down_all

# Verify all migrations downgrade cleanly
make test_downgrade_migrations_compose
```

Note: the root `docker-compose.yaml` and `Makefile`'s `build`/`up_all`/`down_all` targets reference `docker/docker-compose.yml`, which is the actual dev compose file (builds via `docker/Dockerfile`, target `development-env`). The root `Dockerfile` (targets `dev`/`master`) is what CI (`.github/workflows/docker-image-*.yml`) builds and pushes to Docker Hub as `fm_transaction_service:dev`/`:master`.

Tests: `src/tests/__init__.py` sets up the test env (generates an RSA key pair, points `WEB_PUBLIC_KEY_PATH` at the public key, dummy `DB_*`) before any `apps` import, because settings are read at import time. `src/tests/conftest.py` has `make_token` (RS256 tokens like the auth service issues), `client` (httpx over the ASGI app) and the `db` fixtures: a session-scoped Postgres container with `alembic upgrade head`, and `db_engine`, which rebinds `async_session_factory` to it and truncates tables after each test. Without Docker the `db` tests fail with an explicit message rather than being skipped. Command handlers are unit-tested with plain in-memory fakes from `src/tests/modules/<module>/fakes.py`.

Config is loaded from `dev.env`/`prod.env` (see `ENV_FILES` in `src/apps/config.py` and `src/apps/web/config.py`) or `/run/secrets`; `template.env` is the template used to generate a local env file. Env vars are prefixed `DB_` (database) and `WEB_` (app settings).

## Architecture

### Layout — modules on top, layers inside (FM-30)

- `src/apps/config.py` — DB/logging settings (`DB_` prefix).
- `src/apps/shared/` — shared kernel with no domain logic, used by several modules: `apps_types/` (domain-wide `Annotated` aliases like `UserUID`, `MoneySum`, `TransactionType`), `schemas.py` (`Base`, `PageParams`), `api_schemas.py` (`BaseResponseSchema`/`BaseListResponseSchema` envelopes), `exceptions.py` (`BaseError` family), `unit_of_work.py` (`AbstractUnitOfWork`, `AbstractSQLAlchemyUnitOfWork`), `logger.py`, `datetime_tz.py`, and `db/` — `base.py` (`AsyncBase` declarative base with an explicit constraint-naming convention), `session.py` (`async_engine` from `db_settings.DSN`, `async_session_factory`), `base_repo.py` (`BaseSqlAlchemyRepo`), `base_query.py` (`BaseQueries` with `_apply_pagination`/`_model_to_dict`), `tz_type.py`.
- `src/apps/web/` — application assembly, no domain logic: `main.py` builds the app (CORS, exception handlers, lifespan) and mounts the API under `/transaction` (the reverse proxy passes the path through unchanged, like `/auth` in the auth service; tests' `client` fixture has `base_url` ending in `/transaction`, so test paths omit it; until the UI's nginx stops stripping the prefix the routes are also mounted without it, hidden from the schema — `TODO(FM-31)` in `main.py`), `router.py` includes each module's `api` router, `security.py` verifies the access token (RS256 signature with the auth service's public key from `WEB_PUBLIC_KEY_PATH`, default `/run/secrets/jwt_public_key`; `exp` and `sub` required; any failure → 401) and produces `UserInfo` (just `uid` from `sub`). The key is checked on startup (`validate_public_key` in `LifespanEvent`), so a missing/private/non-PEM key fails the app at boot. `config.py` holds `WEB_`-prefixed settings; `exception_handlers/`, `bootstrap/`, `telemetry/`.
- `src/apps/modules/<module>/` — one package per bounded context: `category` (статьи), `transaction` (транзакции) and `reports` (отчёты, read-only; FM-27: `GET /budget-structure`). `reports` has no tables of its own, so `infrastructure/` is empty; queries aggregate over the category/transaction ORM exported by those modules, report rules live in `domain/` and take today's date as a parameter (`api/deps.get_today`, overridden in tests). One file per report in each layer (`domain/budget_structure.py`, `application/queries/budget_structure.py`), so the next read-only report (balance) goes next to it. Being read-only, `reports` deviates from the layering below: no commands/UoW/ports/fakes, the query class (`GetBudgetStructure.execute`) returns the domain read model, which is also the response schema (`NOTE(FM-27)` in `api/endpoints.py`), and its tests are domain unit tests plus API tests on Postgres. Write-side areas (starting balance) get their own module in their own task.
- `src/apps/db_models/__init__.py` — ORM registry: imports every module's `infrastructure/orm.py` and re-exports `AsyncBase`, so Alembic (`migrations/env.py` imports `AsyncBase` **from here**, not from `shared.db.base`) sees all tables. The app itself doesn't import it — see the relationship rule below.
- `src/migrations/` — Alembic env (`env.py` runs migrations async via `run_sync`) and versioned migration scripts.
- `src/tests/` — `modules/<module>/` (command-handler unit tests + that module's in-memory fakes in `fakes.py`; the shared commit/rollback mixin is `tests/modules/fakes.py`), `web/` (security, isolation, health), `test_architecture.py` (module boundary rules, see below).

### Module layering (CQRS-ish, per module)

Each `modules/<name>/` contains only `__init__.py` and four layers; use `transaction` as the reference when adding a module or endpoint:

- `__init__.py` — the module's public API (`__all__`). **The only thing other modules may import.** `category` exports `Category`, `AbstractCategoryRepo`, `CategoryRepo`, `CategoryNotFoundError`, `get_own_category`, `CategoryORM`; `transaction` exports `TransactionORM` (for read-only reports); `reports` exports nothing.
- `domain/` — plain Pydantic aggregates (not ORM models), no SQLAlchemy/FastAPI. Own their invariants and mutation logic (e.g. `Transaction.create(...)`, `transaction.update(...)`, `belongs_to`). Commands and repos operate on these — never pass ORM models across layer boundaries.
- `application/` — `commands/` (write side: `*CommandHandler` with a single `handle(...)`, built with the module's Unit of Work), `queries/` (read side: `*Queries(BaseQueries)` take a session directly — no UoW — build `Select`s on the module's ORM and map rows to `queries/schemas.py` response schemas), `ports.py` (`abc.ABC` repository interfaces over aggregates), `uow.py` (`Abstract<Module>UnitOfWork` exposing the repos as attributes), `exceptions.py`, `guards.py` (ownership checks: someone else's record is "not found").
- `infrastructure/` — `orm.py` (SQLAlchemy models), `repo.py` (`Repo(Abstract<X>Repo, BaseSqlAlchemyRepo)`, aggregate <-> ORM via `builders.py`), `uow.py` (concrete `<Module>UnitOfWork(Abstract…, AbstractSQLAlchemyUnitOfWork)` that creates the repos in `__aenter__`).
- `api/` — `endpoints.py` (`APIRouter`; handlers build a command handler — via `deps.py` where present — call `.handle(...)`, then open a fresh session via `async_session_factory` for the follow-up query), `schemas.py` (request bodies), `deps.py`.

Dependency rules (enforced by `src/tests/test_architecture.py`, which reads imports statically, including `TYPE_CHECKING` ones):

- A module imports another module only through its `__init__` (`from apps.modules import category`, `from apps.modules.category import …`); no cycles. Today `transaction` → `category` and `reports` → `category`, `transaction`; `category` knows nothing about the others.
- `shared/` imports neither `modules/`, `db_models/` nor `web/`. Modules import from `web/` only `apps.web.security` (auth dependency).
- `domain/` doesn't import other layers of its module; `api/` is imported only by `web/`.
- Cross-module ORM relationships are declared by class name (`relationship("Transaction", …)`), not by importing the other module. The name resolves only once the target model is loaded: in the app `web/router.py` loads every module (via their `api`), in Alembic the `db_models` registry does. Code outside the app that touches a module's ORM (scripts, workers, a module test without `apps.web.main`) must import `apps.db_models` first, otherwise SQLAlchemy resolves `"Transaction"` to its own `sqlalchemy.engine.Transaction` (`UnmappedClassError`). The only reverse link is `Category.transactions` (cascade delete of a category's transactions, see `NOTE(FM-30)` in `category/infrastructure/orm.py`; goes away with FM-4).

The "Adapters stay thin" rule from the workspace `CLAUDE.md` applies unchanged.

Each request gets its own `AsyncSession`: commands open one implicitly inside the UoW (`session_factory()` in `__aenter__`); endpoint handlers open a second, separate one directly via `async_session_factory()` for the query that runs after a write. Sessions are not shared between the write and the follow-up read.

### Errors

Domain/application code raises typed exceptions from `apps.shared.exceptions` (`BaseCustomValidationError` -> 422, `BaseNotFoundError` -> 404, `BaseForbiddenError` -> 403) or subclasses defined per module in `application/exceptions.py`. Every command checks ownership against `UserInfo.uid` (aggregate `belongs_to`); someone else's transaction or category is reported as not found (404), never 403. Exceptions are translated to RFC7807-style JSON responses (`BaseErrorResponseSchema` in `web/exception_handlers/base.py`) by handlers registered in `web/exception_handlers/`, wired up via `exception_handlers.setup(fastapi_app)` in `main.py`.

### Linting

`ruff` runs with `lint.select = ["ALL"]` plus an explicit ignore list — see `pyproject.toml`. Notable per-path relaxations: `src/tests/*` allows asserts/missing docstrings/private-member access; `src/migrations/*` allows missing docstrings. `mypy` runs in strict-ish mode (`disallow_untyped_defs`, `check_untyped_defs`, `no_implicit_reexport`) with the pydantic mypy plugin enabled.
