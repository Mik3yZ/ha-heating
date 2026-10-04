"""Climate platform for ha_heating room thermostats."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_AC_ENABLE_COOLING,
    CONF_AC_ENTITY,
    CONF_AC_QUIET_END,
    CONF_AC_QUIET_START,
    CONF_ENTRY_TYPE,
    CONF_MASTER_BOOST_TEMP,
    CONF_MASTER_CONTROL_MODE,
    CONF_MASTER_IDLE_TEMP,
    CONF_MASTER_THERMOSTAT,
    CONF_ROOM_NAME,
    CONF_ROOM_TEMP_SENSOR,
    CONF_SCHEDULE_WEEK_A,
    CONF_SCHEDULE_WEEK_B,
    CONF_TEMP_AWAY,
    CONF_TEMP_BOOST,
    CONF_TEMP_COMFORT,
    CONF_TEMP_ECO,
    CONF_TEMP_HOLIDAY,
    CONF_TEMP_SLEEP,
    CONF_TRVS,
    CONF_WINDOW_CLOSE_DELAY,
    CONF_WINDOW_OPEN_DELAY,
    CONF_WINDOW_SENSORS,
    DEFAULT_AC_COOL_DEADBAND,
    DEFAULT_FROST_TEMP,
    DEFAULT_HYSTERESIS_ON,
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
    ENTRY_TYPE_ROOM,
    HEAT_SOURCE_AC_COOL,
    HEAT_SOURCE_AC_HEAT,
    HEAT_SOURCE_GAS,
    HEAT_SOURCE_IDLE,
    HEAT_SOURCE_PAUSED_WINDOW,
    MASTER_MODE_SETPOINT_BOOST,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOLIDAY,
    PRESET_SLEEP,
)
from .coordinator import HAHeatingCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up room climate entities from a config entry."""
    entry_data = entry.data
    if entry_data.get(CONF_ENTRY_TYPE) != ENTRY_TYPE_ROOM:
        return

    coordinator: HAHeatingCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([HAHeatingRoomClimate(hass, entry, coordinator)])


