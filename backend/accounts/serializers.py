"""Serializadores de cuentas. / Account serializers."""

from typing import Any

from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .roles import ADMIN_GROUP, USER_GROUP, role_of


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
        request = self.context["request"]
        # Por ``authenticate`` y no ``check_password``: así django-axes cuenta los fallos y
        # una sesión robada no sirve para adivinar la clave sin límite.
        # Through ``authenticate``, not ``check_password``, so django-axes counts failures
        # and a hijacked session cannot guess the password without limit.
        user = authenticate(request._request, username=request.user.get_username(), password=value)
        if user is None:
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


class ProfileSerializer(serializers.Serializer[Any]):
    """Usuario con sesión y su rol. / Signed-in user and role."""

    username = serializers.CharField()
    role = serializers.ChoiceField(choices=[ADMIN_GROUP, USER_GROUP])


class MeSerializer(ProfileSerializer):
    """Perfil con los intentos fallidos desde el último inicio de sesión.

    Profile with the failed attempts since the last successful sign-in.
    """

    failed_attempts = serializers.IntegerField()


class SetupStatusSerializer(serializers.Serializer[Any]):
    """Si falta crear el primer administrador. / Whether the first admin is still missing."""

    needed = serializers.BooleanField()


class ManagedUserSerializer(serializers.ModelSerializer[User]):
    """Usuario tal como lo gestiona un administrador. / User as an administrator manages it."""

    role = serializers.SerializerMethodField()

    class Meta:
        """Solo los campos de gestión. / Management fields only."""

        model = User
        fields = ["id", "username", "role", "is_active", "last_login", "date_joined"]
        read_only_fields = ["id", "last_login", "date_joined"]

    def get_role(self, obj: User) -> str:
        """Devuelve el rol del usuario. / Returns the user's role."""
        return role_of(obj)


class ManagedUserCreateSerializer(NewAccountSerializer):
    """Alta de un usuario con rol por un administrador. / Administrator-made account with a role."""

    role = serializers.ChoiceField(choices=[ADMIN_GROUP, USER_GROUP], default=USER_GROUP)

    def validate_username(self, value: str) -> str:
        """Aplica las reglas del modelo y que no exista ya. / Applies model rules and uniqueness."""
        value = super().validate_username(value)
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(_("Ese nombre de usuario ya existe."))
        return value


class ManagedUserUpdateSerializer(serializers.Serializer[Any]):
    """Cambios parciales: rol y activo. / Partial changes: role and active flag."""

    role = serializers.ChoiceField(choices=[ADMIN_GROUP, USER_GROUP], required=False)
    is_active = serializers.BooleanField(required=False)
