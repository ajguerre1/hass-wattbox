"""Constants for wattbox."""

from datetime import timedelta
from typing import Final, TypedDict

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTime,
)

# Base component constants
DOMAIN: Final[str] = "wattbox"
DOMAIN_DATA: Final[str] = f"{DOMAIN}_data"
VERSION: Final[str] = "1.1.0"
PLATFORMS: Final[list[str]] = ["binary_sensor", "button", "sensor", "switch"]
ISSUE_URL: Final[str] = "https://github.com/eseglem/hass-wattbox/issues"

STARTUP: Final[str] = f"""
-------------------------------------------------------------------
{DOMAIN}
Version: {VERSION}
This is a custom component
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""

# Icons
ICON: Final[str] = "mdi:power"
PLUG_ICON: Final[str] = "mdi:power-socket-us"
RESTART_ICON: Final[str] = "mdi:restart"

# Defaults
DEFAULT_NAME: Final[str] = "WattBox"
DEFAULT_PASSWORD: Final[str] = DOMAIN
DEFAULT_PORT: Final[int] = 80
DEFAULT_USER: Final[str] = DOMAIN
DEFAULT_SCAN_INTERVAL: Final[timedelta] = timedelta(seconds=30)

TOPIC_UPDATE: Final[str] = "{}_data_update_{}"

# config options
CONF_NAME_REGEXP: Final[str] = "name_regexp"
CONF_SKIP_REGEXP: Final[str] = "skip_regexp"

#: Per-outlet metering. Off by default: it costs one extra request per outlet
#: on every poll and creates no entities unless explicitly enabled.
CONF_OUTLET_METERING: Final[str] = "outlet_metering"
DEFAULT_OUTLET_METERING: Final[bool] = False

# Connection type. Chosen explicitly rather than inferred from the port,
# because guessing sends 800-series users to the HTTP driver, which answers
# with a 401 and no indication of why.
CONF_CONNECTION_TYPE: Final[str] = "connection_type"
CONNECTION_HTTP: Final[str] = "http"
CONNECTION_TELNET: Final[str] = "telnet"
CONNECTION_SSH: Final[str] = "ssh"
CONNECTION_TYPES: Final[dict[str, int]] = {
    CONNECTION_TELNET: 23,
    CONNECTION_HTTP: 80,
    CONNECTION_SSH: 22,
}
DEFAULT_CONNECTION_TYPE: Final[str] = CONNECTION_TELNET


class _BinarySensorDict(TypedDict):
    """TypedDict for use in BINARY_SENSOR_TYPES"""

    name: str
    device_class: BinarySensorDeviceClass | None
    flipped: bool


BINARY_SENSOR_TYPES: Final[dict[str, _BinarySensorDict]] = {
    "audible_alarm": {
        "name": "Audible Alarm",
        "device_class": BinarySensorDeviceClass.SOUND,
        "flipped": False,
    },
    "auto_reboot": {"name": "Auto Reboot", "device_class": None, "flipped": False},
    "battery_health": {
        "name": "Battery Health",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "flipped": True,
    },
    "battery_test": {"name": "Battery Test", "device_class": None, "flipped": False},
    "cloud_status": {
        "name": "Cloud Status",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "flipped": False,
    },
    "has_ups": {"name": "Has UPS", "device_class": None, "flipped": False},
    "mute": {"name": "Mute", "device_class": None, "flipped": False},
    "power_lost": {
        "name": "Power",
        "device_class": BinarySensorDeviceClass.PLUG,
        "flipped": True,
    },
    "safe_voltage_status": {
        "name": "Safe Voltage Status",
        "device_class": BinarySensorDeviceClass.SAFETY,
        "flipped": True,
    },
}


class _SensorTypeDict(TypedDict):
    name: str
    unit: str
    icon: str
    device_class: SensorDeviceClass | None
    state_class: SensorStateClass | None


SENSOR_TYPES: Final[dict[str, _SensorTypeDict]] = {
    "battery_charge": {
        "name": "Battery Charge",
        "unit": PERCENTAGE,
        "icon": "mdi:battery",
        "device_class": SensorDeviceClass.BATTERY,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "battery_load": {
        "name": "Battery Load",
        "unit": PERCENTAGE,
        "icon": "mdi:gauge",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "current_value": {
        "name": "Current",
        "unit": UnitOfElectricCurrent.AMPERE,
        "icon": "mdi:current-ac",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "est_run_time": {
        "name": "Estimated Run Time",
        "unit": UnitOfTime.MINUTES,
        "icon": "mdi:timer",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "power_value": {
        "name": "Power",
        "unit": UnitOfPower.WATT,
        "icon": "mdi:lightbulb-outline",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "voltage_value": {
        "name": "Voltage",
        "unit": UnitOfElectricPotential.VOLT,
        "icon": "mdi:lightning-bolt-circle",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
}
