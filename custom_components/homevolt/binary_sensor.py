"""Binary sensor platform for Homevolt integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import HomevoltCoordinator
from .entity import HomevoltEntity, HomevoltSensorDeviceEntity
from .models import HomevoltData, NodeInfo, NodeMetrics, SensorData

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom binary sensor descriptions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HomevoltBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Homevolt system binary sensor."""

    value_fn: Callable[[HomevoltData], bool | None] | None = None


@dataclass(frozen=True)
class HomevoltCtBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Homevolt CT clamp binary sensor."""

    value_fn: Callable[[SensorData], bool | None] | None = None


@dataclass(frozen=True)
class HomevoltCtNodeBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Homevolt CT node binary sensor."""

    value_fn: Callable[[NodeMetrics | None, NodeInfo | None], bool | None] | None = None


# ---------------------------------------------------------------------------
# CT clamp binary sensors
# ---------------------------------------------------------------------------

CT_BINARY_SENSORS: tuple[HomevoltCtBinarySensorEntityDescription, ...] = (
    HomevoltCtBinarySensorEntityDescription(
        key="ct_available",
        translation_key="ct_available",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda s: s.available,
    ),
)


# ---------------------------------------------------------------------------
# CT node binary sensors
# ---------------------------------------------------------------------------

CT_NODE_BINARY_SENSORS: tuple[HomevoltCtNodeBinarySensorEntityDescription, ...] = (
    HomevoltCtNodeBinarySensorEntityDescription(
        key="ct_usb_powered",
        translation_key="ct_usb_powered",
        device_class=BinarySensorDeviceClass.PLUG,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m, n: m.usb_power if m is not None else None,
    ),
    HomevoltCtNodeBinarySensorEntityDescription(
        key="ct_firmware_update_available",
        translation_key="ct_firmware_update_available",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m, n: n.version != n.manifest_version if n is not None else None,
    ),
)


# ---------------------------------------------------------------------------
# System binary sensors
# ---------------------------------------------------------------------------

SYSTEM_BINARY_SENSORS: tuple[HomevoltBinarySensorEntityDescription, ...] = (
    HomevoltBinarySensorEntityDescription(
        key="wifi_connected",
        translation_key="wifi_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.wifi_status.connected if data.status is not None else None,
    ),
    HomevoltBinarySensorEntityDescription(
        key="mqtt_connected",
        translation_key="mqtt_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.mqtt_status.connected if data.status is not None else None,
    ),
)


# ---------------------------------------------------------------------------
# Binary sensor entity classes
# ---------------------------------------------------------------------------

class HomevoltBinarySensor(HomevoltEntity, BinarySensorEntity):
    """Binary sensor for system-level data."""

    entity_description: HomevoltBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        ecu_id: str,
        description: HomevoltBinarySensorEntityDescription,
    ) -> None:
        """Initialize a system binary sensor."""
        super().__init__(coordinator, ecu_id)
        self.entity_description = description
        self._attr_unique_id = f"{ecu_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)


class HomevoltCtBinarySensor(HomevoltSensorDeviceEntity, BinarySensorEntity):
    """Binary sensor for CT clamp availability."""

    entity_description: HomevoltCtBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        ecu_id: str,
        sensor_index: int,
        sensor_type: str,
        euid: str,
        description: HomevoltCtBinarySensorEntityDescription,
    ) -> None:
        """Initialize a CT binary sensor."""
        super().__init__(coordinator, ecu_id, sensor_index, sensor_type, euid)
        self.entity_description = description
        self._attr_unique_id = f"{euid}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        sensors = self.coordinator.data.ems.sensors
        if self._sensor_index >= len(sensors):
            return None
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(sensors[self._sensor_index])


class HomevoltCtNodeBinarySensor(HomevoltSensorDeviceEntity, BinarySensorEntity):
    """Binary sensor for CT clamp node data (USB power, firmware update)."""

    entity_description: HomevoltCtNodeBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        ecu_id: str,
        sensor_index: int,
        sensor_type: str,
        euid: str,
        node_id: int,
        description: HomevoltCtNodeBinarySensorEntityDescription,
    ) -> None:
        """Initialize a CT node binary sensor."""
        super().__init__(coordinator, ecu_id, sensor_index, sensor_type, euid)
        self._node_id = node_id
        self.entity_description = description
        self._attr_unique_id = f"{euid}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        if self.entity_description.value_fn is None:
            return None
        metrics = self.coordinator.data.node_metrics.get(self._node_id)
        node_info = next(
            (n for n in self.coordinator.data.nodes if n.node_id == self._node_id),
            None,
        )
        return self.entity_description.value_fn(metrics, node_info)


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homevolt binary sensor entities from a config entry."""
    coordinator: HomevoltCoordinator = entry.runtime_data
    data = coordinator.data
    entities: list[BinarySensorEntity] = []

    ems_list = data.ems.ems
    if not ems_list:
        _LOGGER.error("No EMS devices found in Homevolt data")
        return

    ecu_id = str(ems_list[0].ecu_id)

    # --- System binary sensors ---
    for desc in SYSTEM_BINARY_SENSORS:
        entities.append(HomevoltBinarySensor(coordinator, ecu_id, desc))

    # --- CT clamp binary sensors (skip unconfigured) ---
    for sensor_idx, sensor_data in enumerate(data.ems.sensors):
        euid = sensor_data.euid
        sensor_type = sensor_data.type
        if not euid or euid == "0000000000000000":
            continue
        for desc in CT_BINARY_SENSORS:
            entities.append(
                HomevoltCtBinarySensor(
                    coordinator, ecu_id, sensor_idx, sensor_type, euid, desc
                )
            )
        # CT node binary sensors (USB power, firmware update)
        if sensor_data.node_id:
            for desc in CT_NODE_BINARY_SENSORS:
                entities.append(
                    HomevoltCtNodeBinarySensor(
                        coordinator, ecu_id, sensor_idx, sensor_type, euid,
                        sensor_data.node_id, desc,
                    )
                )

    async_add_entities(entities)
    _LOGGER.debug(
        "Added %d Homevolt binary sensor entities",
        len(entities),
    )
