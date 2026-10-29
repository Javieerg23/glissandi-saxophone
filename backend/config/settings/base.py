"""Ajustes comunes a todos los entornos.

Common settings shared by every environment.
"""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Sin valor por defecto: arrancar sin clave secreta debe fallar, no ser inseguro.
# No default: starting without a secret key must fail rather than run insecurely.
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
DEBUG = False
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "django_filters",
    "simple_history",
    "django_db_logger",
    "core",
    "accounts",
    "catalog",
    "jobs",
    "watches",
    "proxies",
    "activity",
    "preferences",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Después de la sesión y antes de CommonMiddleware, como exige Django.
    # After the session and before CommonMiddleware, as Django requires.
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Un único punto de configuración del motor: SQLite o PostgreSQL según la URL.
# Single engine switch: SQLite or PostgreSQL depending on the URL.
DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
    )
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Español primero; el inglés se elige con la cabecera Accept-Language.
# Spanish first; English is selected through the Accept-Language header.
LANGUAGE_CODE = "es"
LANGUAGES = [("es", "Español"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Glissandi API",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Cada bloque lo edita un único módulo; así los cambios en paralelo no chocan.
# Each block is edited by a single module so parallel changes do not collide.

# --- Seguridad y cuentas / Security and accounts ---

# --- Logs / Logging ---

# Con el formateador activo el mensaje guardado en base de datos incluye la tarea.
# With the formatter on, the message stored in the database includes the job id.
DJANGO_DB_LOGGER_ENABLE_FORMATTER = True
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "job_id": {"()": "activity.logs.JobIdFilter"},
        # Los filtros van en cada handler: los de un logger no afectan a los hijos.
        # Filters sit on each handler: a logger's filters do not apply to its children.
        "sensitive": {"()": "activity.logs.SensitiveDataFilter"},
    },
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s [job %(job_id)s] %(name)s: %(message)s"},
        "db": {"format": "[job %(job_id)s] %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
            "filters": ["job_id", "sensitive"],
        },
        "db": {
            "class": "django_db_logger.db_log_handler.DatabaseLogHandler",
            "level": "INFO",
            "formatter": "db",
            "filters": ["job_id", "sensitive"],
        },
    },
    "root": {"handlers": ["console", "db"], "level": "INFO"},
}

# --- Tareas / Tasks ---

# --- Historial / History ---
