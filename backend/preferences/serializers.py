"""Serializadores de ajustes. / Settings serializers."""

from collections.abc import Callable
from typing import Any

from django.utils.translation import gettext as _
from rest_framework import serializers

from integrations.audio import FORMATS, Tags, render_path

from .defaults import DEFAULTS


def _check_template(value: str) -> None:
    """Prueba la plantilla con una canción de ejemplo. / Tries the template on a sample track."""
    try:
        render_path(value, Tags(title="t", artists=("a",)), "mp3")
    except (KeyError, ValueError, IndexError, AttributeError) as error:
        raise serializers.ValidationError(_("La plantilla no es válida.")) from error


def _check_format(value: str) -> None:
    """Solo formatos que sabe producir la conversión. / Only formats conversion can produce."""
    if value not in FORMATS:
        raise serializers.ValidationError(_("Formato no admitido: %(value)s.") % {"value": value})


# Ajustes que la descarga usaría tal cual: un valor erróneo haría fallar todas.
# Settings downloads use as-is: a bad value would make every one fail.
_CHECKS: dict[str, Callable[[Any], None]] = {
    "download.format": _check_format,
    "download.name_template": _check_template,
}


class PreferenceSerializer(serializers.Serializer[dict[str, Any]]):
    """Ajuste con valor efectivo y por defecto. / Setting with effective and default value."""

    key = serializers.CharField(read_only=True)
    value = serializers.JSONField(read_only=True)
    default = serializers.JSONField(read_only=True)


class PreferenceWriteSerializer(serializers.Serializer[dict[str, Any]]):
    """Valor nuevo de un ajuste. / New value for a setting.

    Solo se admite el mismo tipo que el valor por defecto: así un ajuste no
    cambia de forma y el código que lo lee no tiene que defenderse de ello.
    Only the default's type is accepted, so a setting never changes shape and
    its readers need no defensive parsing.
    """

    value = serializers.JSONField()

    def validate_value(self, value: Any) -> Any:
        """Comprueba el tipo frente al valor por defecto. / Checks the type against the default.

        Args:
            value: Valor recibido. / Received value.

        Returns:
            El mismo valor si el tipo coincide. / The same value when the type matches.

        Raises:
            ValidationError: Si el tipo no coincide con el del valor por defecto.
        """
        expected = type(DEFAULTS[self.context["key"]])
        if type(value) is not expected:
            raise serializers.ValidationError(
                _("El valor debe ser de tipo %(type)s.") % {"type": expected.__name__}
            )
        if check := _CHECKS.get(self.context["key"]):
            check(value)
        return value
