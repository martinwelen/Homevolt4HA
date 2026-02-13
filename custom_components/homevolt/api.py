"""API client for communicating with the Homevolt local HTTP API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import (
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_READ_TIMEOUT,
    ENDPOINT_EMS,
    ENDPOINT_ERROR_REPORT,
    ENDPOINT_STATUS,
)
from .models import (
    ErrorReportEntry,
    HomevoltEmsResponse,
    HomevoltStatusResponse,
)

_LOGGER = logging.getLogger(__name__)

RETRY_STATUS_CODES = {502, 503, 504}
MAX_RETRIES = 3
BACKOFF_BASE = 2  # seconds


class HomevoltApiError(Exception):
    """Base exception for Homevolt API errors."""


class HomevoltConnectionError(HomevoltApiError):
    """Error connecting to the Homevolt device."""


class HomevoltAuthError(HomevoltApiError):
    """Authentication error."""


class HomevoltApiClient:
    """Client for the Homevolt local HTTP API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        password: str | None = None,
        port: int = 80,
        use_ssl: bool = False,
        connect_timeout: int = DEFAULT_CONNECT_TIMEOUT,
        read_timeout: int = DEFAULT_READ_TIMEOUT,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._host = host
        self._port = port
        self._password = password
        self._use_ssl = use_ssl
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        scheme = "https" if use_ssl else "http"
        self._base_url = f"{scheme}://{host}:{port}"

    @property
    def host(self) -> str:
        """Return the host."""
        return self._host

    async def _request(self, endpoint: str, method: str = "GET", **kwargs: Any) -> dict | list:
        """Make an HTTP request with retry logic."""
        url = f"{self._base_url}{endpoint}"
        auth = None
        if self._password:
            auth = aiohttp.BasicAuth("admin", self._password)

        timeout = aiohttp.ClientTimeout(
            connect=self._connect_timeout,
            total=self._read_timeout,
        )

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                async with self._session.request(
                    method, url, auth=auth, timeout=timeout, **kwargs
                ) as resp:
                    if resp.status == 401:
                        raise HomevoltAuthError("Invalid credentials")
                    if resp.status in RETRY_STATUS_CODES:
                        last_error = HomevoltApiError(
                            f"Server error {resp.status} from {endpoint}"
                        )
                        if attempt < MAX_RETRIES - 1:
                            await asyncio.sleep(BACKOFF_BASE ** (attempt + 1))
                            continue
                        raise last_error
                    resp.raise_for_status()
                    return await resp.json()
            except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as err:
                last_error = HomevoltConnectionError(
                    f"Connection error to {self._host}: {err}"
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BACKOFF_BASE ** (attempt + 1))
                    continue
                raise last_error from err

        # Should not reach here, but just in case
        raise last_error or HomevoltApiError("Unknown error")

    async def async_get_ems_data(self) -> HomevoltEmsResponse:
        """Fetch EMS data from /ems.json."""
        data = await self._request(ENDPOINT_EMS)
        return HomevoltEmsResponse.from_dict(data)

    async def async_get_status(self) -> HomevoltStatusResponse:
        """Fetch system status from /status.json."""
        data = await self._request(ENDPOINT_STATUS)
        return HomevoltStatusResponse.from_dict(data)

    async def async_get_error_report(self) -> list[ErrorReportEntry]:
        """Fetch error report from /error_report.json."""
        data = await self._request(ENDPOINT_ERROR_REPORT)
        return [ErrorReportEntry.from_dict(e) for e in data]

    async def async_validate_connection(self) -> HomevoltEmsResponse:
        """Validate connectivity by fetching EMS data. Used in config flow."""
        return await self.async_get_ems_data()
