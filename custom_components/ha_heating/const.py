"""Constants for the HA Heating integration."""

DOMAIN = "ha_heating"

# Entry types
CONF_ENTRY_TYPE = "entry_type"
ENTRY_TYPE_HUB = "hub"
ENTRY_TYPE_ROOM = "room"

# Global Hub configuration keys
CONF_GAS_PRICE_SENSOR = "gas_price_sensor"
CONF_ELECTRIC_PRICE_SENSOR = "electric_price_sensor"
CONF_OUTDOOR_TEMP_SENSOR = "outdoor_temp_sensor"
CONF_SOLAR_EXPORT_SENSOR = "solar_export_sensor"
CONF_VACATION_CALENDAR = "vacation_calendar"
CONF_CALENDAR_FILTER = "calendar_filter"
CONF_CYCLE_TYPE = "cycle_type"
CONF_CYCLE_ANCHOR_DATE = "cycle_anchor_date"
CONF_CYCLE_ENTITY = "cycle_entity"

# Room configuration keys
CONF_AREA_ID = "area_id"
CONF_ROOM_NAME = "room_name"
CONF_ROOM_TEMP_SENSOR = "room_temp_sensor"
CONF_TRVS = "trvs"
CONF_WINDOW_SENSORS = "window_sensors"
CONF_WINDOW_OPEN_DELAY = "window_open_delay"
CONF_WINDOW_CLOSE_DELAY = "window_close_delay"
CONF_MASTER_THERMOSTAT = "master_thermostat"
CONF_MASTER_CONTROL_MODE = "master_control_mode"
CONF_MASTER_BOOST_TEMP = "master_boost_temp"
CONF_MASTER_IDLE_TEMP = "master_idle_temp"
CONF_AC_ENTITY = "ac_entity"
CONF_AC_QUIET_START = "ac_quiet_start"
CONF_AC_QUIET_END = "ac_quiet_end"
CONF_AC_ENABLE_COOLING = "ac_enable_cooling"
CONF_SCHEDULE_WEEK_A = "schedule_week_a"
CONF_SCHEDULE_WEEK_B = "schedule_week_b"

# Presets configuration keys
CONF_TEMP_COMFORT = "temp_comfort"
CONF_TEMP_ECO = "temp_eco"
CONF_TEMP_SLEEP = "temp_sleep"
CONF_TEMP_AWAY = "temp_away"
CONF_TEMP_BOOST = "temp_boost"
CONF_TEMP_HOLIDAY = "temp_holiday"

# Master control modes
MASTER_MODE_SETPOINT_BOOST = "setpoint_boost"
MASTER_MODE_HVAC_SWITCH = "hvac_switch"
MASTER_MODE_BOTH = "both"

# Cycle modes
CYCLE_ISO_EVEN_ODD = "iso_even_odd"
CYCLE_ANCHOR_DATE = "anchor_date"
CYCLE_EXTERNAL_ENTITY = "external_entity"

# Presets
PRESET_COMFORT = "comfort"
PRESET_ECO = "eco"
PRESET_SLEEP = "sleep"
PRESET_AWAY = "away"
PRESET_BOOST = "boost"
PRESET_HOLIDAY = "holiday"

# Default values
DEFAULT_WINDOW_OPEN_DELAY = 30  # seconds
DEFAULT_WINDOW_CLOSE_DELAY = 10  # seconds
DEFAULT_FROST_TEMP = 7.0  # °C

DEFAULT_MASTER_BOOST_TEMP = 25.0  # °C
DEFAULT_MASTER_IDLE_TEMP = 15.0  # °C
DEFAULT_HYSTERESIS_ON = 0.5  # °C
DEFAULT_HYSTERESIS_OFF = 0.1  # °C
DEFAULT_MIN_CYCLE_DURATION = 300  # 5 min anti-cycling
DEFAULT_MIN_OFF_DURATION = 180  # 3 min anti-cycling

DEFAULT_GAS_KWH_PER_M3 = 9.0  # Caloric value * efficiency
DEFAULT_AC_COOL_DEADBAND = 1.0  # °C

DEFAULT_TEMP_COMFORT = 20.5
DEFAULT_TEMP_ECO = 18.0
DEFAULT_TEMP_SLEEP = 16.0
DEFAULT_TEMP_AWAY = 15.0
DEFAULT_TEMP_BOOST = 22.0
DEFAULT_TEMP_HOLIDAY = 15.0

# Active Heat Source States
HEAT_SOURCE_IDLE = "idle"
HEAT_SOURCE_GAS = "gas"
HEAT_SOURCE_AC_HEAT = "ac_heat"
HEAT_SOURCE_AC_COOL = "ac_cool"
HEAT_SOURCE_PAUSED_WINDOW = "window_open"

