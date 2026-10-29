"""Tests del cliente HTTP común. / Tests for the shared HTTP client."""

from typing import Any

import responses
from requests.adapters import HTTPAdapter

from integrations.http import DEFAULT_TIMEOUT, USER_AGENT, build_session


def _timeout_sent() -> Any:
    """Tiempo de espera de la última petición. / Timeout of the last request."""
    return getattr(responses.calls[-1].request, "req_kwargs")["timeout"]  # noqa: B009


@responses.activate
def test_sends_project_user_agent() -> None:
    responses.get("https://api.example.test/x", json={})
    build_session().get("https://api.example.test/x")
    assert responses.calls[0].request.headers["User-Agent"] == USER_AGENT


@responses.activate
def test_custom_user_agent() -> None:
    responses.get("https://api.example.test/x", json={})
    build_session(user_agent="Otro/1.0").get("https://api.example.test/x")
    assert responses.calls[0].request.headers["User-Agent"] == "Otro/1.0"


@responses.activate
def test_applies_default_timeout() -> None:
    responses.get("https://api.example.test/x", json={})
    build_session().get("https://api.example.test/x")
    assert _timeout_sent() == DEFAULT_TIMEOUT


@responses.activate
def test_explicit_timeout_wins() -> None:
    responses.get("https://api.example.test/x", json={})
    build_session().get("https://api.example.test/x", timeout=2)
    assert _timeout_sent() == 2


def test_retries_only_idempotent_methods_on_transient_errors() -> None:
    adapter = build_session().get_adapter("https://api.example.test")
    assert isinstance(adapter, HTTPAdapter)
    retry = adapter.max_retries
    assert retry.total == 3
    assert 503 in retry.status_forcelist
    assert retry.allowed_methods == ("GET", "HEAD")
