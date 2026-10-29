"""Valores por defecto de las preferencias. / Default preference values.

Viven en código para que un ajuste nunca dependa de que exista una fila en la
base de datos. Los hilos de cada funcionalidad añaden aquí sus claves.

Kept in code so a setting never depends on a database row existing. Each
feature adds its keys here.
"""

from typing import Final

DEFAULTS: Final[dict[str, object]] = {}
