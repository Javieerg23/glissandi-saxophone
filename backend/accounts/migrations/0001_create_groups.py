"""Crea los grupos «administrador» y «usuario». / Creates the two role groups."""

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

GROUPS = ["administrador", "usuario"]


def create_groups(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Crea los grupos si no existen. / Creates the groups if missing."""
    group = apps.get_model("auth", "Group")
    for name in GROUPS:
        group.objects.get_or_create(name=name)


def delete_groups(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Borra los grupos. / Deletes the groups."""
    apps.get_model("auth", "Group").objects.filter(name__in=GROUPS).delete()


class Migration(migrations.Migration):
    """Datos iniciales de roles. / Initial role data."""

    dependencies = [("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(create_groups, delete_groups)]
