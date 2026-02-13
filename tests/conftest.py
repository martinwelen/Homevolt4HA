"""Shared test configuration and stubs for Homevolt tests.

Provides module-level stubs for homeassistant and aiohttp so tests can
run on system Python without a full Home Assistant virtualenv. When
running inside a real HA test environment, the stubs are harmless
because the real modules are already in sys.modules.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Aiohttp stub
# ---------------------------------------------------------------------------

def _ensure_aiohttp_stub() -> None:
    """Stub out aiohttp if it cannot be imported (broken version etc.)."""
    try:
        import aiohttp  # noqa: F401
        return  # aiohttp works fine; nothing to do.
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


# ---------------------------------------------------------------------------
# Home Assistant stubs
# ---------------------------------------------------------------------------

def _ensure_ha_stubs() -> None:
    """Install lightweight stubs for homeassistant modules if not present."""
    # Check if real HA is installed (has __file__ attribute)
    ha_mod = sys.modules.get("homeassistant")
    if ha_mod is not None and hasattr(ha_mod, "__file__"):
        return  # Real HA is available; nothing to do.

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
    ha_const.Platform = MagicMock()  # type: ignore[attr-defined]
    ha_const.Platform.SENSOR = "sensor"  # type: ignore[attr-defined]
    sys.modules["homeassistant.const"] = ha_const

    # --- homeassistant.config_entries ---
    ha_config = sys.modules.get("homeassistant.config_entries") or ModuleType(
        "homeassistant.config_entries"
    )

    # ConfigEntry (used by coordinator)
    if not hasattr(ha_config, "ConfigEntry"):
        ha_config.ConfigEntry = MagicMock  # type: ignore[attr-defined]

    # ConfigFlowResult (used by config flow)
    if not hasattr(ha_config, "ConfigFlowResult"):
        ha_config.ConfigFlowResult = dict  # type: ignore[attr-defined]

    # ConfigFlow (used by config flow)
    if not hasattr(ha_config, "ConfigFlow"):

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

            def _abort_if_unique_id_configured(
                self, updates: dict | None = None
            ) -> None:
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
            def __init__(self, reason: str) -> None:
                self.reason = reason
                super().__init__(reason)

        ha_config.ConfigFlow = _StubConfigFlow  # type: ignore[attr-defined]
        ha_config.AbortFlow = _AbortFlow  # type: ignore[attr-defined]

    # OptionsFlow (used by config flow)
    if not hasattr(ha_config, "OptionsFlow"):

        class _StubOptionsFlow:
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

    # --- homeassistant.helpers.update_coordinator ---
    ha_coord_mod = sys.modules.get(
        "homeassistant.helpers.update_coordinator"
    ) or ModuleType("homeassistant.helpers.update_coordinator")

    if not hasattr(ha_coord_mod, "UpdateFailed"):

        class _UpdateFailed(Exception):
            pass

        ha_coord_mod.UpdateFailed = _UpdateFailed  # type: ignore[attr-defined]

    if not hasattr(ha_coord_mod, "DataUpdateCoordinator"):

        class _StubDataUpdateCoordinator:
            """Minimal stand-in for DataUpdateCoordinator."""

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

    sys.modules["homeassistant.helpers.update_coordinator"] = ha_coord_mod

    # --- homeassistant.helpers.aiohttp_client ---
    ha_aiohttp = sys.modules.get(
        "homeassistant.helpers.aiohttp_client"
    ) or ModuleType("homeassistant.helpers.aiohttp_client")
    if not hasattr(ha_aiohttp, "async_get_clientsession"):
        ha_aiohttp.async_get_clientsession = MagicMock(  # type: ignore[attr-defined]
            return_value=MagicMock()
        )
    sys.modules["homeassistant.helpers.aiohttp_client"] = ha_aiohttp

    # --- homeassistant.helpers.device_registry ---
    ha_devreg = sys.modules.get(
        "homeassistant.helpers.device_registry"
    ) or ModuleType("homeassistant.helpers.device_registry")
    if not hasattr(ha_devreg, "DeviceInfo"):
        ha_devreg.DeviceInfo = dict  # type: ignore[attr-defined]
    sys.modules["homeassistant.helpers.device_registry"] = ha_devreg

    # --- homeassistant.components ---
    if "homeassistant.components" not in sys.modules:
        sys.modules["homeassistant.components"] = ModuleType("homeassistant.components")

    # --- homeassistant.components.sensor ---
    ha_sensor = sys.modules.get(
        "homeassistant.components.sensor"
    ) or ModuleType("homeassistant.components.sensor")
    if not hasattr(ha_sensor, "SensorEntity"):
        ha_sensor.SensorEntity = MagicMock  # type: ignore[attr-defined]
        ha_sensor.SensorEntityDescription = MagicMock  # type: ignore[attr-defined]
        ha_sensor.SensorDeviceClass = MagicMock()  # type: ignore[attr-defined]
        ha_sensor.SensorStateClass = MagicMock()  # type: ignore[attr-defined]
    sys.modules["homeassistant.components.sensor"] = ha_sensor


# Run stubs at module level (before test collection imports test modules)
_ensure_aiohttp_stub()
_ensure_ha_stubs()


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

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
