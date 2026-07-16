from __future__ import annotations

import threading
from typing import Any, Mapping

import httpx

from sentinel_combination.ports.broker import (
    BrokerAuthenticationError,
    BrokerRejected,
    BrokerUnknownOutcome,
)


class HttpBrokerMixin:
    def __init__(self) -> None:
        self._http: httpx.Client | None = None
        self._http_lock = threading.RLock()

    def _make_http(
        self,
        *,
        base_url: str,
        headers: Mapping[str, str] | None = None,
        timeout: float = 15.0,
    ) -> httpx.Client:
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=dict(headers or {}),
            timeout=timeout,
        )
        return self._http

    def _close_http(self) -> None:
        with self._http_lock:
            if self._http is not None:
                self._http.close()
            self._http = None

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
        data: Any = None,
        headers: Mapping[str, str] | None = None,
        unknown_on_timeout: bool = False,
    ) -> httpx.Response:
        if self._http is None:
            raise BrokerAuthenticationError("HTTP broker is not connected")
        try:
            response = self._http.request(
                method,
                path,
                params=params,
                json=json,
                data=data,
                headers=headers,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            if unknown_on_timeout:
                raise BrokerUnknownOutcome(str(exc)) from exc
            raise BrokerAuthenticationError(str(exc)) from exc
        if response.status_code in {401, 403}:
            raise BrokerAuthenticationError(response.text)
        if response.status_code >= 400:
            raise BrokerRejected(
                response.text or f"HTTP {response.status_code}",
                code=str(response.status_code),
            )
        return response
