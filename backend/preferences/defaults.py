"""Valores por defecto de las preferencias. / Default preference values.

Viven en código para que un ajuste nunca dependa de que exista una fila en la
base de datos. Los hilos de cada funcionalidad añaden aquí sus claves.

Kept in code so a setting never depends on a database row existing. Each
feature adds its keys here.
"""

from typing import Final

from integrations.audio import DEFAULT_TEMPLATE

DEFAULTS: Final[dict[str, object]] = {
    "download.format": "mp3",
    "download.folder": "music",
    "download.name_template": DEFAULT_TEMPLATE,
}
