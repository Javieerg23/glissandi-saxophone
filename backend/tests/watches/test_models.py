"""Tests de los modelos de ``watches``. / Tests for ``watches`` models."""

import pytest
from django.db.models import ProtectedError

from core.models import AppendOnlyError
from watches.models import Watch, WatchRun

pytestmark = pytest.mark.django_db


def _run(watch: Watch) -> WatchRun:
    """Crea una ejecución mínima. / Creates a minimal run."""
    run = WatchRun(watch=watch, status=WatchRun.Status.SUCCEEDED)
    run.save()
    return run


def test_watch_name_is_unique() -> None:
    Watch.objects.create(name="novedades")
    with pytest.raises(Exception, match="UNIQUE|unique"):
        Watch.objects.create(name="novedades")


def test_watch_change_is_recorded_in_history() -> None:
    watch = Watch.objects.create(name="novedades")
    watch.enabled = False
    watch.save()
    assert watch.history.count() == 2


def test_run_is_inserted_and_readable() -> None:
    run = _run(Watch.objects.create(name="novedades"))
    run.refresh_from_db()
    assert run.status == WatchRun.Status.SUCCEEDED
    assert run.found == 0


def test_run_save_on_existing_row_is_rejected() -> None:
    run = _run(Watch.objects.create(name="novedades"))
    run.found = 3
    with pytest.raises(AppendOnlyError):
        run.save()


def test_run_delete_is_rejected() -> None:
    run = _run(Watch.objects.create(name="novedades"))
    with pytest.raises(AppendOnlyError):
        run.delete()


def test_watch_with_runs_cannot_be_deleted() -> None:
    watch = Watch.objects.create(name="novedades")
    _run(watch)
    with pytest.raises(ProtectedError):
        watch.delete()


def test_watch_str_is_its_name() -> None:
    assert str(Watch(name="novedades")) == "novedades"


def test_watch_run_admin_is_read_only() -> None:
    from django.contrib.admin import site

    model_admin = site._registry[WatchRun]
    request = None
    assert model_admin.has_add_permission(request) is False  # type: ignore[arg-type]
    assert model_admin.has_change_permission(request) is False  # type: ignore[arg-type]
    assert model_admin.has_delete_permission(request) is False  # type: ignore[arg-type]
