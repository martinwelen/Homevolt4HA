"""Diagnostics support for Homevolt."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import HomevoltCoordinator

REDACT_KEYS = {CONF_PASSWORD, "serial_number", "ssid", "psk", "ip", "mqtt_topic", "mqtt_topic_sub", "mqtt_client_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: HomevoltCoordinator = entry.runtime_data

    # Redact sensitive config data
    config_data = dict(entry.data)
    for key in REDACT_KEYS:
        if key in config_data:
            config_data[key] = "**REDACTED**"

    diag: dict[str, Any] = {
        "config": config_data,
        "options": dict(entry.options),
    }

    if coordinator.data:
        diag["ems"] = asdict(coordinator.data.ems)
        if coordinator.data.status:
            status_dict = asdict(coordinator.data.status)
            # Redact WiFi credentials
            if "wifi_status" in status_dict:
                status_dict["wifi_status"]["ssid"] = "**REDACTED**"
                status_dict["wifi_status"]["ip"] = "**REDACTED**"
            diag["status"] = status_dict
        if coordinator.data.error_report:
            diag["error_report"] = [asdict(e) for e in coordinator.data.error_report]
        if coordinator.data.nodes:
            diag["nodes"] = [asdict(n) for n in coordinator.data.nodes]
        if coordinator.data.node_metrics:
            diag["node_metrics"] = {
                str(k): asdict(v) for k, v in coordinator.data.node_metrics.items()
            }

    return diag
