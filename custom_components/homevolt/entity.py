"""Base entity classes for Homevolt."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import HomevoltCoordinator


class HomevoltEntity(CoordinatorEntity[HomevoltCoordinator]):
    """Base entity for Homevolt integration."""

    has_entity_name = True

    def __init__(self, coordinator: HomevoltCoordinator, ecu_id: str) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._ecu_id = ecu_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the main battery system."""
        agg = self.coordinator.data.ems.aggregated
        return DeviceInfo(
            identifiers={(DOMAIN, self._ecu_id)},
            name="Homevolt Battery System",
            manufacturer=MANUFACTURER,
            model="Homevolt",
            sw_version=agg.ems_info.fw_version,
            hw_version=agg.inv_info.fw_version,
        )


class HomevoltBmsEntity(CoordinatorEntity[HomevoltCoordinator]):
    """Entity for a BMS battery module."""

    has_entity_name = True

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        ecu_id: str,
        bms_index: int,
        serial_number: str,
    ) -> None:
        """Initialize the BMS entity."""
        super().__init__(coordinator)
        self._ecu_id = ecu_id
        self._bms_index = bms_index
        self._serial_number = serial_number

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the battery module."""
        bms_info = self.coordinator.data.ems.aggregated.bms_info
        fw = bms_info[self._bms_index].fw_version if self._bms_index < len(bms_info) else ""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial_number)},
            name=f"Battery Module {self._bms_index + 1}",
            manufacturer=MANUFACTURER,
            model="Homevolt BMS",
            sw_version=fw,
            via_device=(DOMAIN, self._ecu_id),
        )


class HomevoltSensorDeviceEntity(CoordinatorEntity[HomevoltCoordinator]):
    """Entity for a CT clamp sensor device (grid, solar, load)."""

    has_entity_name = True

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        ecu_id: str,
        sensor_index: int,
        sensor_type: str,
        euid: str,
    ) -> None:
        """Initialize the sensor device entity."""
        super().__init__(coordinator)
        self._ecu_id = ecu_id
        self._sensor_index = sensor_index
        self._sensor_type = sensor_type
        self._euid = euid

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the CT sensor."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._euid)},
            name=f"{self._sensor_type.title()} Sensor",
            manufacturer=MANUFACTURER,
            model="Tibber Pulse Clamp",
            via_device=(DOMAIN, self._ecu_id),
        )
