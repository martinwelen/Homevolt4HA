"""Tests for Homevolt config flow."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stubs are set up by conftest.py before this module is imported
from custom_components.homevolt.api import (
    HomevoltAuthError,
    HomevoltConnectionError,
)
from custom_components.homevolt.config_flow import (
    HomevoltConfigFlow,
    HomevoltOptionsFlow,
)
from custom_components.homevolt.const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
)
from custom_components.homevolt.models import HomevoltEmsResponse
from homeassistant.config_entries import AbortFlow

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_fixture(name: str):
    """Load a JSON fixture file."""
    return json.loads((FIXTURES / name).read_text())


def _make_ems_response() -> HomevoltEmsResponse:
    """Create an EMS response from fixture data."""
    return HomevoltEmsResponse.from_dict(_load_fixture("ems_response.json"))


def _make_empty_ems_response() -> HomevoltEmsResponse:
    """Create an EMS response with no EMS devices."""
    return HomevoltEmsResponse(type="ems_data", ts=0, ems=[], sensors=[])


class _FakeZeroconfInfo:
    """Fake Zeroconf discovery info."""

    def __init__(self, host: str = "192.168.70.12", port: int = 80) -> None:
        self.host = host
        self.port = port


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def flow() -> HomevoltConfigFlow:
    """Create a fresh config flow instance with a mock hass."""
    f = HomevoltConfigFlow()
    f.hass = MagicMock()
    f.context = {}
    return f


@pytest.fixture
def ems_response() -> HomevoltEmsResponse:
    """Return a parsed EMS response from fixture."""
    return _make_ems_response()


# ---------------------------------------------------------------------------
# Tests: Successful manual setup (user step)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_step_success(flow, ems_response):
    """Test successful manual setup creates an entry with correct data."""
    with patch(
        "custom_components.homevolt.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.config_flow.HomevoltApiClient",
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.async_validate_connection = AsyncMock(return_value=ems_response)
        mock_client_cls.return_value = mock_client

        result = await flow.async_step_user(
            user_input={
                "host": "192.168.70.12",
                "port": 80,
                "password": "secret",
                "scan_interval": 30,
            }
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Homevolt (192.168.70.12)"
    assert result["data"]["host"] == "192.168.70.12"
    assert result["data"]["port"] == 80
    assert result["data"]["password"] == "secret"
    assert result["options"]["scan_interval"] == 30


@pytest.mark.asyncio
async def test_user_step_success_no_password(flow, ems_response):
    """Test successful setup without a password."""
    with patch(
        "custom_components.homevolt.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.config_flow.HomevoltApiClient",
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.async_validate_connection = AsyncMock(return_value=ems_response)
        mock_client_cls.return_value = mock_client

        result = await flow.async_step_user(
            user_input={
                "host": "192.168.70.12",
            }
        )

    assert result["type"] == "create_entry"
    assert result["data"]["password"] is None
    assert result["data"]["port"] == DEFAULT_PORT
    assert result["options"]["scan_interval"] == DEFAULT_SCAN_INTERVAL


@pytest.mark.asyncio
async def test_user_step_unique_id_from_ecu(flow, ems_response):
    """Test that unique_id is set from ecu_id of first EMS device."""
    with patch(
        "custom_components.homevolt.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.config_flow.HomevoltApiClient",
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.async_validate_connection = AsyncMock(return_value=ems_response)
        mock_client_cls.return_value = mock_client

        await flow.async_step_user(
            user_input={"host": "192.168.70.12"}
        )

    assert flow._unique_id == "9731192375880"


# ---------------------------------------------------------------------------
# Tests: Auth error on manual setup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_step_auth_error(flow):
    """Test that auth error shows invalid_auth."""
    with patch(
        "custom_components.homevolt.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.config_flow.HomevoltApiClient",
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.async_validate_connection = AsyncMock(
            side_effect=HomevoltAuthError("Bad password")
        )
        mock_client_cls.return_value = mock_client

        result = await flow.async_step_user(
            user_input={"host": "192.168.70.12", "password": "wrong"}
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


# ---------------------------------------------------------------------------
# Tests: Connection error on manual setup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_step_connection_error(flow):
    """Test that connection error shows cannot_connect."""
    with patch(
        "custom_components.homevolt.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.config_flow.HomevoltApiClient",
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.async_validate_connection = AsyncMock(
            side_effect=HomevoltConnectionError("Timeout")
        )
        mock_client_cls.return_value = mock_client

        result = await flow.async_step_user(
            user_input={"host": "192.168.70.12"}
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


# ---------------------------------------------------------------------------
# Tests: Unknown error on manual setup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_step_unknown_error(flow):
    """Test that unexpected exceptions show unknown error."""
    with patch(
        "custom_components.homevolt.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.config_flow.HomevoltApiClient",
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.async_validate_connection = AsyncMock(
            side_effect=RuntimeError("Something unexpected")
        )
        mock_client_cls.return_value = mock_client

        result = await flow.async_step_user(
            user_input={"host": "192.168.70.12"}
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}


# ---------------------------------------------------------------------------
# Tests: User step shows form when no input
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_step_shows_form(flow):
    """Test that user step shows form when no input is provided."""
    result = await flow.async_step_user(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert "errors" in result
    assert result["errors"] == {}


# ---------------------------------------------------------------------------
# Tests: Zeroconf discovery flow (happy path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zeroconf_discovery_success(flow, ems_response):
    """Test successful Zeroconf discovery shows confirmation form."""
    discovery_info = _FakeZeroconfInfo(host="192.168.70.12", port=80)

    with patch(
        "custom_components.homevolt.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.config_flow.HomevoltApiClient",
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.async_validate_connection = AsyncMock(return_value=ems_response)
        mock_client_cls.return_value = mock_client

        result = await flow.async_step_zeroconf(discovery_info)

    assert result["type"] == "form"
    assert result["step_id"] == "zeroconf_confirm"
    assert flow._host == "192.168.70.12"
    assert flow._port == 80
    assert flow._unique_id == "9731192375880"


@pytest.mark.asyncio
async def test_zeroconf_sets_title_placeholder(flow, ems_response):
    """Test that Zeroconf sets title placeholders in context."""
    discovery_info = _FakeZeroconfInfo(host="192.168.70.12", port=80)

    with patch(
        "custom_components.homevolt.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.config_flow.HomevoltApiClient",
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.async_validate_connection = AsyncMock(return_value=ems_response)
        mock_client_cls.return_value = mock_client

        await flow.async_step_zeroconf(discovery_info)

    assert flow.context["title_placeholders"]["name"] == "Homevolt (192.168.70.12)"


# ---------------------------------------------------------------------------
# Tests: Zeroconf discovery - connection error aborts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zeroconf_connection_error_aborts(flow):
    """Test that Zeroconf aborts if connection fails."""
    discovery_info = _FakeZeroconfInfo(host="192.168.70.99", port=80)

    with patch(
        "custom_components.homevolt.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.config_flow.HomevoltApiClient",
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.async_validate_connection = AsyncMock(
            side_effect=HomevoltConnectionError("No route to host")
        )
        mock_client_cls.return_value = mock_client

        result = await flow.async_step_zeroconf(discovery_info)

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


@pytest.mark.asyncio
async def test_zeroconf_auth_error_aborts(flow):
    """Test that Zeroconf aborts if auth fails."""
    discovery_info = _FakeZeroconfInfo(host="192.168.70.12", port=80)

    with patch(
        "custom_components.homevolt.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.config_flow.HomevoltApiClient",
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.async_validate_connection = AsyncMock(
            side_effect=HomevoltAuthError("Needs password")
        )
        mock_client_cls.return_value = mock_client

        result = await flow.async_step_zeroconf(discovery_info)

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


# ---------------------------------------------------------------------------
# Tests: Duplicate device abort (unique_id already configured)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_step_duplicate_aborts(flow, ems_response):
    """Test that configuring a device with an existing unique_id aborts."""
    flow._existing_unique_ids = {"9731192375880"}

    with patch(
        "custom_components.homevolt.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.config_flow.HomevoltApiClient",
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.async_validate_connection = AsyncMock(return_value=ems_response)
        mock_client_cls.return_value = mock_client

        with pytest.raises(AbortFlow, match="already_configured"):
            await flow.async_step_user(
                user_input={"host": "192.168.70.12"}
            )


@pytest.mark.asyncio
async def test_zeroconf_duplicate_aborts(flow, ems_response):
    """Test that Zeroconf discovery of an already-configured device aborts."""
    flow._existing_unique_ids = {"9731192375880"}
    discovery_info = _FakeZeroconfInfo(host="192.168.70.12", port=80)

    with patch(
        "custom_components.homevolt.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.config_flow.HomevoltApiClient",
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.async_validate_connection = AsyncMock(return_value=ems_response)
        mock_client_cls.return_value = mock_client

        with pytest.raises(AbortFlow, match="already_configured"):
            await flow.async_step_zeroconf(discovery_info)


# ---------------------------------------------------------------------------
# Tests: Zeroconf confirm step with password
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zeroconf_confirm_with_password(flow):
    """Test confirming Zeroconf discovery with a password creates entry."""
    flow._host = "192.168.70.12"
    flow._port = 80

    result = await flow.async_step_zeroconf_confirm(
        user_input={"password": "mysecret"}
    )

    assert result["type"] == "create_entry"
    assert result["title"] == "Homevolt (192.168.70.12)"
    assert result["data"]["host"] == "192.168.70.12"
    assert result["data"]["port"] == 80
    assert result["data"]["password"] == "mysecret"
    assert result["options"]["scan_interval"] == DEFAULT_SCAN_INTERVAL


@pytest.mark.asyncio
async def test_zeroconf_confirm_without_password(flow):
    """Test confirming Zeroconf discovery without a password."""
    flow._host = "192.168.70.12"
    flow._port = 80

    result = await flow.async_step_zeroconf_confirm(
        user_input={}
    )

    assert result["type"] == "create_entry"
    assert result["data"]["password"] is None
    assert result["data"]["host"] == "192.168.70.12"


@pytest.mark.asyncio
async def test_zeroconf_confirm_shows_form(flow):
    """Test that zeroconf_confirm shows form when no input."""
    flow._host = "192.168.70.12"
    flow._port = 80

    result = await flow.async_step_zeroconf_confirm(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "zeroconf_confirm"
    assert result["description_placeholders"]["host"] == "192.168.70.12"


# ---------------------------------------------------------------------------
# Tests: Options flow (change scan interval)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_options_flow_shows_form():
    """Test that options flow shows form with current value."""
    options_flow = HomevoltOptionsFlow()
    config_entry = MagicMock()
    config_entry.options = {"scan_interval": 60}
    options_flow.config_entry = config_entry

    result = await options_flow.async_step_init(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "init"


@pytest.mark.asyncio
async def test_options_flow_saves_new_interval():
    """Test that options flow saves the new scan interval."""
    options_flow = HomevoltOptionsFlow()
    config_entry = MagicMock()
    config_entry.options = {"scan_interval": 30}
    options_flow.config_entry = config_entry

    result = await options_flow.async_step_init(user_input={"scan_interval": 120})

    assert result["type"] == "create_entry"
    assert result["data"]["scan_interval"] == 120


@pytest.mark.asyncio
async def test_options_flow_default_when_no_option_set():
    """Test that options flow defaults to DEFAULT_SCAN_INTERVAL."""
    options_flow = HomevoltOptionsFlow()
    config_entry = MagicMock()
    config_entry.options = {}
    options_flow.config_entry = config_entry

    result = await options_flow.async_step_init(user_input=None)

    assert result["type"] == "form"


# ---------------------------------------------------------------------------
# Tests: async_get_options_flow static method
# ---------------------------------------------------------------------------


def test_get_options_flow_returns_options_flow():
    """Test that async_get_options_flow returns a HomevoltOptionsFlow instance."""
    result = HomevoltConfigFlow.async_get_options_flow(MagicMock())
    assert isinstance(result, HomevoltOptionsFlow)


# ---------------------------------------------------------------------------
# Tests: User step with custom scan interval
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_step_custom_scan_interval(flow, ems_response):
    """Test that custom scan interval is stored in options."""
    with patch(
        "custom_components.homevolt.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.config_flow.HomevoltApiClient",
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.async_validate_connection = AsyncMock(return_value=ems_response)
        mock_client_cls.return_value = mock_client

        result = await flow.async_step_user(
            user_input={
                "host": "192.168.70.12",
                "scan_interval": 60,
            }
        )

    assert result["type"] == "create_entry"
    assert result["options"]["scan_interval"] == 60


# ---------------------------------------------------------------------------
# Tests: Zeroconf with custom port
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zeroconf_custom_port(flow, ems_response):
    """Test Zeroconf discovery with a non-default port."""
    discovery_info = _FakeZeroconfInfo(host="10.0.0.5", port=8080)

    with patch(
        "custom_components.homevolt.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.config_flow.HomevoltApiClient",
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.async_validate_connection = AsyncMock(return_value=ems_response)
        mock_client_cls.return_value = mock_client

        result = await flow.async_step_zeroconf(discovery_info)

    assert flow._host == "10.0.0.5"
    assert flow._port == 8080
    assert result["type"] == "form"


# ---------------------------------------------------------------------------
# Tests: Empty EMS list fallback (unique_id falls back to host)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_step_empty_ems_uses_host_as_unique_id(flow):
    """Test that unique_id falls back to host when no EMS devices."""
    empty_ems = _make_empty_ems_response()

    with patch(
        "custom_components.homevolt.config_flow.async_get_clientsession",
        return_value=MagicMock(),
    ), patch(
        "custom_components.homevolt.config_flow.HomevoltApiClient",
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.async_validate_connection = AsyncMock(return_value=empty_ems)
        mock_client_cls.return_value = mock_client

        result = await flow.async_step_user(
            user_input={"host": "192.168.70.12"}
        )

    assert result["type"] == "create_entry"
    assert flow._unique_id == "192.168.70.12"
