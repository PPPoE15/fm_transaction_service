"""
Проверки модульной структуры сервиса (FM-30): «модули сверху, слои внутри».

Импорты читаются статически (AST), поэтому учитываются и импорты под `TYPE_CHECKING`.
"""

import ast
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

APPS_DIR = Path(__file__).parents[1] / "apps"
MODULES_DIR = APPS_DIR / "modules"
LAYERS = {"domain", "application", "infrastructure", "api"}
# Аутентификация — единственное, что модули берут из сборки приложения.
ALLOWED_WEB_IMPORTS = {"apps.web.security"}

OLD_LAYER_DIRS = [
    "web/modules",
    "web/core",
    "web/utils",
    "web/connectors",
    "db_models/models",
    "db_models/utils",
    "apps_types",
    "utils",
]


def _module_name(path: Path) -> str:
    relative = path.relative_to(APPS_DIR.parent).with_suffix("")
    parts = relative.parts[:-1] if relative.name == "__init__" else relative.parts
    return ".".join(parts)


def _imports(path: Path) -> Iterator[str]:
    """Абсолютные имена всего, что импортирует файл (относительные импорты разрешаются)."""
    package = _module_name(path) if path.name == "__init__.py" else _module_name(path).rpartition(".")[0]
    return _imports_from_source(path.read_text(encoding="utf-8"), package)


def _imports_from_source(source: str, package: str) -> Iterator[str]:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = package.split(".")
                base = ".".join(base_parts[: len(base_parts) - node.level + 1])
                target = f"{base}.{node.module}" if node.module else base
            else:
                target = node.module or ""
            # Импортируются имена из пакета, а не сам пакет: `from apps.web import security` -> `apps.web.security`,
            # `from apps.modules import category` -> `apps.modules.category`.
            yield from (f"{target}.{alias.name}" for alias in node.names)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("from apps.web import security", ["apps.web.security"]),
        ("from apps.web.security import UserInfo", ["apps.web.security.UserInfo"]),
        ("from . import schemas", ["apps.modules.category.api.schemas"]),
        ("from apps.modules import category", ["apps.modules.category"]),
        ("import sqlalchemy", ["sqlalchemy"]),
    ],
)
def test_imports_from_source_names_imported_objects(source: str, expected: list[str]) -> None:
    """`from X import y` даёт `X.y`, а не голый пакет `X` (иначе `from apps.web import security` — нарушение)."""
    assert list(_imports_from_source(source, "apps.modules.category.api")) == expected


def _python_files(directory: Path) -> list[Path]:
    return sorted(directory.rglob("*.py"))


def _module_names() -> list[str]:
    if not MODULES_DIR.is_dir():
        return []
    return sorted(p.name for p in MODULES_DIR.iterdir() if p.is_dir() and not p.name.startswith("__"))


def _owner_module(name: str) -> str | None:
    parts = name.split(".")
    if parts[:2] == ["apps", "modules"] and len(parts) > 2:  # noqa: PLR2004
        return parts[2]
    return None


def _module_dependencies() -> dict[str, set[str]]:
    deps: dict[str, set[str]] = {module: set() for module in _module_names()}
    for module, module_deps in deps.items():
        for path in _python_files(MODULES_DIR / module):
            for name in _imports(path):
                target = _owner_module(name)
                if target and target != module and target in deps:
                    module_deps.add(target)
    return deps


@pytest.mark.parametrize("old_dir", OLD_LAYER_DIRS)
def test_old_layer_directories_are_gone(old_dir: str) -> None:
    """Каталогов старой раскладки «слои сверху» не осталось."""
    assert not (APPS_DIR / old_dir).exists(), f"apps/{old_dir} остался после перехода на модули"


def test_modules_exist() -> None:
    """Модули сервиса — статьи и транзакции."""
    assert _module_names() == ["category", "transaction"]


@pytest.mark.parametrize("module", ["category", "transaction"])
def test_module_contains_only_layers(module: str) -> None:
    """Внутри модуля — только слои domain, application, infrastructure, api."""
    module_dir = MODULES_DIR / module
    assert (module_dir / "__init__.py").is_file()
    entries = {p.name for p in module_dir.iterdir() if p.name not in {"__init__.py", "__pycache__"}}
    assert entries == LAYERS


def test_modules_import_each_other_only_through_public_api() -> None:
    """Модуль берёт из другого модуля только имена из его `__init__.__all__`."""
    violations = []
    for module in _module_names():
        for path in _python_files(MODULES_DIR / module):
            for name in _imports(path):
                target = _owner_module(name)
                if not target or target == module:
                    continue
                # Допустимо `apps.modules.category` и имена из его `__all__` (`apps.modules.category.Category`).
                rest = name.removeprefix(f"apps.modules.{target}").lstrip(".")
                if rest and rest not in _public_names(target):
                    violations.append(f"{path.relative_to(APPS_DIR)}: {name}")
    assert violations == []


def _public_names(module: str) -> set[str]:
    return _all_names((MODULES_DIR / module / "__init__.py").read_text(encoding="utf-8"))


