"""Planificador periódico sencillo. / Simple periodic scheduler.

One daemon thread wakes up every minute and runs whatever is due. It is meant
for short maintenance calls; long work should be started as a task from them.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)

CHECK_EVERY_SECONDS = 60


@dataclass
class _Periodic:
    """Función periódica y cuándo toca de nuevo. / Periodic function and when it is next due."""

    func: Callable[[], object]
    interval: timedelta
    next_run: datetime


_periodics: dict[str, _Periodic] = {}
_thread: threading.Thread | None = None
_stop_event = threading.Event()


def register_periodic(name: str, interval: timedelta, func: Callable[[], object]) -> None:
    """Registra ``func`` para ejecutarla cada ``interval``.

    Registers ``func`` to run every ``interval``. The first run happens on the
    first check after startup, so a server restarted often still gets it.

    Raises:
        ValueError: Si ``name`` ya está registrado. / If ``name`` is already registered.
    """
    if name in _periodics:
        raise ValueError(f"La tarea periódica «{name}» ya está registrada.")
    _periodics[name] = _Periodic(func, interval, timezone.now())


def run_due(now: datetime | None = None) -> None:
    """Ejecuta las funciones que ya tocan; un fallo no afecta a las demás.

    Runs the functions that are due; a failure does not affect the others.
    """
    now = now or timezone.now()
    for name, periodic in _periodics.items():
        if periodic.next_run > now:
            continue
        periodic.next_run = now + periodic.interval
        try:
            periodic.func()
        except Exception:
            logger.exception("Falló la tarea periódica %s", name)


def _loop() -> None:
    """Bucle del hilo hasta que se pida parar. / Thread loop until a stop is requested."""
    try:
        while not _stop_event.is_set():
            run_due()
            _stop_event.wait(CHECK_EVERY_SECONDS)
    finally:
        connection.close()


def start() -> None:
    """Arranca el hilo si no está en marcha. / Starts the thread if it is not running."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, name="job-scheduler", daemon=True)
    _thread.start()


def stop() -> None:
    """Pide parar el hilo y espera a que acabe. / Asks the thread to stop and waits for it."""
    _stop_event.set()
    if _thread is not None:
        _thread.join()
