"""Tests del endpoint de estado. / Health endpoint tests."""

from django.test import Client


def test_health_responde_en_español_por_defecto(client: Client) -> None:
    """Sin Accept-Language el mensaje sale en español."""
    response = client.get("/api/health/")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["message"] == "El servicio funciona."


def test_health_respeta_accept_language(client: Client) -> None:
    """Con Accept-Language: en el mensaje sale en inglés."""
    response = client.get("/api/health/", headers={"accept-language": "en"})

    assert response.json()["message"] == "The service is working."


def test_schema_openapi_disponible(client: Client) -> None:
    """El esquema OpenAPI se genera sin errores."""
    assert client.get("/api/schema/").status_code == 200
