"""Data models for the Homevolt API responses."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EmsInfo:
    """EMS system information."""

    protocol_version: int = 0
    fw_version: str = ""
    rated_capacity: int = 0  # Wh
    rated_power: int = 0  # W

    @classmethod
    def from_dict(cls, data: dict) -> EmsInfo:
        return cls(
            protocol_version=data.get("protocol_version", 0),
            fw_version=data.get("fw_version", ""),
            rated_capacity=data.get("rated_capacity", 0),
            rated_power=data.get("rated_power", 0),
        )


@dataclass
class BmsInfo:
    """Battery Management System info."""

    fw_version: str = ""
    serial_number: str = ""
    rated_cap: int = 0  # Wh
    id: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> BmsInfo:
        return cls(
            fw_version=data.get("fw_version", ""),
            serial_number=data.get("serial_number", ""),
            rated_cap=data.get("rated_cap", 0),
            id=data.get("id", 0),
        )


@dataclass
class InvInfo:
    """Inverter information."""

    fw_version: str = ""
    serial_number: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> InvInfo:
        return cls(
            fw_version=data.get("fw_version", ""),
            serial_number=data.get("serial_number", ""),
        )


@dataclass
class EmsConfig:
    """EMS configuration."""

    grid_code_preset: int = 0
    grid_code_preset_str: str = ""
    control_timeout: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> EmsConfig:
        return cls(
            grid_code_preset=data.get("grid_code_preset", 0),
            grid_code_preset_str=data.get("grid_code_preset_str", ""),
            control_timeout=data.get("control_timeout", False),
        )


@dataclass
class EmsControl:
    """EMS control state."""

    mode_sel: int = 0
    mode_sel_str: str = ""
    pwr_ref: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> EmsControl:
        return cls(
            mode_sel=data.get("mode_sel", 0),
            mode_sel_str=data.get("mode_sel_str", ""),
            pwr_ref=data.get("pwr_ref", 0),
        )


@dataclass
class EmsData:
    """Real-time EMS data."""

    timestamp_ms: int = 0
    state: int = 0
    state_str: str = ""
    info: int = 0
    info_str: list[str] = field(default_factory=list)
    warning: int = 0
    warning_str: list[str] = field(default_factory=list)
    alarm: int = 0
    alarm_str: list[str] = field(default_factory=list)
    phase_angle: int = 0
    frequency: int = 0  # centi-Hz (50040 = 50.040 Hz)
    phase_seq: int = 0
    power: int = 0  # W (positive=discharge, negative=charge)
    apparent_power: int = 0  # VA
    reactive_power: int = 0  # var
    energy_produced: int = 0  # Wh
    energy_consumed: int = 0  # Wh
    sys_temp: int = 0  # decicelsius (60 = 6.0 C)
    avail_cap: int = 0  # Wh
    freq_res_state: int = 0
    soc_avg: int = 0  # percentage

    @classmethod
    def from_dict(cls, data: dict) -> EmsData:
        return cls(
            timestamp_ms=data.get("timestamp_ms", 0),
            state=data.get("state", 0),
            state_str=data.get("state_str", ""),
            info=data.get("info", 0),
            info_str=data.get("info_str", []),
            warning=data.get("warning", 0),
            warning_str=data.get("warning_str", []),
            alarm=data.get("alarm", 0),
            alarm_str=data.get("alarm_str", []),
            phase_angle=data.get("phase_angle", 0),
            frequency=data.get("frequency", 0),
            phase_seq=data.get("phase_seq", 0),
            power=data.get("power", 0),
            apparent_power=data.get("apparent_power", 0),
            reactive_power=data.get("reactive_power", 0),
            energy_produced=data.get("energy_produced", 0),
            energy_consumed=data.get("energy_consumed", 0),
            sys_temp=data.get("sys_temp", 0),
            avail_cap=data.get("avail_cap", 0),
            freq_res_state=data.get("freq_res_state", 0),
            soc_avg=data.get("soc_avg", 0),
        )


@dataclass
class BmsData:
    """Per-battery module data."""

    energy_avail: int = 0  # Wh
    cycle_count: int = 0
    soc: int = 0  # percentage
    state: int = 0
    state_str: str = ""
    alarm: int = 0
    alarm_str: list[str] = field(default_factory=list)
    tmin: int = 0  # decicelsius
    tmax: int = 0  # decicelsius

    @classmethod
    def from_dict(cls, data: dict) -> BmsData:
        return cls(
            energy_avail=data.get("energy_avail", 0),
            cycle_count=data.get("cycle_count", 0),
            soc=data.get("soc", 0),
            state=data.get("state", 0),
            state_str=data.get("state_str", ""),
            alarm=data.get("alarm", 0),
            alarm_str=data.get("alarm_str", []),
            tmin=data.get("tmin", 0),
            tmax=data.get("tmax", 0),
        )


@dataclass
class EmsPrediction:
    """Available charge/discharge predictions."""

    avail_ch_pwr: int = 0  # W
    avail_di_pwr: int = 0  # W
    avail_ch_energy: int = 0  # Wh
    avail_di_energy: int = 0  # Wh
    avail_inv_ch_pwr: int = 0  # W
    avail_inv_di_pwr: int = 0  # W
    avail_group_fuse_ch_pwr: int = 0  # W
    avail_group_fuse_di_pwr: int = 0  # W

    @classmethod
    def from_dict(cls, data: dict) -> EmsPrediction:
        return cls(
            avail_ch_pwr=data.get("avail_ch_pwr", 0),
            avail_di_pwr=data.get("avail_di_pwr", 0),
            avail_ch_energy=data.get("avail_ch_energy", 0),
            avail_di_energy=data.get("avail_di_energy", 0),
            avail_inv_ch_pwr=data.get("avail_inv_ch_pwr", 0),
            avail_inv_di_pwr=data.get("avail_inv_di_pwr", 0),
            avail_group_fuse_ch_pwr=data.get("avail_group_fuse_ch_pwr", 0),
            avail_group_fuse_di_pwr=data.get("avail_group_fuse_di_pwr", 0),
        )


@dataclass
class EmsVoltage:
    """Phase voltages (in decivolts, e.g. 2303 = 230.3V)."""

    l1: int = 0
    l2: int = 0
    l3: int = 0
    l1_l2: int = 0
    l2_l3: int = 0
    l3_l1: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> EmsVoltage:
        return cls(
            l1=data.get("l1", 0),
            l2=data.get("l2", 0),
            l3=data.get("l3", 0),
            l1_l2=data.get("l1_l2", 0),
            l2_l3=data.get("l2_l3", 0),
            l3_l1=data.get("l3_l1", 0),
        )


@dataclass
class EmsCurrent:
    """Phase currents (in deciamps)."""

    l1: int = 0
    l2: int = 0
    l3: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> EmsCurrent:
        return cls(
            l1=data.get("l1", 0),
            l2=data.get("l2", 0),
            l3=data.get("l3", 0),
        )


@dataclass
class EmsAggregate:
    """Aggregated energy data."""

    imported_kwh: float = 0.0
    exported_kwh: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> EmsAggregate:
        return cls(
            imported_kwh=data.get("imported_kwh", 0.0),
            exported_kwh=data.get("exported_kwh", 0.0),
        )


@dataclass
class EmsDevice:
    """A single EMS device (inverter + batteries)."""

    ecu_id: int = 0
    ecu_host: str = ""
    ecu_version: str = ""
    error: int = 0
    error_str: str = ""
    op_state: int = 0
    op_state_str: str = ""
    ems_info: EmsInfo = field(default_factory=EmsInfo)
    bms_info: list[BmsInfo] = field(default_factory=list)
    inv_info: InvInfo = field(default_factory=InvInfo)
    ems_config: EmsConfig = field(default_factory=EmsConfig)
    ems_control: EmsControl = field(default_factory=EmsControl)
    ems_data: EmsData = field(default_factory=EmsData)
    bms_data: list[BmsData] = field(default_factory=list)
    ems_prediction: EmsPrediction = field(default_factory=EmsPrediction)
    ems_voltage: EmsVoltage = field(default_factory=EmsVoltage)
    ems_current: EmsCurrent = field(default_factory=EmsCurrent)
    ems_aggregate: EmsAggregate = field(default_factory=EmsAggregate)
    error_cnt: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> EmsDevice:
        return cls(
            ecu_id=data.get("ecu_id", 0),
            ecu_host=data.get("ecu_host", ""),
            ecu_version=data.get("ecu_version", ""),
            error=data.get("error", 0),
            error_str=data.get("error_str", ""),
            op_state=data.get("op_state", 0),
            op_state_str=data.get("op_state_str", ""),
            ems_info=EmsInfo.from_dict(data.get("ems_info", {})),
            bms_info=[BmsInfo.from_dict(b) for b in data.get("bms_info", [])],
            inv_info=InvInfo.from_dict(data.get("inv_info", {})),
            ems_config=EmsConfig.from_dict(data.get("ems_config", {})),
            ems_control=EmsControl.from_dict(data.get("ems_control", {})),
            ems_data=EmsData.from_dict(data.get("ems_data", {})),
            bms_data=[BmsData.from_dict(b) for b in data.get("bms_data", [])],
            ems_prediction=EmsPrediction.from_dict(data.get("ems_prediction", {})),
            ems_voltage=EmsVoltage.from_dict(data.get("ems_voltage", {})),
            ems_current=EmsCurrent.from_dict(data.get("ems_current", {})),
            ems_aggregate=EmsAggregate.from_dict(data.get("ems_aggregate", {})),
            error_cnt=data.get("error_cnt", 0),
        )


@dataclass
class PhaseData:
    """Per-phase CT clamp measurement."""

    voltage: float = 0.0
    amp: float = 0.0
    power: float = 0.0
    pf: float = 0.0  # power factor

    @classmethod
    def from_dict(cls, data: dict) -> PhaseData:
        return cls(
            voltage=data.get("voltage", 0.0),
            amp=data.get("amp", 0.0),
            power=data.get("power", 0.0),
            pf=data.get("pf", 0.0),
        )


@dataclass
class SensorData:
    """CT clamp sensor data (grid, solar, load)."""

    type: str = ""
    node_id: int = 0
    euid: str = ""
    interface: int = 0
    available: bool = False
    rssi: float = 0.0
    average_rssi: float = 0.0
    pdr: float = 0.0  # packet delivery rate %
    phase: list[PhaseData] = field(default_factory=list)
    frequency: float = 0.0
    total_power: int = 0  # W
    energy_imported: float = 0.0  # kWh
    energy_exported: float = 0.0  # kWh
    timestamp: int = 0
    timestamp_str: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> SensorData:
        return cls(
            type=data.get("type", ""),
            node_id=data.get("node_id", 0),
            euid=data.get("euid", ""),
            interface=data.get("interface", 0),
            available=data.get("available", False),
            rssi=data.get("rssi", 0.0),
            average_rssi=data.get("average_rssi", 0.0),
            pdr=data.get("pdr", 0.0),
            phase=[PhaseData.from_dict(p) for p in data.get("phase", [])],
            frequency=data.get("frequency", 0.0),
            total_power=data.get("total_power", 0),
            energy_imported=data.get("energy_imported", 0.0),
            energy_exported=data.get("energy_exported", 0.0),
            timestamp=data.get("timestamp", 0),
            timestamp_str=data.get("timestamp_str", ""),
        )


@dataclass
class HomevoltEmsResponse:
    """Top-level response from /ems.json."""

    type: str = ""
    ts: int = 0
    ems: list[EmsDevice] = field(default_factory=list)
    aggregated: EmsDevice = field(default_factory=EmsDevice)
    sensors: list[SensorData] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> HomevoltEmsResponse:
        return cls(
            type=data.get("$type", ""),
            ts=data.get("ts", 0),
            ems=[EmsDevice.from_dict(e) for e in data.get("ems", [])],
            aggregated=EmsDevice.from_dict(data.get("aggregated", {})),
            sensors=[SensorData.from_dict(s) for s in data.get("sensors", [])],
        )


@dataclass
class WifiStatus:
    """WiFi status from /status.json."""

    wifi_mode: str = ""
    ip: str = ""
    ssid: str = ""
    rssi: int = 0
    connected: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> WifiStatus:
        return cls(
            wifi_mode=data.get("wifi_mode", ""),
            ip=data.get("ip", ""),
            ssid=data.get("ssid", ""),
            rssi=data.get("rssi", 0),
            connected=data.get("connected", False),
        )


@dataclass
class MqttStatus:
    """MQTT status from /status.json."""

    connected: bool = False
    subscribed: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> MqttStatus:
        return cls(
            connected=data.get("connected", False),
            subscribed=data.get("subscribed", False),
        )


@dataclass
class LteStatus:
    """LTE status from /status.json."""

    operator_name: str = ""
    band: str = ""
    rssi_db: int = 0
    pdp_active: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> LteStatus:
        return cls(
            operator_name=data.get("operator_name", ""),
            band=data.get("band", ""),
            rssi_db=data.get("rssi_db", 0),
            pdp_active=data.get("pdp_active", False),
        )


@dataclass
class FirmwareInfo:
    """Firmware versions from /status.json."""

    esp: str = ""
    efr: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> FirmwareInfo:
        return cls(
            esp=data.get("esp", ""),
            efr=data.get("efr", ""),
        )


@dataclass
class HomevoltStatusResponse:
    """Response from /status.json."""

    up_time: int = 0
    firmware: FirmwareInfo = field(default_factory=FirmwareInfo)
    wifi_status: WifiStatus = field(default_factory=WifiStatus)
    mqtt_status: MqttStatus = field(default_factory=MqttStatus)
    lte_status: LteStatus = field(default_factory=LteStatus)

    @classmethod
    def from_dict(cls, data: dict) -> HomevoltStatusResponse:
        return cls(
            up_time=data.get("up_time", 0),
            firmware=FirmwareInfo.from_dict(data.get("firmware", {})),
            wifi_status=WifiStatus.from_dict(data.get("wifi_status", {})),
            mqtt_status=MqttStatus.from_dict(data.get("mqtt_status", {})),
            lte_status=LteStatus.from_dict(data.get("lte_status", {})),
        )


@dataclass
class ErrorReportEntry:
    """Single entry from /error_report.json."""

    sub_system_id: int = 0
    sub_system_name: str = ""
    error_id: int = 0
    error_name: str = ""
    activated: str = ""  # "ok", "warning", "error", "unknown"
    message: str = ""
    details: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> ErrorReportEntry:
        return cls(
            sub_system_id=data.get("sub_system_id", 0),
            sub_system_name=data.get("sub_system_name", ""),
            error_id=data.get("error_id", 0),
            error_name=data.get("error_name", ""),
            activated=data.get("activated", ""),
            message=data.get("message", ""),
            details=data.get("details", []),
        )


@dataclass
class HomevoltData:
    """Combined data from all API endpoints."""

    ems: HomevoltEmsResponse = field(default_factory=HomevoltEmsResponse)
    status: HomevoltStatusResponse | None = None
    error_report: list[ErrorReportEntry] = field(default_factory=list)
