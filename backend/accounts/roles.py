"""Roles de la aplicación. / Application roles."""

from django.contrib.auth.models import AnonymousUser, User

ADMIN_GROUP = "administrador"
USER_GROUP = "usuario"


def is_administrator(user: User | AnonymousUser) -> bool:
    """Indica si el usuario pertenece al grupo administrador.

    Whether the user belongs to the administrator group.
    """
    return user.is_authenticated and user.groups.filter(name=ADMIN_GROUP).exists()


def role_of(user: User) -> str:
    """Devuelve el nombre del rol del usuario autenticado.

    Returns the role name of an authenticated user.
    """
    return ADMIN_GROUP if is_administrator(user) else USER_GROUP
