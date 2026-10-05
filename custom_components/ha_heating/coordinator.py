"""DataUpdateCoordinator for HA Heating integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_CALENDAR_FILTER,
    CONF_CYCLE_ANCHOR_DATE,
    CONF_CYCLE_ENTITY,
    CONF_CYCLE_TYPE,
    CONF_ELECTRIC_PRICE_SENSOR,
    CONF_GAS_PRICE_SENSOR,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_SOLAR_EXPORT_SENSOR,
    CONF_VACATION_CALENDAR,
    CYCLE_ISO_EVEN_ODD,
    DEFAULT_MASTER_BOOST_OFFSET,
    DEFAULT_MASTER_IDLE_TEMP,
    DOMAIN,
)
from .energy_arbitrage import EnergyArbitrage
from .heat_demand import MasterThermostatController
from .scheduler import HeatingScheduler
from .window_manager import WindowManager

_LOGGER = logging.getLogger(__name__)


class HAHeatingCoordinator(DataUpdateCoordinator[dict]):
    """Central hub coordinator managing energy arbitrage, schedules, masters and windows."""

    def __init__(
        self,
        hass: HomeAssistant,
        hub_config: dict,
        entry: ConfigEntry | None = None,
    ) -> None:
        """Initialize central coordinator."""
        try:
            super().__init__(
                hass,
                _LOGGER,
                name=DOMAIN,
                update_interval=timedelta(seconds=60),
                config_entry=entry,
            )
        except TypeError:
            super().__init__(
                hass,
                _LOGGER,
                name=DOMAIN,
                update_interval=timedelta(seconds=60),
            )
            if entry is not None:
                self.config_entry = entry

        self.hub_config = hub_config

        # Core logic engines
        self.arbitrage = EnergyArbitrage()
        self.scheduler = HeatingScheduler(
            cycle_type=hub_config.get(CONF_CYCLE_TYPE, CYCLE_ISO_EVEN_ODD),
            cycle_anchor_date_str=hub_config.get(CONF_CYCLE_ANCHOR_DATE),
            calendar_filter=hub_config.get(CONF_CALENDAR_FILTER),
        )
        self.window_manager = WindowManager()

        # Master controllers indexed by master entity_id
        self.master_controllers: dict[str, MasterThermostatController] = {}

        # Tracking listeners
        self._unsub_listeners: list[CALLBACK_TYPE] = []

    def get_or_create_master_controller(
        self,
        master_entity_id: str,
        control_mode: str,
        boost_offset: float = DEFAULT_MASTER_BOOST_OFFSET,
        idle_temp: float = DEFAULT_MASTER_IDLE_TEMP,
        boost_temp: float | None = None,
    ) -> MasterThermostatController:
        """Get or initialize a MasterThermostatController for a given entity."""
        if master_entity_id not in self.master_controllers:
            ctrl = MasterThermostatController(
                hass=self.hass,
                master_entity_id=master_entity_id,
                control_mode=control_mode,
                boost_offset=boost_offset,
                idle_temp=idle_temp,
                boost_temp=boost_temp,
            )
            ctrl.start_tracking()
            self.master_controllers[master_entity_id] = ctrl
        return self.master_controllers[master_entity_id]

    async def async_setup(self) -> None:
        """Start tracking state changes and timer intervals."""
        # Only track discrete state changes (calendar vacation & schedule helpers).
        # Continuous numeric sensors (solar export, outdoor temperature, energy tariffs)
        # are sampled strictly on the 60-second periodic coordinator interval to prevent
        # log spam and rapid state-machine thrashing.
        watched_entities = set()

        for key in (
            CONF_VACATION_CALENDAR,
            CONF_CYCLE_ENTITY,
        ):
            ent = self.hub_config.get(key)
            if ent:
                watched_entities.add(ent)

        if watched_entities:
            @callback
            def _handle_state_change(event: Event) -> None:
                self.async_set_updated_data(self._evaluate_data())

            unsub = async_track_state_change_event(
                self.hass, list(watched_entities), _handle_state_change
            )
            self._unsub_listeners.append(unsub)

        # Initial data update
        self.async_set_updated_data(self._evaluate_data())

    async def _async_update_data(self) -> dict:
        """Periodic update handler."""
        return self._evaluate_data()

    def _evaluate_data(self) -> dict:
        """Calculate and return live system status."""
        now = datetime.now()

        # Read sensor states
        gas_price = self._get_float_state(self.hub_config.get(CONF_GAS_PRICE_SENSOR))
        elec_price = self._get_float_state(
            self.hub_config.get(CONF_ELECTRIC_PRICE_SENSOR)
        )
        outdoor_temp = self._get_float_state(
            self.hub_config.get(CONF_OUTDOOR_TEMP_SENSOR)
        )
        solar_export = self._get_float_state(
            self.hub_config.get(CONF_SOLAR_EXPORT_SENSOR)
        )

        cycle_ent = self.hub_config.get(CONF_CYCLE_ENTITY)
        cycle_state = self.hass.states.get(cycle_ent).state if cycle_ent and self.hass.states.get(cycle_ent) else None
        active_week = self.scheduler.determine_week_cycle(now, cycle_state)

        cal_ent = self.hub_config.get(CONF_VACATION_CALENDAR)
        cal_state = None
        cal_attrs = None
        if cal_ent and self.hass.states.get(cal_ent):
            st = self.hass.states.get(cal_ent)
            cal_state = st.state
            cal_attrs = st.attributes

        is_vacation = self.scheduler.is_vacation_active(cal_state, cal_attrs)

        cop = self.arbitrage.estimate_cop(outdoor_temp)
        thermal_gas = self.arbitrage.calculate_thermal_cost_gas(gas_price)
        thermal_elec = self.arbitrage.calculate_thermal_cost_electric(
            elec_price, outdoor_temp, solar_export
        )

        use_ac, reason = self.arbitrage.should_use_ac_for_heating(
            gas_price, elec_price, outdoor_temp, solar_export
        )

        return {
            "timestamp": now.isoformat(),
            "active_week": active_week,
            "is_vacation": is_vacation,
            "outdoor_temp": outdoor_temp,
            "gas_price": gas_price,
            "electric_price": elec_price,
            "solar_export": solar_export,
            "airco_cop": cop,
            "thermal_cost_gas": thermal_gas,
            "thermal_cost_electric": thermal_elec,
            "should_use_ac": use_ac,
            "arbitrage_reason": reason,
        }

    def _get_float_state(self, entity_id: str | None) -> float | None:
        """Safely extract float value from state entity."""
        if not entity_id:
            return None
        st = self.hass.states.get(entity_id)
        if not st or st.state in ("unknown", "unavailable", None):
            return None
        try:
            return float(st.state)
        except (ValueError, TypeError):
            return None

    def cleanup(self) -> None:
        """Clean up listeners and timers."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        self.window_manager.cleanup()
        for ctrl in self.master_controllers.values():
            ctrl.stop_tracking()
        self.master_controllers.clear()

