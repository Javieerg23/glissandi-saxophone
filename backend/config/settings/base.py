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

REST_FRAMEWORK: dict[str, object] = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
SPECTACULAR_SETTINGS = {
    "TITLE": "Glissandi API",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Un tipo para lo que se envía y otro para lo que se recibe (p. ej. campos write_only).
    # Separate types for what is sent and what is received (e.g. write_only fields).
    "COMPONENT_SPLIT_REQUEST": True,
}

# Cada bloque lo edita un único módulo; así los cambios en paralelo no chocan.
# Each block is edited by a single module so parallel changes do not collide.

# --- Seguridad y cuentas / Security and accounts ---

from datetime import timedelta  # noqa: E402

from django.utils.csp import CSP  # noqa: E402

INSTALLED_APPS += ["axes"]
# Axes va el último: debe ver la respuesta final para bloquear. La CSP, tras la seguridad.
# Axes goes last so it sees the final response. CSP right after the security middleware.
MIDDLEWARE.insert(1, "django.middleware.csp.ContentSecurityPolicyMiddleware")
MIDDLEWARE.append("axes.middleware.AxesMiddleware")
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
# Bloqueo por usuario *y* origen: un atacante no deja fuera a la víctima desde otra IP.
# Lock per user *and* origin so an attacker cannot lock the victim out from elsewhere.
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True

# DRF: sesión + CSRF por cabecera (X-CSRFToken), y todo cerrado salvo que la vista diga otra cosa.
# DRF: session + CSRF header, and closed unless a view says otherwise.
REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = [
    "rest_framework.authentication.SessionAuthentication"
]
REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = ["rest_framework.permissions.IsAuthenticated"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{name}"}
    for name in (
        "UserAttributeSimilarityValidator",
        "MinimumLengthValidator",
        "CommonPasswordValidator",
        "NumericPasswordValidator",
    )
]

SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
# El frontend lee la cookie CSRF y la reenvía en la cabecera, así que no puede ser HttpOnly.
# The frontend reads the CSRF cookie and echoes it in a header, so it cannot be HttpOnly.
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"

# Detrás de un proxy que termina TLS hay que fiarse de su cabecera, o la redirección a HTTPS
# entra en bucle. Solo se activa si el despliegue lo declara.
# Behind a TLS-terminating proxy, trust its header or the HTTPS redirect loops. Opt-in only.
if os.environ.get("DJANGO_TRUST_PROXY_SSL_HEADER") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"

# Sin 'unsafe-inline' ni 'unsafe-eval': el front compilado con Vite solo carga ficheros propios.
# No 'unsafe-inline'/'unsafe-eval': the Vite build only loads same-origin files.
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF],
    # Las portadas vienen de CDN externos (Deezer, Cover Art Archive).
    # Covers come from external CDNs (Deezer, Cover Art Archive).
    "img-src": [CSP.SELF, "data:", "https:"],
    "frame-src": ["https://www.youtube-nocookie.com"],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
}

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
    # Axes escribe un INFO al arrancar (ready()), antes de que exista la tabla de logs en una
    # base de datos nueva; los bloqueos y fallos de acceso salen como WARNING y se siguen guardando.
    # Axes logs an INFO line in ready(), before the log table exists on a fresh database;
    # lockouts and failed logins are WARNING and are still stored.
    "loggers": {"axes": {"level": "WARNING"}},
}

# --- Tareas / Tasks ---

# Hilos del ejecutor: como mucho una tarea por tipo, así que basta con unos pocos.
# Executor threads: at most one task per kind runs, so a few are plenty.
JOBS_MAX_WORKERS = 4
# Con True las tareas se ejecutan en el mismo hilo que las lanza (tests).
# When True tasks run in the calling thread (tests).
JOBS_SYNCHRONOUS = False

# --- Historial / History ---