def _all_names(source: str) -> set[str]:
    """Имена из `__all__` модуля."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets):
            return set(ast.literal_eval(value))
    return set()


@pytest.mark.parametrize(
    "source",
    [
        "__all__ = ['Category', 'CategoryRepo']",
        "__all__: list[str] = ['Category', 'CategoryRepo']",
    ],
)
def test_all_names_reads_plain_and_annotated_all(source: str) -> None:
    """`__all__` читается и в обычном, и в аннотированном присваивании."""
    assert _all_names(source) == {"Category", "CategoryRepo"}


def test_no_cycles_between_modules() -> None:
    """Зависимости между модулями без циклов."""
    deps = _module_dependencies()
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(module: str, path: list[str]) -> None:
        if module in done:
            return
        assert module not in visiting, f"Цикл зависимостей модулей: {' -> '.join([*path, module])}"
        visiting.add(module)
        for dep in deps[module]:
            visit(dep, [*path, module])
        visiting.discard(module)
        done.add(module)

    for module in deps:
        visit(module, [])


def test_transaction_depends_on_category_not_vice_versa() -> None:
    """Транзакции зависят от статей, статьи о транзакциях не знают."""
    deps = _module_dependencies()
    assert deps == {"category": set(), "transaction": {"category"}}


def test_shared_does_not_import_modules_or_web() -> None:
    """Общее ядро не зависит от модулей, реестра ORM и сборки приложения."""
    violations = [
        f"{path.relative_to(APPS_DIR)}: {name}"
        for path in _python_files(APPS_DIR / "shared")
        for name in _imports(path)
        if name.startswith(("apps.modules", "apps.web", "apps.db_models"))
    ]
    assert _python_files(APPS_DIR / "shared")
    assert violations == []


def test_modules_import_from_web_only_security() -> None:
    """Из сборки приложения модули берут только аутентификацию."""
    violations = [
        f"{path.relative_to(APPS_DIR)}: {name}"
        for path in _python_files(MODULES_DIR)
        for name in _imports(path)
        if name.startswith("apps.web")
        and name not in ALLOWED_WEB_IMPORTS
        and name.rpartition(".")[0] not in ALLOWED_WEB_IMPORTS
    ]
    assert violations == []


@pytest.mark.parametrize("module", ["category", "transaction"])
def test_domain_does_not_depend_on_other_layers(module: str) -> None:
    """Домен не зависит от других слоёв модуля, БД и HTTP."""
    other_layers = tuple(f"apps.modules.{module}.{layer}" for layer in LAYERS - {"domain"})
    violations = [
        f"{path.relative_to(APPS_DIR)}: {name}"
        for path in _python_files(MODULES_DIR / module / "domain")
        for name in _imports(path)
        if name.startswith(other_layers) or name.startswith(("sqlalchemy", "fastapi"))
    ]
    assert violations == []


def test_api_is_imported_only_by_web() -> None:
    """HTTP-слой модуля подключает только сборка приложения."""
    violations = [
        f"{path.relative_to(APPS_DIR)}: {name}"
        for path in _python_files(APPS_DIR)
        if not path.is_relative_to(APPS_DIR / "web")
        for name in _imports(path)
        if (module := _owner_module(name))
        and name.startswith(f"apps.modules.{module}.api")
        and not path.is_relative_to(MODULES_DIR / module / "api")
    ]
    assert violations == []


@pytest.mark.parametrize("module", ["category", "transaction"])
def test_repo_interfaces_live_in_application_ports(module: str) -> None:
    """Интерфейсы репозиториев — в `application/ports.py`, реализации — в инфраструктуре."""
    module_dir = MODULES_DIR / module
    assert (module_dir / "infrastructure" / "repo.py").is_file()
    assert (module_dir / "application" / "ports.py").is_file()


def _orm_tables() -> set[str]:
    """Имена таблиц (`__tablename__`) из `infrastructure/orm.py` всех модулей."""
    tables: set[str] = set()
    for orm in sorted(MODULES_DIR.glob("*/infrastructure/orm.py")):
        for node in ast.walk(ast.parse(orm.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "__tablename__" for target in node.targets)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                tables.add(node.value.value)
    return tables


def test_db_models_registry_registers_all_tables() -> None:
    """
    Реестр ORM регистрирует таблицы всех модулей (на нём держится autogenerate Alembic).

    Проверяется в отдельном процессе: в процессе тестов модели уже загружены через `apps.web.main` (conftest),
    и пропущенный в реестре модуль там не заметен.
    """
    code = "import json; from apps.db_models import AsyncBase; print(json.dumps(sorted(AsyncBase.metadata.tables)))"
    result = subprocess.run(  # noqa: S603 — фиксированная команда, без пользовательского ввода
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=APPS_DIR.parent,
        env={**os.environ, "PYTHONPATH": str(APPS_DIR.parent)},
    )
    assert _orm_tables() >= {"categories", "transactions"}
    assert set(json.loads(result.stdout)) == _orm_tables()
