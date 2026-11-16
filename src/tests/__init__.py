"""
Окружение тестов.

Настройки приложения читаются при импорте модулей `apps`, поэтому ключ проверки JWT и параметры БД
задаются здесь: пакет `tests` импортируется раньше `conftest.py` и тестовых модулей.
"""

import os
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _generate_rsa_key_pair() -> tuple[bytes, bytes]:
    """Сгенерировать пару ключей RSA в формате PEM: (приватный, публичный)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


PRIVATE_KEY, PUBLIC_KEY = _generate_rsa_key_pair()
# Ключ «чужого» сервиса: подписанные им токены сервис транзакций должен отклонять.
FOREIGN_PRIVATE_KEY, _ = _generate_rsa_key_pair()

_public_key_path = Path(tempfile.mkdtemp(prefix="fm-transaction-tests-")) / "jwt_public_key"
_public_key_path.write_bytes(PUBLIC_KEY)

os.environ.setdefault("WEB_SERVICE_NAME", "fm_transaction_service_tests")
os.environ["WEB_PUBLIC_KEY_PATH"] = str(_public_key_path)
os.environ["WEB_TOKEN_SIGNING_ALGORITHM"] = "RS256"  # noqa: S105 — имя алгоритма, не секрет
# Движок приложения создаётся при импорте, но не подключается к БД до первого запроса.
# Тесты с БД переключают фабрику сессий на Postgres из testcontainers (фикстура db_engine).
for _name, _value in {
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "DB_USERNAME": "postgres",
    "DB_PASSWORD": "postgres",
    "DB_DATABASE": "fm_transaction_service",
}.items():
    os.environ.setdefault(_name, _value)
