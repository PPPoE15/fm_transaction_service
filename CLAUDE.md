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

# Run a single test (pytest is not yet declared in pyproject.toml — install it if missing)
cd src && pytest tests/web/test_healthy.py -v

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

Config is loaded from `dev.env`/`prod.env` (see `ENV_FILES` in `src/apps/config.py` and `src/apps/web/config.py`) or `/run/secrets`; `template.env` is the template used to generate a local env file. Env vars are prefixed `DB_` (database) and `WEB_` (app settings).

## Architecture

### Layout

- `src/apps/` — shared, transport-agnostic code: `config.py` (DB/logging settings), `apps_types/` (domain-wide `Annotated` type aliases like `UserUID`, `MoneySum`, `TransactionType`), `db_models/` (SQLAlchemy ORM models + `AsyncBase` declarative base with an explicit constraint-naming convention), `utils/`.
- `src/apps/web/` — the FastAPI application: `main.py` builds the app (CORS, exception handlers, lifespan), `router.py` aggregates module routers, `security.py` does JWT decoding (signature verification is currently disabled — `verify_signature: False`) to produce `UserInfo`, `config.py` holds `WEB_`-prefixed app settings, `core/` holds cross-module base classes (see below), `connectors/postgres.py` builds the async SQLAlchemy engine from `db_settings.DSN`.
- `src/apps/web/modules/<module>/` — one directory per bounded context (currently `category`, `transaction`). Every module follows the same internal layering; use `transaction` as the reference implementation when adding a new module or endpoint.
- `src/migrations/` — Alembic env (`env.py` runs migrations async via `run_sync`) and versioned migration scripts.
- `src/tests/` — pytest tests, mirroring the `src/apps/...` layout (currently minimal).

### Module layering (CQRS-ish, per module)

Each module under `modules/<name>/` is split into:

- `aggregators/` — plain Pydantic domain objects (not ORM models). Own their invariants and mutation logic via classmethods/methods (e.g. `Transaction.create(...)`, `transaction.update(...)`). These are what commands and repos operate on — never pass ORM models across layer boundaries.
- `application/commands/` — write side. Each command is a `*CommandHandler` class with a single `handle(...)` method, constructed with a module-specific Unit of Work. `uow.py` in each module defines an `Abstract<Module>UnitOfWork(AbstractUnitOfWork)` protocol exposing the module's repo(s) as attributes, and a concrete SQLAlchemy implementation (`<Module>UnitOfWork(Abstract<Module>UnitOfWork, AbstractSQLAlchemyUnitOfWork)`) that instantiates the repo inside `__aenter__`.
- `application/queries/` — read side. `*Queries(BaseQueries)` classes take a session directly (no UoW — reads don't need transactional write semantics) and build SQLAlchemy `Select` statements, applying filters/pagination, then map ORM rows to `application/queries/schemas.py` Pydantic response schemas via a `build_list`/`build` helper.
- `infrastructure/db/repos/` — `interface.py` defines an `abc.ABC` repo interface operating on aggregators; `repo.py` implements it against SQLAlchemy (`Repo(Abstract<X>Repo, BaseSqlAlchemyRepo)`), converting aggregator <-> ORM via `builders.py` (`build_orm`, `build`, `build_list`).
- `endpoints/` — `endpoints.py` defines the `APIRouter`; handlers build a command handler via `deps.py` (`deps.build_create_<x>_command_handler()` etc., wiring the concrete UoW), call `.handle(...)`, then open a fresh session via `async_session_factory` to run a query and return a response. `schemas.py` holds request bodies specific to this module's endpoints (distinct from `application/queries/schemas.py`, which holds response/filter schemas).

Cross-cutting base classes for the above live in `src/apps/web/core/`: `base.py` (`BaseSqlAlchemyRepo`), `unit_of_work.py` (`AbstractUnitOfWork`, `AbstractSQLAlchemyUnitOfWork`), `base_query.py` (`BaseQueries`, with `_apply_pagination`/`_model_to_dict` helpers), `schemas.py` (`BaseResponseSchema`/`BaseListResponseSchema` generic API envelopes), `deps.py` (`async_session_factory`).

Each request gets its own `AsyncSession`: commands open one implicitly inside the UoW (`session_factory()` in `__aenter__`); endpoint handlers open a second, separate one directly via `async_session_factory()` for the query that runs after a write. Sessions are not shared between the write and the follow-up read.

### Errors

Domain/application code raises typed exceptions from `apps.web.utils.exceptions` (`BaseCustomValidationError` -> 422, `BaseNotFoundError` -> 404, `BaseForbiddenError` -> 403) or subclasses defined per-module (e.g. `modules/transaction/application/commands/exceptions.py`). These are translated to RFC7807-style JSON responses (`BaseErrorResponseSchema` in `exception_handlers/base.py`) by handlers registered in `exception_handlers/`, wired up via `exception_handlers.setup(fastapi_app)` in `main.py`.

### Linting

`ruff` runs with `lint.select = ["ALL"]` plus an explicit ignore list — see `pyproject.toml`. Notable per-path relaxations: `src/tests/*` allows asserts/missing docstrings/private-member access; `src/migrations/*` allows missing docstrings. `mypy` runs in strict-ish mode (`disallow_untyped_defs`, `check_untyped_defs`, `no_implicit_reexport`) with the pydantic mypy plugin enabled.
