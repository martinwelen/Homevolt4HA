"""DataUpdateCoordinator for Homevolt."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import HomevoltApiClient, HomevoltAuthError, HomevoltConnectionError
from .const import (
    DEFAULT_SCAN_INTERVAL,
    ERROR_REPORT_POLL_INTERVAL,
    NODES_POLL_INTERVAL,
    SCHEDULE_POLL_INTERVAL,
    STATUS_POLL_INTERVAL,
)
from .models import HomevoltData

_LOGGER = logging.getLogger(__name__)

# Python 3.9-compatible type alias (3.12 would use: type HomevoltConfigEntry = ...)
HomevoltConfigEntry = ConfigEntry


class HomevoltCoordinator(DataUpdateCoordinator[HomevoltData]):
    """Coordinator for Homevolt data updates with tiered polling."""

    config_entry: HomevoltConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: HomevoltConfigEntry,
        client: HomevoltApiClient,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Homevolt",
            config_entry=config_entry,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self._poll_count = 0

    async def _async_update_data(self) -> HomevoltData:
        """Fetch data from the Homevolt API with tiered polling."""
        self._poll_count += 1

        try:
            # Always fetch EMS data (primary data source)
            ems = await self.client.async_get_ems_data()

            # Build the combined data object
            combined = HomevoltData(ems=ems)

            # Fetch status data every Nth cycle
            if self._poll_count % STATUS_POLL_INTERVAL == 0 or self.data is None:
                combined.status = await self.client.async_get_status()
            elif self.data is not None:
                combined.status = self.data.status

            # Fetch error report every Nth cycle
            if self._poll_count % ERROR_REPORT_POLL_INTERVAL == 0 or self.data is None:
                combined.error_report = await self.client.async_get_error_report()
            elif self.data is not None:
                combined.error_report = self.data.error_report

            # Fetch nodes and node metrics every Nth cycle
            if self._poll_count % NODES_POLL_INTERVAL == 0 or self.data is None:
                combined.nodes = await self.client.async_get_nodes()
                # Fetch metrics for each configured CT sensor node
                for sensor in combined.ems.sensors:
                    if sensor.euid and sensor.euid != "0000000000000000" and sensor.node_id:
                        try:
                            metrics = await self.client.async_get_node_metrics(sensor.node_id)
                            combined.node_metrics[sensor.node_id] = metrics
                        except Exception:
                            _LOGGER.warning(
                                "Failed to fetch node_metrics for node %s",
                                sensor.node_id,
                            )
            elif self.data is not None:
                combined.nodes = self.data.nodes
                combined.node_metrics = self.data.node_metrics

            # Fetch schedule every Nth cycle (non-fatal)
            if self._poll_count % SCHEDULE_POLL_INTERVAL == 0 or self.data is None:
                try:
                    combined.schedule = await self.client.async_get_schedule()
                except Exception:
                    _LOGGER.warning("Failed to fetch schedule data")
                    if self.data is not None:
                        combined.schedule = self.data.schedule
            elif self.data is not None:
                combined.schedule = self.data.schedule

            # Fire events when alarm/warning/info state changes
            if self.data is not None:
                prev = self.data.ems.aggregated.ems_data
                curr = combined.ems.aggregated.ems_data
                if prev.alarm_str != curr.alarm_str:
                    self.hass.bus.async_fire(
                        "homevolt_alarm",
                        {"previous": prev.alarm_str, "current": curr.alarm_str},
                    )
                if prev.warning_str != curr.warning_str:
                    self.hass.bus.async_fire(
                        "homevolt_warning",
                        {"previous": prev.warning_str, "current": curr.warning_str},
                    )
                if prev.info_str != curr.info_str:
                    self.hass.bus.async_fire(
                        "homevolt_info",
                        {"previous": prev.info_str, "current": curr.info_str},
                    )

        except HomevoltAuthError as err:
            raise ConfigEntryAuthFailed("Invalid credentials") from err
        except HomevoltConnectionError as err:
            raise UpdateFailed(f"Error communicating with Homevolt: {err}") from err

        return combined
