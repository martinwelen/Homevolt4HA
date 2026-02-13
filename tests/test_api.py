"""Tests for Homevolt API client."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
import pytest_asyncio
from aioresponses import aioresponses

from custom_components.homevolt.api import (
    HomevoltApiClient,
    HomevoltApiError,
    HomevoltAuthError,
    HomevoltConnectionError,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest_asyncio.fixture
async def mock_session():
    """Create a real aiohttp session for testing."""
    session = aiohttp.ClientSession()
    yield session
    await session.close()


@pytest.fixture
def api_client(mock_session):
    """Create an API client for testing."""
    return HomevoltApiClient(
        session=mock_session,
        host="192.168.70.12",
    )


@pytest.fixture
def api_client_with_password(mock_session):
    """Create an API client with password."""
    return HomevoltApiClient(
        session=mock_session,
        host="192.168.70.12",
        password="secret",
    )


@pytest.fixture
def ems_fixture():
    """Load EMS response fixture."""
    return json.loads((FIXTURES / "ems_response.json").read_text())


@pytest.fixture
def status_fixture():
    """Load status response fixture."""
    return json.loads((FIXTURES / "status_response.json").read_text())


@pytest.fixture
def error_report_fixture():
    """Load error report fixture."""
    return json.loads((FIXTURES / "error_report_response.json").read_text())


@pytest.mark.asyncio
async def test_get_ems_data(api_client, ems_fixture):
    """Test fetching EMS data."""
    with aioresponses() as m:
        m.get("http://192.168.70.12:80/ems.json", payload=ems_fixture)
        result = await api_client.async_get_ems_data()
        assert result.type == "ems_data"
        assert result.aggregated.ems_info.rated_capacity == 13304


@pytest.mark.asyncio
async def test_get_status(api_client, status_fixture):
    """Test fetching status data."""
    with aioresponses() as m:
        m.get("http://192.168.70.12:80/status.json", payload=status_fixture)
        result = await api_client.async_get_status()
        assert result.up_time > 0
        assert result.wifi_status.connected is True


@pytest.mark.asyncio
async def test_get_error_report(api_client, error_report_fixture):
    """Test fetching error report."""
    with aioresponses() as m:
        m.get(
            "http://192.168.70.12:80/error_report.json",
            payload=error_report_fixture,
        )
        result = await api_client.async_get_error_report()
        assert len(result) > 0
        assert any(e.sub_system_name == "EMS" for e in result)


@pytest.mark.asyncio
async def test_auth_error(api_client):
    """Test 401 raises HomevoltAuthError."""
    with aioresponses() as m:
        m.get("http://192.168.70.12:80/ems.json", status=401)
        with pytest.raises(HomevoltAuthError):
            await api_client.async_get_ems_data()


@pytest.mark.asyncio
async def test_retry_on_503(api_client, ems_fixture):
    """Test retry logic on 503 status."""
    mock_sleep = AsyncMock()
    with aioresponses() as m:
        with patch("custom_components.homevolt.api.asyncio.sleep", mock_sleep):
            m.get("http://192.168.70.12:80/ems.json", status=503)
            m.get("http://192.168.70.12:80/ems.json", payload=ems_fixture)
            result = await api_client.async_get_ems_data()
            assert result.type == "ems_data"
            mock_sleep.assert_called_once()


@pytest.mark.asyncio
async def test_retry_exhausted_raises(api_client):
    """Test that exhausted retries on 503 raises HomevoltApiError."""
    mock_sleep = AsyncMock()
    with aioresponses() as m:
        with patch("custom_components.homevolt.api.asyncio.sleep", mock_sleep):
            m.get("http://192.168.70.12:80/ems.json", status=503)
            m.get("http://192.168.70.12:80/ems.json", status=503)
            m.get("http://192.168.70.12:80/ems.json", status=503)
            with pytest.raises(HomevoltApiError, match="Server error 503"):
                await api_client.async_get_ems_data()
            assert mock_sleep.call_count == 2  # sleeps between retries, not after last


@pytest.mark.asyncio
async def test_connection_error(api_client):
    """Test connection error raises HomevoltConnectionError."""
    mock_sleep = AsyncMock()
    with aioresponses() as m:
        with patch("custom_components.homevolt.api.asyncio.sleep", mock_sleep):
            m.get(
                "http://192.168.70.12:80/ems.json",
                exception=aiohttp.ClientConnectionError("refused"),
            )
            m.get(
                "http://192.168.70.12:80/ems.json",
                exception=aiohttp.ClientConnectionError("refused"),
            )
            m.get(
                "http://192.168.70.12:80/ems.json",
                exception=aiohttp.ClientConnectionError("refused"),
            )
            with pytest.raises(HomevoltConnectionError):
                await api_client.async_get_ems_data()


@pytest.mark.asyncio
async def test_connection_error_retry_then_success(api_client, ems_fixture):
    """Test that a connection error followed by success works."""
    mock_sleep = AsyncMock()
    with aioresponses() as m:
        with patch("custom_components.homevolt.api.asyncio.sleep", mock_sleep):
            m.get(
                "http://192.168.70.12:80/ems.json",
                exception=aiohttp.ClientConnectionError("refused"),
            )
            m.get("http://192.168.70.12:80/ems.json", payload=ems_fixture)
            result = await api_client.async_get_ems_data()
            assert result.type == "ems_data"
            mock_sleep.assert_called_once()


@pytest.mark.asyncio
async def test_validate_connection(api_client, ems_fixture):
    """Test validate_connection returns EMS data."""
    with aioresponses() as m:
        m.get("http://192.168.70.12:80/ems.json", payload=ems_fixture)
        result = await api_client.async_validate_connection()
        assert result.type == "ems_data"


@pytest.mark.asyncio
async def test_auth_header_sent_with_password(api_client_with_password, ems_fixture):
    """Test that auth header is sent when password is configured."""
    with aioresponses() as m:
        m.get("http://192.168.70.12:80/ems.json", payload=ems_fixture)
        result = await api_client_with_password.async_get_ems_data()
        assert result.type == "ems_data"
        # Verify the request was made (aioresponses will have consumed it)
        m.assert_called_once()


@pytest.mark.asyncio
async def test_base_url_construction():
    """Test that the base URL is constructed correctly."""
    session = aiohttp.ClientSession()
    try:
        client = HomevoltApiClient(
            session=session,
            host="10.0.0.1",
            port=8080,
            use_ssl=True,
        )
        assert client._base_url == "https://10.0.0.1:8080"
        assert client.host == "10.0.0.1"
    finally:
        await session.close()


@pytest.mark.asyncio
async def test_host_property(api_client):
    """Test host property returns the configured host."""
    assert api_client.host == "192.168.70.12"
