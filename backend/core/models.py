"""Modelos base compartidos. / Shared base models."""

from typing import Any, NoReturn

from django.db import models


class AppendOnlyError(Exception):
    """Se intentó modificar o borrar un registro de solo añadir.

    An append-only record was modified or deleted.
    """


class AppendOnlyQuerySet(models.QuerySet["AppendOnlyModel"]):
    """QuerySet que rechaza las escrituras en bloque que alteran filas existentes.

    QuerySet that rejects bulk writes which alter existing rows. ``bulk_update``
    goes through ``update()``, so it is covered too.
    """

    def update(self, **kwargs: Any) -> NoReturn:
        """Prohibido. / Forbidden."""
        raise AppendOnlyError("Los registros de solo añadir no se actualizan.")

    def delete(self) -> NoReturn:
        """Prohibido. / Forbidden."""
        raise AppendOnlyError("Los registros de solo añadir no se borran.")


class AppendOnlyModel(models.Model):
    """Base abstracta de tablas que solo admiten inserciones.

    Abstract base for tables that only accept inserts. The guarantee lives in
    Python, not in database triggers, so it behaves the same on every engine.
    """

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        """Sin tabla propia. / No table of its own."""

        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Guarda solo filas nuevas. / Saves new rows only."""
        if not self._state.adding:
            raise AppendOnlyError("Los registros de solo añadir no se modifican.")
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> NoReturn:
        """Prohibido. / Forbidden."""
        raise AppendOnlyError("Los registros de solo añadir no se borran.")
