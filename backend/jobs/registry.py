"""Registro de tipos de tarea. / Task type registry.

Each app adds its tasks in its own ``<app>/tasks/`` modules; they are imported
once at startup (see ``JobsConfig.ready``), so nothing shared has to change.
"""

from collections.abc import Callable
from typing import Any

from jobs.models import JobRun

#: Una tarea recibe su ejecución y sus parámetros y devuelve el resumen final.
#: A task takes its run and params and returns the final summary.
TaskFunc = Callable[[JobRun, dict[str, Any]], dict[str, Any] | None]

_tasks: dict[str, TaskFunc] = {}


class UnknownJobKind(KeyError):
    """No hay ninguna tarea registrada con ese tipo. / No task is registered under that kind."""


def register(kind: str) -> Callable[[TaskFunc], TaskFunc]:
    """Decorador que registra una función como tarea de tipo ``kind``.

    Decorator registering a function as the task of type ``kind``.

    Args:
        kind: Identificador estable del tipo (se guarda en ``JobRun.kind``).
            Stable type identifier (stored in ``JobRun.kind``).

    Raises:
        ValueError: Si el tipo ya está registrado. / If the kind is already registered.
    """

    def decorator(func: TaskFunc) -> TaskFunc:
        if kind in _tasks:
            raise ValueError(f"El tipo de tarea «{kind}» ya está registrado.")
        _tasks[kind] = func
        return func

    return decorator


def get(kind: str) -> TaskFunc:
    """Devuelve la función de un tipo. / Returns the function for a kind.

    Raises:
        UnknownJobKind: Si el tipo no existe. / If the kind does not exist.
    """
    try:
        return _tasks[kind]
    except KeyError:
        raise UnknownJobKind(kind) from None


def kinds() -> list[str]:
    """Lista los tipos registrados, ordenados. / Lists registered kinds, sorted."""
    return sorted(_tasks)
