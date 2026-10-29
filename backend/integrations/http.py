"""Cliente HTTP común a todas las integraciones.

Shared HTTP client for every integration.
"""

from collections.abc import Mapping
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

USER_AGENT = "Glissandi/0.1 (+https://github.com/Javieerg23/glissandi-saxophone)"
DEFAULT_TIMEOUT = 10.0

_RETRY = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=(429, 500, 502, 503, 504),
    # Solo métodos idempotentes: reintentar un POST podría duplicar su efecto.
    # Idempotent methods only: retrying a POST could repeat its side effect.
    allowed_methods=("GET", "HEAD"),
)


class _TimeoutAdapter(HTTPAdapter):
    """Adaptador que aplica un tiempo de espera cuando la llamada no indica uno.

    Adapter that applies a timeout when the call does not set one. ``requests``
    has no session-wide timeout, and a missing one can hang a worker forever.
    """

    def __init__(self, timeout: float, **kwargs: Any) -> None:
        """Guarda el tiempo de espera por defecto. / Stores the default timeout."""
        self._timeout = timeout
        super().__init__(**kwargs)

    def send(
        self,
        request: requests.PreparedRequest,
        stream: bool = False,
        timeout: None | float | tuple[float, float] | tuple[float, None] = None,
        verify: bool | str = True,
        cert: None | bytes | str | tuple[bytes | str, bytes | str] = None,
        proxies: Mapping[str, str] | None = None,
    ) -> requests.Response:
        """Envía la petición con tiempo de espera. / Sends the request with a timeout."""
        if timeout is None:
            timeout = self._timeout
        return super().send(request, stream, timeout, verify, cert, proxies)


def build_session(
    user_agent: str = USER_AGENT, timeout: float = DEFAULT_TIMEOUT
) -> requests.Session:
    """Crea una sesión con tiempo de espera, reintentos y ``User-Agent`` propio.

    Builds a session with a timeout, retries and the project's ``User-Agent``.

    Args:
        user_agent: Cabecera ``User-Agent`` a enviar. / ``User-Agent`` header to send.
        timeout: Segundos de espera por petición. / Seconds to wait per request.

    Returns:
        Sesión lista para usar con ``http://`` y ``https://``.
        Session ready for ``http://`` and ``https://``.
    """
    session = requests.Session()
    session.headers["User-Agent"] = user_agent
    adapter = _TimeoutAdapter(timeout, max_retries=_RETRY)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
