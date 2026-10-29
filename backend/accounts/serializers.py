"""Serializadores de cuentas. / Account serializers."""

from typing import Any

from django.contrib.auth import password_validation
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


class CredentialsSerializer(serializers.Serializer[Any]):
    """Usuario y contraseña de entrada. / Username and password input."""

    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class NewAccountSerializer(CredentialsSerializer):
    """Alta de la primera cuenta; valida usuario y contraseña con las reglas de Django.

    First account creation, validated with Django's own rules.
    """

    def validate_username(self, value: str) -> str:
        """Aplica las reglas de nombre de usuario del modelo. / Applies model username rules."""
        user = User(username=value)
        user.full_clean(exclude=["password"], validate_unique=False)
        return value

    def validate_password(self, value: str) -> str:
        """Aplica los validadores de contraseña. / Applies password validators."""
        password_validation.validate_password(value)
        return value


class _CurrentPasswordSerializer(serializers.Serializer[Any]):
    """Pide la contraseña actual: una sesión robada no basta para cambiar credenciales.

    Requires the current password so a hijacked session cannot change credentials.
    """

    current_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_current_password(self, value: str) -> str:
        """Comprueba la contraseña del usuario de la petición. / Checks the caller's password."""
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError(_("La contraseña actual no es correcta."))
        return value


class PasswordChangeSerializer(_CurrentPasswordSerializer):
    """Cambio de contraseña. / Password change."""

    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_new_password(self, value: str) -> str:
        """Aplica los validadores de contraseña. / Applies password validators."""
        password_validation.validate_password(value, self.context["request"].user)
        return value


class UsernameChangeSerializer(_CurrentPasswordSerializer):
    """Cambio de nombre de usuario. / Username change."""

    username = serializers.CharField(max_length=150)

    def validate_username(self, value: str) -> str:
        """Aplica reglas del modelo y unicidad. / Applies model rules and uniqueness."""
        user = self.context["request"].user
        user.username = value
        user.full_clean(exclude=["password"])
        return value
