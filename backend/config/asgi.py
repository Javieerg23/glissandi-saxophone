"""Punto de entrada ASGI. / ASGI entry point."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")

application = get_asgi_application()

# Tras cargar Django: toca la base de datos y arranca el planificador.
# After Django is loaded: touches the database and starts the scheduler.
from jobs.startup import start  # noqa: E402

start()
