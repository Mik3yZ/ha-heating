"""Config flow for HA Heating integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import area_registry as ar, selector

from .const import (
    CONF_AC_ENABLE_COOLING,
    CONF_AC_ENTITY,
    CONF_AC_QUIET_END,
    CONF_AC_QUIET_START,
    CONF_AREA_ID,
    CONF_CALENDAR_FILTER,
    CONF_CYCLE_ANCHOR_DATE,
    CONF_CYCLE_ENTITY,
    CONF_CYCLE_TYPE,
    CONF_ELECTRIC_PRICE_SENSOR,
    CONF_ENTRY_TYPE,
    CONF_GAS_PRICE_SENSOR,
    CONF_MASTER_BOOST_TEMP,
    CONF_MASTER_CONTROL_MODE,
    CONF_MASTER_IDLE_TEMP,
    CONF_MASTER_THERMOSTAT,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMP_SENSOR,
    CONF_SCHEDULE_WEEK_A,
    CONF_SCHEDULE_WEEK_B,
    CONF_SOLAR_EXPORT_SENSOR,
    CONF_TEMP_AWAY,
    CONF_TEMP_BOOST,
    CONF_TEMP_COMFORT,
    CONF_TEMP_ECO,
    CONF_TEMP_HOLIDAY,
    CONF_TEMP_SLEEP,
    CONF_TRVS,
    CONF_VACATION_CALENDAR,
    CONF_WINDOW_CLOSE_DELAY,
    CONF_WINDOW_OPEN_DELAY,
    CONF_WINDOW_SENSORS,
    CYCLE_ANCHOR_DATE,
    CYCLE_EXTERNAL_ENTITY,
    CYCLE_ISO_EVEN_ODD,
    DEFAULT_MASTER_BOOST_TEMP,
    DEFAULT_MASTER_IDLE_TEMP,
    DEFAULT_TEMP_AWAY,
    DEFAULT_TEMP_BOOST,
    DEFAULT_TEMP_COMFORT,
    DEFAULT_TEMP_ECO,
    DEFAULT_TEMP_HOLIDAY,
    DEFAULT_TEMP_SLEEP,
    DEFAULT_WINDOW_CLOSE_DELAY,
    DEFAULT_WINDOW_OPEN_DELAY,
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_ROOM,
    MASTER_MODE_BOTH,
    MASTER_MODE_HVAC_SWITCH,
    MASTER_MODE_SETPOINT_BOOST,
)

_LOGGER = logging.getLogger(__name__)


class HAHeatingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Heating."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["hub", "room"],
        )

    async def async_step_hub(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle central hub setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_ENTRY_TYPE] = ENTRY_TYPE_HUB
            return self.async_create_entry(
                title="HA Heating Central Hub",
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Optional(CONF_GAS_PRICE_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_ELECTRIC_PRICE_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_OUTDOOR_TEMP_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_SOLAR_EXPORT_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_VACATION_CALENDAR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="calendar")
                ),
                vol.Optional(CONF_CALENDAR_FILTER, default="Vakantie"): str,
                vol.Required(CONF_CYCLE_TYPE, default=CYCLE_ISO_EVEN_ODD): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": CYCLE_ISO_EVEN_ODD, "label": "Even / Oneven ISO Week"},
                            {"value": CYCLE_ANCHOR_DATE, "label": "14-daagse Cyclus vanaf Startdatum"},
                            {"value": CYCLE_EXTERNAL_ENTITY, "label": "Externe Sensor / Helper"},
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_CYCLE_ANCHOR_DATE): str,
                vol.Optional(CONF_CYCLE_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig()
                ),
            }
        )

        return self.async_show_form(
            step_id="hub",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_room(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle room / zone setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            area_id = user_input.get(CONF_AREA_ID)

            # Prevent duplicate rooms for the same Home Assistant Area
            if area_id:
                for entry in self._async_current_entries():
                    if (
                        entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_ROOM
                        and entry.data.get(CONF_AREA_ID) == area_id
                    ):
                        errors[CONF_AREA_ID] = "area_already_configured"
                        break

            if not errors:
                area_reg = ar.async_get(self.hass)
                area = area_reg.async_get_area(area_id) if area_id else None
                default_name = area.name if area else "Kamer"
                room_name = user_input.get(CONF_ROOM_NAME) or default_name
                user_input[CONF_ROOM_NAME] = room_name
                user_input[CONF_ENTRY_TYPE] = ENTRY_TYPE_ROOM

                return self.async_create_entry(
                    title=f"Kamer: {room_name}",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_AREA_ID): selector.AreaSelector(
                    selector.AreaSelectorConfig()
                ),
                vol.Optional(CONF_ROOM_NAME): str,
                vol.Optional(CONF_ROOM_TEMP_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_TRVS): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate", multiple=True)
                ),
                vol.Optional(CONF_WINDOW_SENSORS): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
                ),
                vol.Optional(
                    CONF_WINDOW_OPEN_DELAY, default=DEFAULT_WINDOW_OPEN_DELAY
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=600, step=5)
                ),
                vol.Optional(
                    CONF_WINDOW_CLOSE_DELAY, default=DEFAULT_WINDOW_CLOSE_DELAY
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=0, max=300, step=5)
                ),
                vol.Optional(CONF_MASTER_THERMOSTAT): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate")
                ),
                vol.Optional(
                    CONF_MASTER_CONTROL_MODE, default=MASTER_MODE_SETPOINT_BOOST
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {"value": MASTER_MODE_SETPOINT_BOOST, "label": "Setpoint Boost (o.a. Moes BHT-002)"},
                            {"value": MASTER_MODE_HVAC_SWITCH, "label": "HVAC Switch (Heat vs Off)"},
                            {"value": MASTER_MODE_BOTH, "label": "Gecombineerd (Beide)"},
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_MASTER_BOOST_TEMP, default=DEFAULT_MASTER_BOOST_TEMP
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=18, max=32, step=0.5)
                ),
                vol.Optional(
                    CONF_MASTER_IDLE_TEMP, default=DEFAULT_MASTER_IDLE_TEMP
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=20, step=0.5)
                ),
                vol.Optional(CONF_AC_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate")
                ),
                vol.Optional(CONF_AC_QUIET_START, default="22:00"): str,
                vol.Optional(CONF_AC_QUIET_END, default="07:00"): str,
                vol.Optional(CONF_AC_ENABLE_COOLING, default=True): bool,
                vol.Optional(CONF_SCHEDULE_WEEK_A): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="schedule")
                ),
                vol.Optional(CONF_SCHEDULE_WEEK_B): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="schedule")
                ),
                vol.Optional(CONF_TEMP_COMFORT, default=DEFAULT_TEMP_COMFORT): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=15, max=26, step=0.5)
                ),
                vol.Optional(CONF_TEMP_ECO, default=DEFAULT_TEMP_ECO): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=12, max=22, step=0.5)
                ),
                vol.Optional(CONF_TEMP_SLEEP, default=DEFAULT_TEMP_SLEEP): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=20, step=0.5)
                ),
                vol.Optional(CONF_TEMP_AWAY, default=DEFAULT_TEMP_AWAY): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=18, step=0.5)
                ),
                vol.Optional(CONF_TEMP_BOOST, default=DEFAULT_TEMP_BOOST): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=18, max=28, step=0.5)
                ),
                vol.Optional(CONF_TEMP_HOLIDAY, default=DEFAULT_TEMP_HOLIDAY): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=18, step=0.5)
                ),
            }
        )

        return self.async_show_form(
            step_id="room",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create options flow handler."""
        return HAHeatingOptionsFlowHandler(config_entry)


class HAHeatingOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for HA Heating entries."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage entry options."""
        entry_type = self.config_entry.data.get(CONF_ENTRY_TYPE)

        if user_input is not None:
            # Update entry data and options
            new_data = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data=user_input)

        current_data = {**self.config_entry.data, **self.config_entry.options}

        if entry_type == ENTRY_TYPE_HUB:
            schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_GAS_PRICE_SENSOR,
                        description={"suggested_value": current_data.get(CONF_GAS_PRICE_SENSOR)},
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
                    vol.Optional(
                        CONF_ELECTRIC_PRICE_SENSOR,
                        description={"suggested_value": current_data.get(CONF_ELECTRIC_PRICE_SENSOR)},
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
                    vol.Optional(
                        CONF_OUTDOOR_TEMP_SENSOR,
                        description={"suggested_value": current_data.get(CONF_OUTDOOR_TEMP_SENSOR)},
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
                    vol.Optional(
                        CONF_SOLAR_EXPORT_SENSOR,
                        description={"suggested_value": current_data.get(CONF_SOLAR_EXPORT_SENSOR)},
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
                    vol.Optional(
                        CONF_VACATION_CALENDAR,
                        description={"suggested_value": current_data.get(CONF_VACATION_CALENDAR)},
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain="calendar")),
                    vol.Optional(
                        CONF_CALENDAR_FILTER,
                        default=current_data.get(CONF_CALENDAR_FILTER, "Vakantie"),
                    ): str,
                    vol.Required(
                        CONF_CYCLE_TYPE,
                        default=current_data.get(CONF_CYCLE_TYPE, CYCLE_ISO_EVEN_ODD),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": CYCLE_ISO_EVEN_ODD, "label": "Even / Oneven ISO Week"},
                                {"value": CYCLE_ANCHOR_DATE, "label": "14-daagse Cyclus vanaf Startdatum"},
                                {"value": CYCLE_EXTERNAL_ENTITY, "label": "Externe Sensor / Helper"},
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            )
        else:
            schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_AREA_ID,
                        description={"suggested_value": current_data.get(CONF_AREA_ID)},
                    ): selector.AreaSelector(selector.AreaSelectorConfig()),
                    vol.Optional(
                        CONF_ROOM_NAME,
                        default=current_data.get(CONF_ROOM_NAME, "Room"),
                    ): str,
                    vol.Optional(
                        CONF_ROOM_TEMP_SENSOR,
                        description={"suggested_value": current_data.get(CONF_ROOM_TEMP_SENSOR)},
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
                    vol.Required(
                        CONF_TRVS,
                        default=current_data.get(CONF_TRVS, []),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="climate", multiple=True)
                    ),
                    vol.Optional(
                        CONF_WINDOW_SENSORS,
                        default=current_data.get(CONF_WINDOW_SENSORS, []),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
                    ),
                    vol.Optional(
                        CONF_MASTER_THERMOSTAT,
                        description={"suggested_value": current_data.get(CONF_MASTER_THERMOSTAT)},
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain="climate")),
                    vol.Optional(
                        CONF_MASTER_CONTROL_MODE,
                        default=current_data.get(CONF_MASTER_CONTROL_MODE, MASTER_MODE_SETPOINT_BOOST),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": MASTER_MODE_SETPOINT_BOOST, "label": "Setpoint Boost (Moes BHT-002)"},
                                {"value": MASTER_MODE_HVAC_SWITCH, "label": "HVAC Switch (Heat vs Off)"},
                                {"value": MASTER_MODE_BOTH, "label": "Gecombineerd (Beide)"},
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_AC_ENTITY,
                        description={"suggested_value": current_data.get(CONF_AC_ENTITY)},
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain="climate")),
                    vol.Optional(
                        CONF_AC_QUIET_START,
                        default=current_data.get(CONF_AC_QUIET_START, "22:00"),
                    ): str,
                    vol.Optional(
                        CONF_AC_QUIET_END,
                        default=current_data.get(CONF_AC_QUIET_END, "07:00"),
                    ): str,
                    vol.Optional(
                        CONF_TEMP_COMFORT,
                        default=current_data.get(CONF_TEMP_COMFORT, DEFAULT_TEMP_COMFORT),
                    ): selector.NumberSelector(selector.NumberSelectorConfig(min=15, max=26, step=0.5)),
                    vol.Optional(
                        CONF_TEMP_ECO,
                        default=current_data.get(CONF_TEMP_ECO, DEFAULT_TEMP_ECO),
                    ): selector.NumberSelector(selector.NumberSelectorConfig(min=12, max=22, step=0.5)),
                    vol.Optional(
                        CONF_TEMP_SLEEP,
                        default=current_data.get(CONF_TEMP_SLEEP, DEFAULT_TEMP_SLEEP),
                    ): selector.NumberSelector(selector.NumberSelectorConfig(min=10, max=20, step=0.5)),
                }
            )

        return self.async_show_form(step_id="init", data_schema=schema)

