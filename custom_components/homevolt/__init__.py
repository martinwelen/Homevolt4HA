"""The Homevolt integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HomevoltApiClient
from .const import CONF_SCAN_INTERVAL, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import HomevoltCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Python 3.9-compatible type alias (3.12 would use: type HomevoltConfigEntry = ...)
HomevoltConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: HomevoltConfigEntry) -> bool:
    """Set up Homevolt from a config entry."""
    session = async_get_clientsession(hass)

    client = HomevoltApiClient(
        session=session,
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        password=entry.data.get(CONF_PASSWORD),
    )

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = HomevoltCoordinator(hass, entry, client, scan_interval)

    # First refresh - raises ConfigEntryNotReady on failure
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload on options change
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    return True


async def _async_update_options(hass: HomeAssistant, entry: HomevoltConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HomevoltConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
