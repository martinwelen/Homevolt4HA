"""Sensor platform for Homevolt integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfTemperature,
    UnitOfTime,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import HomevoltCoordinator
from .entity import HomevoltBmsEntity, HomevoltEntity, HomevoltSensorDeviceEntity
from .models import (
    BmsData,
    EmsDevice,
    ErrorReportEntry,
    HomevoltData,
    NodeInfo,
    NodeMetrics,
    ScheduleData,
    ScheduleEntry,
    SensorData,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom sensor entity description
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HomevoltSensorEntityDescription(SensorEntityDescription):
    """Describes a Homevolt sensor entity."""

    value_fn: Callable[[EmsDevice], StateType] | None = None


@dataclass(frozen=True)
class HomevoltBmsSensorEntityDescription(SensorEntityDescription):
    """Describes a Homevolt BMS sensor entity."""

    value_fn: Callable[[BmsData], StateType] | None = None


@dataclass(frozen=True)
class HomevoltCtSensorEntityDescription(SensorEntityDescription):
    """Describes a Homevolt CT clamp sensor entity."""

    value_fn: Callable[[SensorData], StateType] | None = None


@dataclass(frozen=True)
class HomevoltStatusSensorEntityDescription(SensorEntityDescription):
    """Describes a Homevolt status sensor entity."""

    value_fn: Callable[[HomevoltData], StateType] | None = None


@dataclass(frozen=True)
class HomevoltScheduleSensorEntityDescription(SensorEntityDescription):
    """Describes a Homevolt schedule sensor entity."""

    value_fn: Callable[[ScheduleData | None], StateType] | None = None
    attr_fn: Callable[[ScheduleData | None], dict[str, Any] | None] | None = None


@dataclass(frozen=True)
class HomevoltCtNodeSensorEntityDescription(SensorEntityDescription):
    """Describes a Homevolt CT node sensor entity."""

    value_fn: Callable[[NodeMetrics | None, NodeInfo | None], StateType] | None = None


# ---------------------------------------------------------------------------
# System sensors (aggregated EMS data)
# ---------------------------------------------------------------------------

SYSTEM_SENSORS: tuple[HomevoltSensorEntityDescription, ...] = (
    HomevoltSensorEntityDescription(
        key="battery_status",
        translation_key="battery_status",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda agg: agg.op_state_str,
    ),
    HomevoltSensorEntityDescription(
        key="battery_state",
        translation_key="battery_state",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda agg: agg.ems_data.state_str,
    ),
    HomevoltSensorEntityDescription(
        key="battery_soc",
        translation_key="battery_soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda agg: agg.ems_data.soc_avg / 100,
    ),
    HomevoltSensorEntityDescription(
        key="battery_power",
        translation_key="battery_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda agg: agg.ems_data.power,
    ),
    HomevoltSensorEntityDescription(
        key="apparent_power",
        translation_key="apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        value_fn=lambda agg: agg.ems_data.apparent_power,
    ),
    HomevoltSensorEntityDescription(
        key="reactive_power",
        translation_key="reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        value_fn=lambda agg: agg.ems_data.reactive_power,
    ),
    HomevoltSensorEntityDescription(
        key="system_temperature",
        translation_key="system_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda agg: agg.ems_data.sys_temp / 10,
    ),
    HomevoltSensorEntityDescription(
        key="grid_frequency",
        translation_key="grid_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=3,
        value_fn=lambda agg: agg.ems_data.frequency / 1000,
    ),
    HomevoltSensorEntityDescription(
        key="energy_produced",
        translation_key="energy_produced",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda agg: agg.ems_data.energy_produced,
    ),
    HomevoltSensorEntityDescription(
        key="energy_consumed",
        translation_key="energy_consumed",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda agg: agg.ems_data.energy_consumed,
    ),
    HomevoltSensorEntityDescription(
        key="energy_imported",
        translation_key="energy_imported",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda agg: agg.ems_aggregate.imported_kwh,
    ),
    HomevoltSensorEntityDescription(
        key="energy_exported",
        translation_key="energy_exported",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda agg: agg.ems_aggregate.exported_kwh,
    ),
    HomevoltSensorEntityDescription(
        key="available_charge_power",
        translation_key="available_charge_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda agg: agg.ems_prediction.avail_ch_pwr,
    ),
    HomevoltSensorEntityDescription(
        key="available_discharge_power",
        translation_key="available_discharge_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda agg: agg.ems_prediction.avail_di_pwr,
    ),
    HomevoltSensorEntityDescription(
        key="available_charge_energy",
        translation_key="available_charge_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda agg: agg.ems_prediction.avail_ch_energy,
    ),
    HomevoltSensorEntityDescription(
        key="available_discharge_energy",
        translation_key="available_discharge_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda agg: agg.ems_prediction.avail_di_energy,
    ),
    HomevoltSensorEntityDescription(
        key="rated_capacity",
        translation_key="rated_capacity",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda agg: agg.ems_info.rated_capacity,
    ),
    HomevoltSensorEntityDescription(
        key="rated_power",
        translation_key="rated_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda agg: agg.ems_info.rated_power,
    ),
    HomevoltSensorEntityDescription(
        key="phase_angle",
        translation_key="phase_angle",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°",
        value_fn=lambda agg: agg.ems_data.phase_angle,
    ),
)


# ---------------------------------------------------------------------------
# Voltage sensors
# ---------------------------------------------------------------------------

VOLTAGE_SENSORS: tuple[HomevoltSensorEntityDescription, ...] = (
    HomevoltSensorEntityDescription(
        key="voltage_l1",
        translation_key="voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=lambda agg: agg.ems_voltage.l1 / 10,
    ),
    HomevoltSensorEntityDescription(
        key="voltage_l2",
        translation_key="voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=lambda agg: agg.ems_voltage.l2 / 10,
    ),
    HomevoltSensorEntityDescription(
        key="voltage_l3",
        translation_key="voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=lambda agg: agg.ems_voltage.l3 / 10,
    ),
    HomevoltSensorEntityDescription(
        key="voltage_l1_l2",
        translation_key="voltage_l1_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=lambda agg: agg.ems_voltage.l1_l2 / 10,
    ),
    HomevoltSensorEntityDescription(
        key="voltage_l2_l3",
        translation_key="voltage_l2_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=lambda agg: agg.ems_voltage.l2_l3 / 10,
    ),
    HomevoltSensorEntityDescription(
        key="voltage_l3_l1",
        translation_key="voltage_l3_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=lambda agg: agg.ems_voltage.l3_l1 / 10,
    ),
)


# ---------------------------------------------------------------------------
# Current sensors
# ---------------------------------------------------------------------------

CURRENT_SENSORS: tuple[HomevoltSensorEntityDescription, ...] = (
    HomevoltSensorEntityDescription(
        key="current_l1",
        translation_key="current_l1",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        value_fn=lambda agg: agg.ems_current.l1 / 10,
    ),
    HomevoltSensorEntityDescription(
        key="current_l2",
        translation_key="current_l2",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        value_fn=lambda agg: agg.ems_current.l2 / 10,
    ),
    HomevoltSensorEntityDescription(
        key="current_l3",
        translation_key="current_l3",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        value_fn=lambda agg: agg.ems_current.l3 / 10,
    ),
)


# ---------------------------------------------------------------------------
# BMS sensors (per battery module)
# ---------------------------------------------------------------------------

BMS_SENSORS: tuple[HomevoltBmsSensorEntityDescription, ...] = (
    HomevoltBmsSensorEntityDescription(
        key="bms_soc",
        translation_key="bms_soc",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda bms: bms.soc / 100,
    ),
    HomevoltBmsSensorEntityDescription(
        key="bms_state",
        translation_key="bms_state",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda bms: bms.state_str,
    ),
    HomevoltBmsSensorEntityDescription(
        key="bms_min_temperature",
        translation_key="bms_min_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda bms: bms.tmin / 10,
    ),
    HomevoltBmsSensorEntityDescription(
        key="bms_max_temperature",
        translation_key="bms_max_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda bms: bms.tmax / 10,
    ),
    HomevoltBmsSensorEntityDescription(
        key="bms_cycle_count",
        translation_key="bms_cycle_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="cycles",
        value_fn=lambda bms: bms.cycle_count,
    ),
    HomevoltBmsSensorEntityDescription(
        key="bms_energy_available",
        translation_key="bms_energy_available",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        value_fn=lambda bms: bms.energy_avail,
    ),
    HomevoltBmsSensorEntityDescription(
        key="bms_alarm",
        translation_key="bms_alarm",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda bms: ", ".join(bms.alarm_str) if bms.alarm_str else None,
    ),
)


# ---------------------------------------------------------------------------
# CT clamp sensors (per sensor device)
# ---------------------------------------------------------------------------

CT_SENSORS: tuple[HomevoltCtSensorEntityDescription, ...] = (
    HomevoltCtSensorEntityDescription(
        key="ct_power",
        translation_key="ct_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda s: s.total_power,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_energy_imported",
        translation_key="ct_energy_imported",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda s: s.energy_imported,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_energy_exported",
        translation_key="ct_energy_exported",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda s: s.energy_exported,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_rssi",
        translation_key="ct_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        value_fn=lambda s: s.rssi,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_pdr",
        translation_key="ct_pdr",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda s: s.pdr,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_frequency",
        translation_key="ct_frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
        value_fn=lambda s: s.frequency,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_voltage_l1",
        translation_key="ct_voltage_l1",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=lambda s: s.phase[0].voltage if len(s.phase) > 0 else None,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_voltage_l2",
        translation_key="ct_voltage_l2",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=lambda s: s.phase[1].voltage if len(s.phase) > 1 else None,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_voltage_l3",
        translation_key="ct_voltage_l3",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        value_fn=lambda s: s.phase[2].voltage if len(s.phase) > 2 else None,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_current_l1",
        translation_key="ct_current_l1",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        value_fn=lambda s: s.phase[0].amp if len(s.phase) > 0 else None,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_current_l2",
        translation_key="ct_current_l2",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        value_fn=lambda s: s.phase[1].amp if len(s.phase) > 1 else None,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_current_l3",
        translation_key="ct_current_l3",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        value_fn=lambda s: s.phase[2].amp if len(s.phase) > 2 else None,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_power_l1",
        translation_key="ct_power_l1",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda s: s.phase[0].power if len(s.phase) > 0 else None,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_power_l2",
        translation_key="ct_power_l2",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda s: s.phase[1].power if len(s.phase) > 1 else None,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_power_l3",
        translation_key="ct_power_l3",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda s: s.phase[2].power if len(s.phase) > 2 else None,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_power_factor_l1",
        translation_key="ct_power_factor_l1",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.phase[0].pf if len(s.phase) > 0 else None,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_power_factor_l2",
        translation_key="ct_power_factor_l2",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.phase[1].pf if len(s.phase) > 1 else None,
    ),
    HomevoltCtSensorEntityDescription(
        key="ct_power_factor_l3",
        translation_key="ct_power_factor_l3",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.phase[2].pf if len(s.phase) > 2 else None,
    ),
)


# ---------------------------------------------------------------------------
# CT node sensors (per CT clamp node, from /nodes.json + /node_metrics.json)
# ---------------------------------------------------------------------------

def _ct_battery_level(metrics: NodeMetrics | None, _info: NodeInfo | None) -> float | None:
    """Convert 2xAA battery voltage to percentage (3.0V=100%, 1.8V=0%)."""
    if metrics is None:
        return None
    voltage = metrics.battery_voltage
    level = round(max(0.0, min(100.0, (voltage - 1.8) / (3.0 - 1.8) * 100.0)), 1)
    return level


CT_NODE_SENSORS: tuple[HomevoltCtNodeSensorEntityDescription, ...] = (
    HomevoltCtNodeSensorEntityDescription(
        key="ct_battery_level",
        translation_key="ct_battery_level",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=_ct_battery_level,
    ),
    HomevoltCtNodeSensorEntityDescription(
        key="ct_battery_voltage",
        translation_key="ct_battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m, n: m.battery_voltage if m is not None else None,
    ),
    HomevoltCtNodeSensorEntityDescription(
        key="ct_temperature",
        translation_key="ct_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m, n: m.temperature if m is not None else None,
    ),
    HomevoltCtNodeSensorEntityDescription(
        key="ct_node_uptime",
        translation_key="ct_node_uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m, n: m.node_uptime if m is not None else None,
    ),
    HomevoltCtNodeSensorEntityDescription(
        key="ct_firmware",
        translation_key="ct_firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m, n: n.version if n is not None else None,
    ),
    HomevoltCtNodeSensorEntityDescription(
        key="ct_ota_status",
        translation_key="ct_ota_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda m, n: n.ota_distribute_status if n is not None else None,
    ),
)


# ---------------------------------------------------------------------------
# Schedule sensors
# ---------------------------------------------------------------------------


def _find_current_entry(schedule: ScheduleData | None) -> ScheduleEntry | None:
    """Find the schedule entry that covers the current time."""
    if schedule is None or not schedule.entries:
        return None
    now = int(datetime.now(tz=timezone.utc).timestamp())
    for entry in schedule.entries:
        if entry.from_ts <= now < entry.to_ts:
            return entry
    return None


def _find_next_entry(schedule: ScheduleData | None) -> ScheduleEntry | None:
    """Find the next future schedule entry with a different action."""
    if schedule is None or not schedule.entries:
        return None
    now = int(datetime.now(tz=timezone.utc).timestamp())
    current = _find_current_entry(schedule)
    for entry in schedule.entries:
        if entry.from_ts >= now:
            if current is None or entry.type != current.type or entry.setpoint != current.setpoint:
                return entry
    return None


def _schedule_current_action(schedule: ScheduleData | None) -> str | None:
    """Return the current schedule action as a human-readable string."""
    entry = _find_current_entry(schedule)
    if entry is None:
        return None
    if entry.setpoint:
        return f"{entry.type_name} ({entry.setpoint} W)"
    return entry.type_name


def _schedule_current_attrs(schedule: ScheduleData | None) -> dict[str, Any] | None:
    """Return extra attributes for the current schedule action sensor."""
    if schedule is None:
        return None
    entry = _find_current_entry(schedule)
    attrs: dict[str, Any] = {"schedule_id": schedule.schedule_id}
    if entry is not None:
        attrs["type"] = entry.type
        attrs["setpoint"] = entry.setpoint
        attrs["from"] = datetime.fromtimestamp(entry.from_ts, tz=timezone.utc).isoformat()
        attrs["to"] = datetime.fromtimestamp(entry.to_ts, tz=timezone.utc).isoformat()
    attrs["schedule"] = [
        {
            "from": datetime.fromtimestamp(e.from_ts, tz=timezone.utc).isoformat(),
            "to": datetime.fromtimestamp(e.to_ts, tz=timezone.utc).isoformat(),
            "type": e.type_name,
            "setpoint": e.setpoint,
        }
        for e in schedule.entries
    ]
    return attrs


def _schedule_next_action(schedule: ScheduleData | None) -> str | None:
    """Return the next schedule action as a human-readable string."""
    entry = _find_next_entry(schedule)
    if entry is None:
        return None
    time_str = datetime.fromtimestamp(entry.from_ts, tz=timezone.utc).strftime("%H:%M")
    return f"{entry.type_name} at {time_str}"


SCHEDULE_SENSORS: tuple[HomevoltScheduleSensorEntityDescription, ...] = (
    HomevoltScheduleSensorEntityDescription(
        key="schedule_current_action",
        translation_key="schedule_current_action",
        value_fn=_schedule_current_action,
        attr_fn=_schedule_current_attrs,
    ),
    HomevoltScheduleSensorEntityDescription(
        key="schedule_next_action",
        translation_key="schedule_next_action",
        value_fn=_schedule_next_action,
    ),
    HomevoltScheduleSensorEntityDescription(
        key="schedule_entry_count",
        translation_key="schedule_entry_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: len(s.entries) if s is not None else None,
    ),
)


# ---------------------------------------------------------------------------
# Diagnostic sensors (EntityCategory.DIAGNOSTIC)
# ---------------------------------------------------------------------------

DIAGNOSTIC_SENSORS: tuple[HomevoltSensorEntityDescription, ...] = (
    HomevoltSensorEntityDescription(
        key="ems_info",
        translation_key="ems_info",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda agg: ", ".join(agg.ems_data.info_str) if agg.ems_data.info_str else None,
    ),
    HomevoltSensorEntityDescription(
        key="ems_warning",
        translation_key="ems_warning",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda agg: ", ".join(agg.ems_data.warning_str) if agg.ems_data.warning_str else None,
    ),
    HomevoltSensorEntityDescription(
        key="ems_alarm",
        translation_key="ems_alarm",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda agg: ", ".join(agg.ems_data.alarm_str) if agg.ems_data.alarm_str else None,
    ),
    HomevoltSensorEntityDescription(
        key="error_count",
        translation_key="error_count",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda agg: agg.error_cnt,
    ),
    HomevoltSensorEntityDescription(
        key="ems_error",
        translation_key="ems_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda agg: agg.error_str if agg.error_str else None,
    ),
)


# ---------------------------------------------------------------------------
# Status sensors (EntityCategory.DIAGNOSTIC, from /status.json)
# ---------------------------------------------------------------------------

STATUS_SENSORS: tuple[HomevoltStatusSensorEntityDescription, ...] = (
    HomevoltStatusSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: data.status.up_time if data.status is not None else None,
    ),
    HomevoltStatusSensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        value_fn=lambda data: data.status.wifi_status.rssi if data.status is not None else None,
    ),
    HomevoltStatusSensorEntityDescription(
        key="firmware_esp",
        translation_key="firmware_esp",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.firmware.esp if data.status is not None else None,
    ),
    HomevoltStatusSensorEntityDescription(
        key="firmware_efr",
        translation_key="firmware_efr",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.status.firmware.efr if data.status is not None else None,
    ),
)


# ---------------------------------------------------------------------------
# Error report sensor
# ---------------------------------------------------------------------------

def _error_report_status(entries: list[ErrorReportEntry]) -> str | None:
    """Return worst status from error report (ignoring 'unknown')."""
    if not entries:
        return None
    statuses = {e.activated for e in entries}
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    return "ok"


def _error_report_attrs(entries: list[ErrorReportEntry]) -> dict[str, Any]:
    """Return extra attributes for the error report sensor."""
    ok_count = sum(1 for e in entries if e.activated == "ok")
    warning_count = sum(1 for e in entries if e.activated == "warning")
    error_count = sum(1 for e in entries if e.activated == "error")
    warnings = [
        {"subsystem": e.sub_system_name, "name": e.error_name, "message": e.message}
        for e in entries if e.activated == "warning"
    ]
    errors = [
        {"subsystem": e.sub_system_name, "name": e.error_name, "message": e.message}
        for e in entries if e.activated == "error"
    ]
    return {
        "ok_count": ok_count,
        "warning_count": warning_count,
        "error_count": error_count,
        "warnings": warnings,
        "errors": errors,
    }


ERROR_REPORT_SENSOR_KEY = "error_report_status"


# ---------------------------------------------------------------------------
# Sensor entity classes
# ---------------------------------------------------------------------------

class HomevoltSystemSensor(HomevoltEntity, SensorEntity):
    """Sensor for system-level (aggregated EMS) data."""

    entity_description: HomevoltSensorEntityDescription

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        ecu_id: str,
        description: HomevoltSensorEntityDescription,
    ) -> None:
        """Initialize a system sensor."""
        super().__init__(coordinator, ecu_id)
        self.entity_description = description
        self._attr_unique_id = f"{ecu_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(
            self.coordinator.data.ems.aggregated,
        )


class HomevoltStatusSensor(HomevoltEntity, SensorEntity):
    """Sensor for status data (from /status.json)."""

    entity_description: HomevoltStatusSensorEntityDescription

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        ecu_id: str,
        description: HomevoltStatusSensorEntityDescription,
    ) -> None:
        """Initialize a status sensor."""
        super().__init__(coordinator, ecu_id)
        self.entity_description = description
        self._attr_unique_id = f"{ecu_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)


class HomevoltBmsSensor(HomevoltBmsEntity, SensorEntity):
    """Sensor for per-battery-module (BMS) data."""

    entity_description: HomevoltBmsSensorEntityDescription

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        ecu_id: str,
        bms_index: int,
        serial_number: str,
        description: HomevoltBmsSensorEntityDescription,
    ) -> None:
        """Initialize a BMS sensor."""
        super().__init__(coordinator, ecu_id, bms_index, serial_number)
        self.entity_description = description
        self._attr_unique_id = f"{serial_number}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        bms_list = self.coordinator.data.ems.aggregated.bms_data
        if self._bms_index >= len(bms_list):
            return None
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(bms_list[self._bms_index])


class HomevoltCtSensor(HomevoltSensorDeviceEntity, SensorEntity):
    """Sensor for CT clamp sensor data."""

    entity_description: HomevoltCtSensorEntityDescription

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        ecu_id: str,
        sensor_index: int,
        sensor_type: str,
        euid: str,
        description: HomevoltCtSensorEntityDescription,
    ) -> None:
        """Initialize a CT sensor."""
        super().__init__(coordinator, ecu_id, sensor_index, sensor_type, euid)
        self.entity_description = description
        self._attr_unique_id = f"{euid}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        sensors = self.coordinator.data.ems.sensors
        if self._sensor_index >= len(sensors):
            return None
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(sensors[self._sensor_index])


class HomevoltCtNodeSensor(HomevoltSensorDeviceEntity, SensorEntity):
    """Sensor for CT clamp node data (battery, temperature, firmware)."""

    entity_description: HomevoltCtNodeSensorEntityDescription

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        ecu_id: str,
        sensor_index: int,
        sensor_type: str,
        euid: str,
        node_id: int,
        description: HomevoltCtNodeSensorEntityDescription,
    ) -> None:
        """Initialize a CT node sensor."""
        super().__init__(coordinator, ecu_id, sensor_index, sensor_type, euid)
        self._node_id = node_id
        self.entity_description = description
        self._attr_unique_id = f"{euid}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        if self.entity_description.value_fn is None:
            return None
        metrics = self.coordinator.data.node_metrics.get(self._node_id)
        node_info = next(
            (n for n in self.coordinator.data.nodes if n.node_id == self._node_id),
            None,
        )
        return self.entity_description.value_fn(metrics, node_info)


class HomevoltScheduleSensor(HomevoltEntity, SensorEntity):
    """Sensor for schedule data."""

    entity_description: HomevoltScheduleSensorEntityDescription

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        ecu_id: str,
        description: HomevoltScheduleSensorEntityDescription,
    ) -> None:
        """Initialize a schedule sensor."""
        super().__init__(coordinator, ecu_id)
        self.entity_description = description
        self._attr_unique_id = f"{ecu_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data.schedule)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if self.entity_description.attr_fn is None:
            return None
        return self.entity_description.attr_fn(self.coordinator.data.schedule)


class HomevoltErrorReportSensor(HomevoltEntity, SensorEntity):
    """Sensor summarising the error report."""

    def __init__(
        self,
        coordinator: HomevoltCoordinator,
        ecu_id: str,
    ) -> None:
        """Initialize the error report sensor."""
        super().__init__(coordinator, ecu_id)
        self._attr_unique_id = f"{ecu_id}_{ERROR_REPORT_SENSOR_KEY}"
        self._attr_translation_key = ERROR_REPORT_SENSOR_KEY
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str | None:
        """Return the worst status across all error report entries."""
        return _error_report_status(self.coordinator.data.error_report)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return counts and details of warnings/errors."""
        if not self.coordinator.data.error_report:
            return None
        return _error_report_attrs(self.coordinator.data.error_report)


