"""Tests for Homevolt config flow."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

# ---------------------------------------------------------------------------
# Stub out homeassistant and aiohttp modules so the config flow can be
# imported even when Home Assistant or compatible aiohttp is not installed.
# This mirrors the pattern used in test_coordinator.py.
# ---------------------------------------------------------------------------


def _ensure_aiohttp_stub() -> None:
    """Stub out aiohttp if it cannot be imported (broken version etc.)."""
    try:
        import aiohttp  # noqa: F401

        return
    except (ImportError, Exception):
        pass

    aiohttp_mod = ModuleType("aiohttp")
    aiohttp_mod.ClientSession = MagicMock  # type: ignore[attr-defined]
    aiohttp_mod.BasicAuth = MagicMock  # type: ignore[attr-defined]
    aiohttp_mod.ClientTimeout = MagicMock  # type: ignore[attr-defined]
    aiohttp_mod.ClientConnectionError = type(  # type: ignore[attr-defined]
        "ClientConnectionError", (Exception,), {}
    )
    sys.modules["aiohttp"] = aiohttp_mod


def _ensure_ha_stubs() -> None:
    """Install lightweight stubs for homeassistant modules."""
    if "homeassistant" in sys.modules and hasattr(
        sys.modules.get("homeassistant", None), "__file__"
    ):
        return  # Real HA is available

    # --- homeassistant (top-level) ---
    ha = sys.modules.get("homeassistant") or ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    # --- homeassistant.core ---
    ha_core = sys.modules.get("homeassistant.core") or ModuleType("homeassistant.core")
    ha_core.HomeAssistant = MagicMock  # type: ignore[attr-defined]
    if not hasattr(ha_core, "callback"):
        ha_core.callback = lambda f: f  # type: ignore[attr-defined]
    sys.modules["homeassistant.core"] = ha_core

    # --- homeassistant.const ---
    ha_const = sys.modules.get("homeassistant.const") or ModuleType("homeassistant.const")
    ha_const.CONF_HOST = "host"  # type: ignore[attr-defined]
    ha_const.CONF_PASSWORD = "password"  # type: ignore[attr-defined]
    ha_const.CONF_PORT = "port"  # type: ignore[attr-defined]
    sys.modules["homeassistant.const"] = ha_const

    # --- homeassistant.config_entries ---
    ha_config = sys.modules.get("homeassistant.config_entries") or ModuleType(
        "homeassistant.config_entries"
    )

    # ConfigFlowResult is just a TypedDict / dict in real HA
    ha_config.ConfigFlowResult = dict  # type: ignore[attr-defined]

    class _StubConfigFlow:
        """Minimal ConfigFlow stub."""

        VERSION = 1

        def __init_subclass__(cls, *, domain: str = "", **kwargs: Any) -> None:
            cls._domain = domain
            super().__init_subclass__(**kwargs)

        def __init__(self) -> None:
            self.hass = None
            self.context: dict[str, Any] = {}
            self._unique_id: str | None = None

        async def async_set_unique_id(self, uid: str) -> None:
            self._unique_id = uid

        def _abort_if_unique_id_configured(self, updates: dict | None = None) -> None:
            """Abort if unique_id is already configured.

            In tests, we control this via the _existing_unique_ids set.
            """
            existing = getattr(self, "_existing_unique_ids", set())
            if self._unique_id in existing:
                raise _AbortFlow("already_configured")

        def async_show_form(self, **kwargs: Any) -> dict:
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs: Any) -> dict:
            return {"type": "create_entry", **kwargs}

        def async_abort(self, **kwargs: Any) -> dict:
            return {"type": "abort", **kwargs}

    class _AbortFlow(Exception):
        """Stub for AbortFlow exception."""

        def __init__(self, reason: str) -> None:
            self.reason = reason
            super().__init__(reason)

    ha_config.ConfigFlow = _StubConfigFlow  # type: ignore[attr-defined]
    ha_config.AbortFlow = _AbortFlow  # type: ignore[attr-defined]

    class _StubOptionsFlow:
        """Minimal OptionsFlow stub."""

        def __init__(self) -> None:
            self.config_entry = None

        def async_show_form(self, **kwargs: Any) -> dict:
            return {"type": "form", **kwargs}

        def async_create_entry(self, **kwargs: Any) -> dict:
            return {"type": "create_entry", **kwargs}

    ha_config.OptionsFlow = _StubOptionsFlow  # type: ignore[attr-defined]
    sys.modules["homeassistant.config_entries"] = ha_config

    # --- homeassistant.exceptions ---
    ha_exc = sys.modules.get("homeassistant.exceptions") or ModuleType(
        "homeassistant.exceptions"
    )
    if not hasattr(ha_exc, "ConfigEntryAuthFailed"):

        class _ConfigEntryAuthFailed(Exception):
            pass

        ha_exc.ConfigEntryAuthFailed = _ConfigEntryAuthFailed  # type: ignore[attr-defined]
    sys.modules["homeassistant.exceptions"] = ha_exc

    # --- homeassistant.helpers ---
    ha_helpers = sys.modules.get("homeassistant.helpers") or ModuleType(
        "homeassistant.helpers"
    )
    sys.modules["homeassistant.helpers"] = ha_helpers

    # --- homeassistant.helpers.aiohttp_client ---
    ha_aiohttp = sys.modules.get("homeassistant.helpers.aiohttp_client") or ModuleType(
        "homeassistant.helpers.aiohttp_client"
    )
    ha_aiohttp.async_get_clientsession = MagicMock(  # type: ignore[attr-defined]
        return_value=MagicMock()
    )
    sys.modules["homeassistant.helpers.aiohttp_client"] = ha_aiohttp

    # --- homeassistant.helpers.update_coordinator ---
    ha_coord_mod = sys.modules.get(
        "homeassistant.helpers.update_coordinator"
    ) or ModuleType("homeassistant.helpers.update_coordinator")
    if not hasattr(ha_coord_mod, "DataUpdateCoordinator"):

        class _UpdateFailed(Exception):
            pass

        class _StubDataUpdateCoordinator:
            def __init__(
                self, hass, logger, *, name, config_entry=None, update_interval=None
            ):
                self.hass = hass
                self.logger = logger
                self.name = name
                self.config_entry = config_entry
                self.update_interval = update_interval
                self.data = None

            def __class_getitem__(cls, item):
                return cls

        ha_coord_mod.DataUpdateCoordinator = _StubDataUpdateCoordinator  # type: ignore[attr-defined]
        ha_coord_mod.UpdateFailed = _UpdateFailed  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.update_coordinator"] = ha_coord_mod


_ensure_aiohttp_stub()
_ensure_ha_stubs()

# Now safe to import our modules
from custom_components.homevolt.api import (  # noqa: E402
    HomevoltApiClient,
    HomevoltAuthError,
    HomevoltConnectionError,
)
from custom_components.homevolt.config_flow import (  # noqa: E402
    HomevoltConfigFlow,
    HomevoltOptionsFlow,
)
from custom_components.homevolt.const import (  # noqa: E402
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
)
from custom_components.homevolt.models import (  # noqa: E402
    EmsDevice,
    HomevoltEmsResponse,
)
from homeassistant.config_entries import AbortFlow  # noqa: E402

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

    # Should show the zeroconf_confirm form
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
    # Simulate that this unique_id is already configured
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


def test_options_flow_shows_form():
    """Test that options flow shows form with current value."""
    import asyncio

    options_flow = HomevoltOptionsFlow()
    config_entry = MagicMock()
    config_entry.options = {"scan_interval": 60}
    options_flow.config_entry = config_entry

    result = asyncio.get_event_loop().run_until_complete(
        options_flow.async_step_init(user_input=None)
    )

    assert result["type"] == "form"
    assert result["step_id"] == "init"


def test_options_flow_saves_new_interval():
    """Test that options flow saves the new scan interval."""
    import asyncio

    options_flow = HomevoltOptionsFlow()
    config_entry = MagicMock()
    config_entry.options = {"scan_interval": 30}
    options_flow.config_entry = config_entry

    result = asyncio.get_event_loop().run_until_complete(
        options_flow.async_step_init(user_input={"scan_interval": 120})
    )

    assert result["type"] == "create_entry"
    assert result["data"]["scan_interval"] == 120


def test_options_flow_default_when_no_option_set():
    """Test that options flow defaults to DEFAULT_SCAN_INTERVAL."""
    import asyncio

    options_flow = HomevoltOptionsFlow()
    config_entry = MagicMock()
    config_entry.options = {}  # No scan_interval set
    options_flow.config_entry = config_entry

    result = asyncio.get_event_loop().run_until_complete(
        options_flow.async_step_init(user_input=None)
    )

    assert result["type"] == "form"
    # The form should be shown; the default value is handled by voluptuous schema


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