class HAHeatingRoomClimate(CoordinatorEntity[HAHeatingCoordinator], ClimateEntity):
    """Virtual climate entity representing a room zone."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: HAHeatingCoordinator,
    ) -> None:
        """Initialize the room climate entity."""
        super().__init__(coordinator)
        self.hass = hass
        self.entry = entry
        self._config = entry.data
        self._options = entry.options

        self._room_id = entry.entry_id
        self._attr_name = self._config.get(CONF_ROOM_NAME, "Room")
        self._attr_unique_id = f"ha_heating_room_{self._room_id}"

        # TRVs and actuators
        self._trvs: list[str] = self._config.get(CONF_TRVS, [])
        self._ac_entity: str | None = self._config.get(CONF_AC_ENTITY)
        self._room_temp_sensor: str | None = self._config.get(CONF_ROOM_TEMP_SENSOR)
        self._window_sensors: list[str] = self._config.get(CONF_WINDOW_SENSORS, [])

        # Master Thermostat coupling
        self._master_entity: str | None = self._config.get(CONF_MASTER_THERMOSTAT)
        self._master_controller = None
        if self._master_entity:
            self._master_controller = coordinator.get_or_create_master_controller(
                master_entity_id=self._master_entity,
                control_mode=self._config.get(
                    CONF_MASTER_CONTROL_MODE, MASTER_MODE_SETPOINT_BOOST
                ),
                boost_temp=self._config.get(
                    CONF_MASTER_BOOST_TEMP, DEFAULT_MASTER_BOOST_TEMP
                ),
                idle_temp=self._config.get(
                    CONF_MASTER_IDLE_TEMP, DEFAULT_MASTER_IDLE_TEMP
                ),
            )
            self._master_controller.register_room(self._room_id)

        # Schedules and presets
        self._schedule_week_a: str | None = self._config.get(CONF_SCHEDULE_WEEK_A)
        self._schedule_week_b: str | None = self._config.get(CONF_SCHEDULE_WEEK_B)

        self._preset_temps = {
            PRESET_COMFORT: float(self._config.get(CONF_TEMP_COMFORT, DEFAULT_TEMP_COMFORT)),
            PRESET_ECO: float(self._config.get(CONF_TEMP_ECO, DEFAULT_TEMP_ECO)),
            PRESET_SLEEP: float(self._config.get(CONF_TEMP_SLEEP, DEFAULT_TEMP_SLEEP)),
            PRESET_AWAY: float(self._config.get(CONF_TEMP_AWAY, DEFAULT_TEMP_AWAY)),
            PRESET_BOOST: float(self._config.get(CONF_TEMP_BOOST, DEFAULT_TEMP_BOOST)),
            PRESET_HOLIDAY: float(self._config.get(CONF_TEMP_HOLIDAY, DEFAULT_TEMP_HOLIDAY)),
        }

        # Features & modes
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        self._attr_supported_features = features
        self._attr_preset_modes = [
            PRESET_COMFORT,
            PRESET_ECO,
            PRESET_SLEEP,
            PRESET_AWAY,
            PRESET_BOOST,
            PRESET_HOLIDAY,
        ]

        hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
        if self._ac_entity and self._config.get(CONF_AC_ENABLE_COOLING, True):
            hvac_modes.append(HVACMode.COOL)
        self._attr_hvac_modes = hvac_modes

        # Internal states
        self._attr_hvac_mode = HVACMode.HEAT
        self._attr_hvac_action = HVACAction.IDLE
        self._attr_preset_mode = PRESET_COMFORT

        self._attr_target_temperature = self._preset_temps[PRESET_COMFORT]
        self._attr_current_temperature = None

        self._manual_override_temp: float | None = None
        self._manual_override_until: datetime | None = None

        self._active_heat_source = HEAT_SOURCE_IDLE
        self._reason = "Initialized"
        self._demand_active = False

    async def async_added_to_hass(self) -> None:
        """Register listeners for external entities."""
        await super().async_added_to_hass()

        watched = set(self._trvs)
        if self._room_temp_sensor:
            watched.add(self._room_temp_sensor)
        if self._window_sensors:
            watched.update(self._window_sensors)
        if self._schedule_week_a:
            watched.add(self._schedule_week_a)
        if self._schedule_week_b:
            watched.add(self._schedule_week_b)

        if watched:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, list(watched), self._handle_entity_state_change
                )
            )

        # Initial evaluation
        await self._async_evaluate()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.hass.async_create_task(self._async_evaluate())

    @callback
    def _handle_entity_state_change(self, event: Event) -> None:
        """Handle changes in monitored TRVs, sensors or schedules."""
        entity_id = event.data.get("entity_id")
        if entity_id in self._window_sensors:
            self._handle_window_sensor_update()
        self.hass.async_create_task(self._async_evaluate())

    def _handle_window_sensor_update(self) -> None:
        """Evaluate open status of window sensors and invoke WindowManager."""
        any_open = False
        for w_ent in self._window_sensors:
            st = self.hass.states.get(w_ent)
            if st and st.state == "on":
                any_open = True
                break

        def _on_window_state_changed(room_id: str, is_paused: bool) -> None:
            self.hass.async_create_task(self._async_evaluate())

        self.coordinator.window_manager.handle_sensor_update(
            room_id=self._room_id,
            any_window_open=any_open,
            loop=self.hass.loop,
            on_state_change=_on_window_state_changed,
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature (manual override)."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        self._manual_override_temp = float(temp)
        # Override valid for 2 hours by default
        self._manual_override_until = datetime.now() + timedelta(hours=2)
        _LOGGER.info("Room '%s': Manual override set to %.1f°C", self._attr_name, temp)
        await self._async_evaluate()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        self._attr_hvac_mode = hvac_mode
        await self._async_evaluate()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set Preset mode."""
        if preset_mode in self._attr_preset_modes:
            self._attr_preset_mode = preset_mode
            self._manual_override_temp = None  # Clear manual override
            await self._async_evaluate()

    async def _async_evaluate(self) -> None:
        """Main control loop: calculate temperatures, arbitrage, actuators, and master demand."""
        now = datetime.now()

        # 1. Update current temperature
        self._attr_current_temperature = self._calc_current_temperature()

        # 2. Check window pause
        is_window_paused = self.coordinator.window_manager.get_is_room_paused(
            self._room_id
        )

        # 3. Resolve target temperature
        coord_data = self.coordinator.data or {}
        active_week = coord_data.get("active_week", "week_a")
        is_vacation = coord_data.get("is_vacation", False)

        sched_a_st = (
            self.hass.states.get(self._schedule_week_a).state
            if self._schedule_week_a and self.hass.states.get(self._schedule_week_a)
            else None
        )
        sched_b_st = (
            self.hass.states.get(self._schedule_week_b).state
            if self._schedule_week_b and self.hass.states.get(self._schedule_week_b)
            else None
        )

        target_temp, reason = self.coordinator.scheduler.resolve_target_temperature(
            current_dt=now,
            preset_mode=self._attr_preset_mode,
            is_vacation=is_vacation,
            active_week=active_week,
            schedule_a_state=sched_a_st,
            schedule_b_state=sched_b_st,
            preset_temps=self._preset_temps,
            manual_override_temp=self._manual_override_temp,
            manual_override_until=self._manual_override_until,
        )
        self._attr_target_temperature = target_temp
        self._reason = reason

        # 4. Determine heat demand
        needs_heat = False
        needs_cool = False

        if self._attr_hvac_mode != HVACMode.OFF and not is_window_paused:
            if self._attr_current_temperature is not None:
                if (
                    self._attr_target_temperature - self._attr_current_temperature
                    >= DEFAULT_HYSTERESIS_ON
                ):
                    needs_heat = True
                elif (
                    self._ac_entity
                    and self._attr_hvac_mode == HVACMode.COOL
                    and (self._attr_current_temperature - self._attr_target_temperature)
                    >= DEFAULT_AC_COOL_DEADBAND
                ):
                    needs_cool = True

        # 5. Check quiet hours for AC
        is_quiet = self.coordinator.arbitrage.is_in_quiet_hours(
            now,
            self._config.get(CONF_AC_QUIET_START),
            self._config.get(CONF_AC_QUIET_END),
        )
        # Slaap preset blocks AC heating as well
        if self._attr_preset_mode == PRESET_SLEEP:
            is_quiet = True

        # 6. Arbitrage decision: AC vs Gas
        use_ac_decision = False
        if needs_heat and self._ac_entity and not is_quiet:
            use_ac_decision = coord_data.get("should_use_ac", False)

        # 7. Actuate hardware & update demand
        if is_window_paused:
            self._active_heat_source = HEAT_SOURCE_PAUSED_WINDOW
            self._attr_hvac_action = HVACAction.OFF
            self._demand_active = False
            await self._set_trvs(DEFAULT_FROST_TEMP)
            await self._set_ac(HVACMode.OFF)
        elif self._attr_hvac_mode == HVACMode.OFF:
            self._active_heat_source = HEAT_SOURCE_IDLE
            self._attr_hvac_action = HVACAction.OFF
            self._demand_active = False
            await self._set_trvs(DEFAULT_FROST_TEMP)
            await self._set_ac(HVACMode.OFF)
        elif needs_cool:
            self._active_heat_source = HEAT_SOURCE_AC_COOL
            self._attr_hvac_action = HVACAction.COOLING
            self._demand_active = False
            await self._set_trvs(DEFAULT_FROST_TEMP)
            await self._set_ac(HVACMode.COOL, self._attr_target_temperature)
        elif needs_heat:
            if use_ac_decision:
                # Heat via AC
                self._active_heat_source = HEAT_SOURCE_AC_HEAT
                self._attr_hvac_action = HVACAction.HEATING
                self._demand_active = False
                await self._set_trvs(DEFAULT_FROST_TEMP)
                await self._set_ac(HVACMode.HEAT, self._attr_target_temperature)
            else:
                # Heat via Gas / Radiators
                self._active_heat_source = HEAT_SOURCE_GAS
                self._attr_hvac_action = HVACAction.HEATING
                self._demand_active = True
                await self._set_trvs(self._attr_target_temperature)
                await self._set_ac(HVACMode.OFF)
        else:
            # Idle / Temperature reached
            self._active_heat_source = HEAT_SOURCE_IDLE
            self._attr_hvac_action = HVACAction.IDLE
            self._demand_active = False
            await self._set_trvs(self._attr_target_temperature)
            await self._set_ac(HVACMode.OFF)

        # 8. Notify Master Thermostat controller
        if self._master_controller:
            await self._master_controller.update_room_demand(
                self._room_id, self._demand_active, now
            )

        self.async_write_ha_state()

    def _calc_current_temperature(self) -> float | None:
        """Calculate current temperature from sensor or TRV average."""
        if self._room_temp_sensor:
            st = self.hass.states.get(self._room_temp_sensor)
            if st and st.state not in ("unknown", "unavailable", None):
                try:
                    return float(st.state)
                except ValueError:
                    pass

        # TRV average
        temps = []
        for trv in self._trvs:
            st = self.hass.states.get(trv)
            if st and st.attributes.get("current_temperature") is not None:
                try:
                    temps.append(float(st.attributes["current_temperature"]))
                except (ValueError, TypeError):
                    pass
        if temps:
            return round(sum(temps) / len(temps), 1)
        return None

    async def _set_trvs(self, temp: float) -> None:
        """Command all TRVs in this room to the desired temperature."""
        for trv in self._trvs:
            try:
                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {"entity_id": trv, "temperature": temp},
                    blocking=False,
                )
            except Exception as err:
                _LOGGER.error("Failed to set temperature for TRV '%s': %s", trv, err)

    async def _set_ac(self, mode: HVACMode, temp: float | None = None) -> None:
        """Command the room AC unit."""
        if not self._ac_entity:
            return
        try:
            if mode == HVACMode.OFF:
                await self.hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {"entity_id": self._ac_entity, "hvac_mode": HVACMode.OFF},
                    blocking=False,
                )
            else:
                data: dict[str, Any] = {
                    "entity_id": self._ac_entity,
                    "hvac_mode": mode,
                }
                if temp is not None:
                    data["temperature"] = temp
                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    data,
                    blocking=False,
                )
        except Exception as err:
            _LOGGER.error("Failed to set AC unit '%s': %s", self._ac_entity, err)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Attributes for dashboard cards and monitoring."""
        coord_data = self.coordinator.data or {}
        now = datetime.now()
        is_quiet = self.coordinator.arbitrage.is_in_quiet_hours(
            now,
            self._config.get(CONF_AC_QUIET_START),
            self._config.get(CONF_AC_QUIET_END),
        )

        return {
            "active_heat_source": self._active_heat_source,
            "window_open": any(
                self.hass.states.get(w).state == "on"
                for w in self._window_sensors
                if self.hass.states.get(w)
            ),
            "window_paused": self.coordinator.window_manager.get_is_room_paused(
                self._room_id
            ),
            "heat_demand_active": self._demand_active,
            "linked_master": self._master_entity,
            "master_heating_active": (
                self._master_controller.is_heating_active
                if self._master_controller
                else False
            ),
            "trv_entities": self._trvs,
            "ac_entity": self._ac_entity,
            "ac_quiet_hours_active": is_quiet,
            "active_week": coord_data.get("active_week"),
            "vacation_override_active": coord_data.get("is_vacation", False),
            "resolution_reason": self._reason,
            "thermal_cost_gas": coord_data.get("thermal_cost_gas"),
            "thermal_cost_electric": coord_data.get("thermal_cost_electric"),
            "airco_cop": coord_data.get("airco_cop"),
        }

    async def async_will_remove_from_hass(self) -> None:
        """Handle removal."""
        if self._master_controller:
            self._master_controller.unregister_room(self._room_id)
        self.coordinator.window_manager.cleanup(self._room_id)
        await super().async_will_remove_from_hass()