# ---------------------------------------------------------------------------
# Platform setup
# ---------------------------------------------------------------------------

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homevolt sensor entities from a config entry."""
    coordinator: HomevoltCoordinator = entry.runtime_data
    data = coordinator.data
    entities: list[SensorEntity] = []

    # Determine the ECU ID from the first EMS device in the list
    ems_list = data.ems.ems
    if not ems_list:
        _LOGGER.error("No EMS devices found in Homevolt data")
        return

    ecu_id = str(ems_list[0].ecu_id)

    # --- System sensors (aggregated EMS + voltage + current) ---
    all_system_descs = SYSTEM_SENSORS + VOLTAGE_SENSORS + CURRENT_SENSORS + DIAGNOSTIC_SENSORS
    for desc in all_system_descs:
        entities.append(HomevoltSystemSensor(coordinator, ecu_id, desc))

    # --- Status sensors ---
    for desc in STATUS_SENSORS:
        entities.append(HomevoltStatusSensor(coordinator, ecu_id, desc))

    # --- Error report sensor ---
    entities.append(HomevoltErrorReportSensor(coordinator, ecu_id))

    # --- Schedule sensors ---
    for desc in SCHEDULE_SENSORS:
        entities.append(HomevoltScheduleSensor(coordinator, ecu_id, desc))

    # --- BMS sensors (per battery module) ---
    aggregated = data.ems.aggregated
    for bms_idx, bms_info in enumerate(aggregated.bms_info):
        serial = bms_info.serial_number
        if not serial:
            serial = f"{ecu_id}_bms_{bms_idx}"
        for desc in BMS_SENSORS:
            entities.append(
                HomevoltBmsSensor(coordinator, ecu_id, bms_idx, serial, desc)
            )

    # --- CT clamp sensors (skip unconfigured/offline clamps) ---
    for sensor_idx, sensor_data in enumerate(data.ems.sensors):
        euid = sensor_data.euid
        sensor_type = sensor_data.type
        if not euid or euid == "0000000000000000":
            continue
        for desc in CT_SENSORS:
            entities.append(
                HomevoltCtSensor(
                    coordinator, ecu_id, sensor_idx, sensor_type, euid, desc
                )
            )
        # CT node sensors (battery voltage, temperature, firmware, etc.)
        if sensor_data.node_id:
            for desc in CT_NODE_SENSORS:
                entities.append(
                    HomevoltCtNodeSensor(
                        coordinator, ecu_id, sensor_idx, sensor_type, euid,
                        sensor_data.node_id, desc,
                    )
                )

    async_add_entities(entities)
