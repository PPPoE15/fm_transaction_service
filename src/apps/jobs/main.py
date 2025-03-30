from apps.jobs import config
from apps.jobs.bootstrap import dramatiq, logger

logger.setup()
# Сначала конфигурим dramatiq
dramatiq.setup()

if not config.app_settings.HEALTHCHECK_MODE:
    # Затем импортим модули с actor'ами, чтобы воркер dramatiq'а их видел при запуске main.py
    import apps.jobs.app.handlers.jobs  # noqa: F401
