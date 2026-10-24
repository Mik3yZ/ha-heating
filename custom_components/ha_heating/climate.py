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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity
try:
    from homeassistant.helpers.restore_state import RestoreEntity
except ImportError:
    class RestoreEntity:
        """Fallback RestoreEntity."""
        async def async_get_last_state(self):
            return None

from .const import (
    CONF_AC_ENABLE_COOLING,
    CONF_AC_ENTITY,
    CONF_AC_QUIET_END,
    CONF_AC_QUIET_START,
    CONF_AC_TEMP_OFFSET,
    CONF_AREA_ID,
    CONF_BOOST_DURATION_MINUTES,
    CONF_ENTRY_TYPE,
    CONF_MASTER_BOOST_OFFSET,
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
    CONF_VALVE_EXERCISE_ENABLED,
    CONF_WINDOW_CLOSE_DELAY,
    CONF_WINDOW_OPEN_DELAY,
    CONF_WINDOW_SENSORS,
    DEFAULT_AC_COOL_DEADBAND,
    DEFAULT_AC_TEMP_OFFSET,
    DEFAULT_BOOST_DURATION_MINUTES,
    DEFAULT_FROST_TEMP,
    DEFAULT_HYSTERESIS_OFF,
    DEFAULT_HYSTERESIS_ON,
    DEFAULT_MASTER_BOOST_OFFSET,
    DEFAULT_MASTER_BOOST_TEMP,
    DEFAULT_MASTER_IDLE_TEMP,
    DEFAULT_MAX_CONTINUOUS_HEAT_HOURS,
    DEFAULT_TEMP_AWAY,
    DEFAULT_TEMP_BOOST,
    DEFAULT_TEMP_COMFORT,
    DEFAULT_TEMP_ECO,
    DEFAULT_TEMP_HOLIDAY,
    DEFAULT_TEMP_SLEEP,
    DEFAULT_VALVE_EXERCISE_ENABLED,
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
    RAPID_TEMP_DROP_THRESHOLD,
    VALVE_EXERCISE_DURATION_MINUTES,
    VALVE_EXERCISE_INTERVAL_DAYS,
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


class HAHeatingRoomClimate(CoordinatorEntity[HAHeatingCoordinator], RestoreEntity, ClimateEntity):
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
        merged_cfg = dict(entry.data)
        if getattr(entry, "options", None):
            merged_cfg.update(dict(entry.options))
        self._config = merged_cfg
        self._options = entry.options

        self._room_id = entry.entry_id
        self._room_name = self._config.get(CONF_ROOM_NAME, "Room")
        self._attr_name = None
        self._attr_unique_id = f"ha_heating_room_{self._room_id}"
        area_id = self._config.get(CONF_AREA_ID)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._room_id)},
            name=self._room_name,
            manufacturer="HA Heating",
            model="Room Thermostat",
            suggested_area=area_id,
        )

        # TRVs and actuators
        self._trvs: list[str] = self._config.get(CONF_TRVS, [])
        self._ac_entity: str | None = self._config.get(CONF_AC_ENTITY)
        self._room_temp_sensor: str | None = self._config.get(CONF_ROOM_TEMP_SENSOR)
        self._window_sensors: list[str] = self._config.get(CONF_WINDOW_SENSORS, [])
        self._window_open_delay: int = int(
            self._config.get(CONF_WINDOW_OPEN_DELAY, DEFAULT_WINDOW_OPEN_DELAY)
        )
        self._window_close_delay: int = int(
            self._config.get(CONF_WINDOW_CLOSE_DELAY, DEFAULT_WINDOW_CLOSE_DELAY)
        )

        # Master Thermostat coupling
        self._master_entity: str | None = self._config.get(CONF_MASTER_THERMOSTAT)
        self._master_controller = None
        if self._master_entity:
            raw_boost = float(
                self._config.get(
                    CONF_MASTER_BOOST_OFFSET,
                    self._config.get(CONF_MASTER_BOOST_TEMP, DEFAULT_MASTER_BOOST_OFFSET),
                )
            )
            boost_offset = (
                DEFAULT_MASTER_BOOST_OFFSET if raw_boost > 15.0 else raw_boost
            )

            self._master_controller = coordinator.get_or_create_master_controller(
                master_entity_id=self._master_entity,
                control_mode=self._config.get(
                    CONF_MASTER_CONTROL_MODE, MASTER_MODE_SETPOINT_BOOST
                ),
                boost_offset=boost_offset,
                idle_temp=float(
                    self._config.get(
                        CONF_MASTER_IDLE_TEMP, DEFAULT_MASTER_IDLE_TEMP
                    )
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
        self._demand_reason = "Initialized"
        self._ac_block_reason = "Initialized"
        self._action_summary = "Initialized"
        self._demand_active = False

        # State tracking for command deduplication and schedule transitions
        self._last_commanded_trv_temps: dict[str, float] = {}
        self._last_commanded_ac_state: tuple[str, float | None] | None = None
        self._last_active_week: str | None = None

        # Smart features state: Timed Boost, AC stratification offset, Valve Exercise, Anomaly detection
        self._boost_duration_minutes: int = int(
            self._config.get(CONF_BOOST_DURATION_MINUTES, DEFAULT_BOOST_DURATION_MINUTES)
        )
        self._boost_until: datetime | None = None
        self._pre_boost_preset: str | None = None
        self._ac_temp_offset: float = float(
            self._config.get(CONF_AC_TEMP_OFFSET, DEFAULT_AC_TEMP_OFFSET)
        )
        self._valve_exercise_enabled: bool = bool(
            self._config.get(CONF_VALVE_EXERCISE_ENABLED, DEFAULT_VALVE_EXERCISE_ENABLED)
        )
        self._last_trv_open_time: datetime = datetime.now()
        self._valve_exercise_until: datetime | None = None
        self._recent_temp_samples: list[tuple[datetime, float]] = []
        self._rapid_drop_pause_until: datetime | None = None
        self._heating_started_at: datetime | None = None
        self._heating_start_temp: float | None = None

    async def async_added_to_hass(self) -> None:
        """Register listeners for external entities and restore previous state."""
        await super().async_added_to_hass()

        # Restore previous state after reboot
        last_state = await self.async_get_last_state()
        if last_state:
            last_preset = last_state.attributes.get("preset_mode")
            if last_preset in self._attr_preset_modes:
                self._attr_preset_mode = last_preset
                _LOGGER.info(
                    "Room '%s': Restored preset_mode to '%s'",
                    self._room_name,
                    last_preset,
                )

            if last_state.state in self._attr_hvac_modes:
                self._attr_hvac_mode = HVACMode(last_state.state)
                _LOGGER.info(
                    "Room '%s': Restored hvac_mode to '%s'",
                    self._room_name,
                    self._attr_hvac_mode,
                )

            override_temp = last_state.attributes.get("manual_override_temp")
            override_until = last_state.attributes.get("manual_override_until")
            if override_temp is not None and override_until:
                try:
                    dt_until = datetime.fromisoformat(override_until)
                    if datetime.now() < dt_until:
                        self._manual_override_temp = float(override_temp)
                        self._manual_override_until = dt_until
                        _LOGGER.info(
                            "Room '%s': Restored active manual override %.1f°C until %s",
                            self._room_name,
                            self._manual_override_temp,
                            dt_until,
                        )
                except Exception:
                    pass

            boost_until_str = last_state.attributes.get("boost_until")
            pre_boost = last_state.attributes.get("pre_boost_preset")
            if boost_until_str:
                try:
                    dt_boost = datetime.fromisoformat(boost_until_str)
                    if datetime.now() < dt_boost and self._attr_preset_mode == PRESET_BOOST:
                        self._boost_until = dt_boost
                        self._pre_boost_preset = pre_boost
                    elif self._attr_preset_mode == PRESET_BOOST and pre_boost in self._attr_preset_modes:
                        self._attr_preset_mode = pre_boost
                except Exception:
                    pass

            last_trv_str = last_state.attributes.get("last_trv_open_time")
            if last_trv_str:
                try:
                    self._last_trv_open_time = datetime.fromisoformat(last_trv_str)
                except Exception:
                    pass

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

        # Initial checks
        if self._window_sensors:
            self._handle_window_sensor_update()
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
        elif entity_id in (self._schedule_week_a, self._schedule_week_b):
            coord_data = self.coordinator.data or {}
            active_week = coord_data.get("active_week", "week_a")
            active_sched = (
                self._schedule_week_a
                if active_week == "week_a"
                else self._schedule_week_b
            )
            if entity_id == active_sched and self._attr_preset_mode not in (
                PRESET_AWAY,
                PRESET_HOLIDAY,
            ):
                st = self.hass.states.get(entity_id)
                if st and st.state in ("on", "off"):
                    new_preset = PRESET_COMFORT if st.state == "on" else PRESET_ECO
                    if self._attr_preset_mode != new_preset:
                        self._attr_preset_mode = new_preset
                        self._manual_override_temp = None
                        self._manual_override_until = None
                        _LOGGER.info(
                            "Room '%s': Schedule '%s' changed to '%s' -> switching preset to '%s'",
                            self._room_name,
                            entity_id,
                            st.state,
                            new_preset,
                        )
        self.hass.async_create_task(self._async_evaluate())

    def _check_window_sensors_offline(self) -> None:
        """Check all window sensors for offline/unavailable status."""
        for w_ent in self._window_sensors:
            st = self.hass.states.get(w_ent)
            is_offline = (st is None) or (st.state in ("unavailable", "unknown"))
            curr_state = st.state if st else "unavailable"
            self.hass.async_create_task(
                self.coordinator.async_handle_window_sensor_offline(
                    room_id=self._room_id,
                    room_name=self._room_name,
                    sensor_entity_id=w_ent,
                    is_offline=is_offline,
                    current_state=curr_state,
                )
            )

    def _handle_window_sensor_update(self) -> None:
        """Evaluate open status of window sensors and invoke WindowManager."""
        self._check_window_sensors_offline()
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
            open_delay_sec=self._window_open_delay,
            close_delay_sec=self._window_close_delay,
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature (manual override)."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        self._manual_override_temp = float(temp)
        # Override valid for 2 hours by default
        self._manual_override_until = datetime.now() + timedelta(hours=2)
        _LOGGER.info("Room '%s': Manual override set to %.1f°C", self._room_name, temp)
        await self._async_evaluate()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        self._attr_hvac_mode = hvac_mode
        await self._async_evaluate()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set Preset mode (with automatic countdown timer when Boost is selected)."""
        if preset_mode in self._attr_preset_modes:
            if preset_mode == PRESET_BOOST:
                if self._attr_preset_mode != PRESET_BOOST:
                    self._pre_boost_preset = self._attr_preset_mode
                if self._boost_duration_minutes > 0:
                    self._boost_until = datetime.now() + timedelta(
                        minutes=self._boost_duration_minutes
                    )
            else:
                self._boost_until = None
                self._pre_boost_preset = None

            self._attr_preset_mode = preset_mode
            self._manual_override_temp = None  # Clear manual override
            self._manual_override_until = None
            await self._async_evaluate()

    async def _async_evaluate(self) -> None:
        """Main control loop: calculate temperatures, arbitrage, actuators, and master demand."""
        now = datetime.now()

        # 1. Update current temperature
        self._attr_current_temperature = self._calc_current_temperature()

        # Check Master Switch (Algemene Aan/Uit knop)
        if not self.coordinator.system_enabled:
            self._active_heat_source = HEAT_SOURCE_IDLE
            self._attr_hvac_action = HVACAction.OFF
            self._demand_active = False
            self._reason = "Systeem uitgeschakeld via hoofdschakelaar"
            self._demand_reason = "Systeem uitgeschakeld via hoofdschakelaar"
            self._ac_block_reason = "Hoofdschakelaar staat UIT"
            self._action_summary = "Hoofdschakelaar staat UIT. Alle verwarming/koeling gestopt."
            await self._set_trvs(DEFAULT_FROST_TEMP)
            await self._set_ac(HVACMode.OFF)
            if self._master_controller:
                await self._master_controller.update_room_demand(
                    self._room_id, False, now
                )
            self.async_write_ha_state()
            return

        # 2. Check window pause & rapid temperature drop protection
        is_window_paused = self.coordinator.window_manager.get_is_room_paused(
            self._room_id
        )

        if self._attr_current_temperature is not None:
            cutoff = now - timedelta(minutes=10)
            self._recent_temp_samples = [
                (ts, t) for ts, t in self._recent_temp_samples if ts >= cutoff
            ]
            self._recent_temp_samples.append((now, self._attr_current_temperature))
            if (
                not is_window_paused
                and self._attr_hvac_mode != HVACMode.COOL
                and (
                    self._rapid_drop_pause_until is None
                    or now >= self._rapid_drop_pause_until
                )
                and len(self._recent_temp_samples) >= 2
            ):
                max_temp = max(t for _, t in self._recent_temp_samples)
                drop = round(max_temp - self._attr_current_temperature, 2)
                if drop >= RAPID_TEMP_DROP_THRESHOLD:
                    self._rapid_drop_pause_until = now + timedelta(minutes=15)
                    self.hass.async_create_task(
                        self.coordinator.async_send_anomaly_warning(
                            self._room_id,
                            self._attr_name or "Kamer",
                            "rapid_drop",
                            f"⚠️ HA Heating: Snelle temperatuurdaling ({self._attr_name})",
                            f"Snelle temperatuurdaling gedetecteerd ({max_temp}°C -> {self._attr_current_temperature}°C binnen 10 min) "
                            f"in '{self._attr_name}'. Verwarming is 15 minuten gepauzeerd (mogelijk open raam of defecte raamsensor).",
                        )
                    )

        is_rapid_drop_paused = (
            self._rapid_drop_pause_until is not None
            and now < self._rapid_drop_pause_until
        )
        effective_paused = is_window_paused or is_rapid_drop_paused

        # 3. Resolve target temperature & handle expired overrides / boost timer / week cycle transitions
        if self._manual_override_until is not None and now >= self._manual_override_until:
            self._manual_override_temp = None
            self._manual_override_until = None

        if (
            self._attr_preset_mode == PRESET_BOOST
            and self._boost_until is not None
            and now >= self._boost_until
        ):
            reverted_preset = (
                self._pre_boost_preset
                if self._pre_boost_preset in self._attr_preset_modes
                else PRESET_ECO
            )
            self._attr_preset_mode = reverted_preset
            self._boost_until = None
            self._pre_boost_preset = None

        coord_data = self.coordinator.data or {}
        active_week = coord_data.get("active_week", "week_a")
        is_vacation = coord_data.get("is_vacation", False)
        is_auto_away = coord_data.get("is_auto_away", False)

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

        if self._last_active_week is not None and active_week != self._last_active_week:
            active_sched_st = sched_a_st if active_week == "week_a" else sched_b_st
            if active_sched_st in ("on", "off") and self._attr_preset_mode in (
                PRESET_COMFORT,
                PRESET_ECO,
            ):
                self._attr_preset_mode = (
                    PRESET_COMFORT if active_sched_st == "on" else PRESET_ECO
                )
        self._last_active_week = active_week

        # Check quiet hours early so solar buffer knows if AC is allowed
        quiet_start = self._config.get(CONF_AC_QUIET_START, "22:00")
        quiet_end = self._config.get(CONF_AC_QUIET_END, "07:00")
        is_quiet = self.coordinator.arbitrage.is_in_quiet_hours(
            now, quiet_start, quiet_end
        )
        is_sleep = self._attr_preset_mode == PRESET_SLEEP
        if is_sleep:
            is_quiet = True

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
            is_auto_away=is_auto_away,
        )
        if self._attr_preset_mode == PRESET_BOOST and self._boost_until is not None:
            reason = f"{reason} (tot {self._boost_until.strftime('%H:%M')})"

        # Apply Solar Surplus / Negative Price Thermal Buffer if AC is eligible
        solar_buffer_applied = False
        if (
            coord_data.get("solar_buffer_active", False)
            and self._ac_entity
            and not is_quiet
            and not is_vacation
            and not is_auto_away
            and self._manual_override_temp is None
            and self._attr_preset_mode in (PRESET_COMFORT, PRESET_ECO)
        ):
            buf_offset = float(coord_data.get("solar_buffer_offset", 0.0))
            if buf_offset > 0:
                solar_buffer_applied = True
                if self._attr_hvac_mode == HVACMode.COOL:
                    target_temp = round(target_temp - buf_offset, 1)
                    reason = f"{reason} (-{buf_offset:.1f}°C Zonne-buffer)"
                else:
                    target_temp = round(target_temp + buf_offset, 1)
                    reason = f"{reason} (+{buf_offset:.1f}°C Zonne-buffer)"

        self._attr_target_temperature = target_temp
        self._reason = reason

        # 4. Determine heat demand (with Schmitt-trigger hysteresis)
        needs_heat = False
        needs_cool = False
        was_heating = self._attr_hvac_action == HVACAction.HEATING
        was_cooling = self._attr_hvac_action == HVACAction.COOLING

        if self._attr_hvac_mode != HVACMode.OFF and not effective_paused:
            if self._attr_current_temperature is not None:
                temp_deficit = round(
                    self._attr_target_temperature - self._attr_current_temperature, 2
                )
                temp_surplus = round(
                    self._attr_current_temperature - self._attr_target_temperature, 2
                )

                if temp_deficit >= DEFAULT_HYSTERESIS_ON:
                    needs_heat = True
                elif was_heating and temp_deficit > DEFAULT_HYSTERESIS_OFF:
                    needs_heat = True
                elif (
                    self._ac_entity
                    and self._attr_hvac_mode == HVACMode.COOL
                    and (
                        temp_surplus >= DEFAULT_AC_COOL_DEADBAND
                        or (was_cooling and temp_surplus > DEFAULT_HYSTERESIS_OFF)
                    )
                ):
                    needs_cool = True

        # Formulate demand reason
        if self._attr_hvac_mode == HVACMode.OFF:
            self._demand_reason = "Klimaat staat op UIT (geen verwarming)"
        elif is_window_paused:
            self._demand_reason = "Gepauzeerd: raam staat open"
        elif is_rapid_drop_paused:
            until_str = (
                self._rapid_drop_pause_until.strftime("%H:%M")
                if self._rapid_drop_pause_until
                else ""
            )
            self._demand_reason = f"Gepauzeerd: snelle temperatuurdaling gedetecteerd (tot {until_str})"
        elif self._attr_current_temperature is None:
            self._demand_reason = "Geen actuele temperatuurmeting beschikbaar"
        elif needs_heat:
            diff = round(self._attr_target_temperature - self._attr_current_temperature, 1)
            if diff >= DEFAULT_HYSTERESIS_ON:
                self._demand_reason = (
                    f"Warmtevraag actief: actueel {self._attr_current_temperature}°C < doel {self._attr_target_temperature}°C "
                    f"(verschil {diff}°C >= drempel {DEFAULT_HYSTERESIS_ON}°C)"
                )
            else:
                self._demand_reason = (
                    f"Warmtevraag actief (hysterese): verwarmen loopt door tot {self._attr_target_temperature}°C "
                    f"(actueel {self._attr_current_temperature}°C, nog {diff}°C te gaan)"
                )
        elif needs_cool:
            diff = round(self._attr_current_temperature - self._attr_target_temperature, 1)
            self._demand_reason = (
                f"Koelvraag actief: actueel {self._attr_current_temperature}°C > doel {self._attr_target_temperature}°C "
                f"(verschil {diff}°C >= deadband {DEFAULT_AC_COOL_DEADBAND}°C)"
            )
        else:
            diff = round(abs(self._attr_target_temperature - self._attr_current_temperature), 1)
            self._demand_reason = (
                f"Temperatuur bereikt: actueel {self._attr_current_temperature}°C "
                f"(doel {self._attr_target_temperature}°C, binnen hysterese)"
            )

        # 5. Check AC availability & arbitrage
        global_should_use_ac = coord_data.get("should_use_ac", False) or solar_buffer_applied
        global_arbitrage_reason = coord_data.get("arbitrage_reason", "")

        # 6. Arbitrage decision: AC vs Gas explanation
        if not self._ac_entity:
            self._ac_block_reason = "Geen airco gekoppeld aan deze kamer (verwarmen verloopt altijd via CV/gas)"
            ac_eligible = False
        elif is_sleep:
            self._ac_block_reason = "Airco geblokkeerd: Slaap-modus actief (geen tocht of ventilatorgeluid in de slaapkamer)"
            ac_eligible = False
        elif is_quiet:
            self._ac_block_reason = f"Airco geblokkeerd: Stille uren actief ({quiet_start} - {quiet_end})"
            ac_eligible = False
        elif not global_should_use_ac:
            self._ac_block_reason = f"Airco financieel/technisch niet geselecteerd: {global_arbitrage_reason}"
            ac_eligible = False
        else:
            self._ac_block_reason = f"Airco voordelig en actief: {global_arbitrage_reason}"
            ac_eligible = True

        use_ac_decision = needs_heat and ac_eligible

        # 7. Actuate hardware & update demand
        if effective_paused:
            self._active_heat_source = HEAT_SOURCE_PAUSED_WINDOW
            self._attr_hvac_action = HVACAction.OFF
            self._demand_active = False
            if is_window_paused:
                self._action_summary = "Raam open gedetecteerd: TRV's gesloten (7.0°C vorstbeveiliging), airco uitgeschakeld"
            else:
                self._action_summary = "Snelle temperatuurdaling gedetecteerd: TRV's gesloten (7.0°C), airco tijdelijk gepauzeerd"
            await self._set_trvs(DEFAULT_FROST_TEMP)
            await self._set_ac(HVACMode.OFF)
        elif self._attr_hvac_mode == HVACMode.OFF:
            self._active_heat_source = HEAT_SOURCE_IDLE
            self._attr_hvac_action = HVACAction.OFF
            self._demand_active = False
            self._action_summary = "Thermostaat staat op UIT: TRV's op vorstbeveiliging (7.0°C), airco uit"
            await self._set_trvs(DEFAULT_FROST_TEMP)
            await self._set_ac(HVACMode.OFF)
        elif needs_cool:
            self._active_heat_source = HEAT_SOURCE_AC_COOL
            self._attr_hvac_action = HVACAction.COOLING
            self._demand_active = False
            self._action_summary = f"Koelen via Airco ({self._ac_entity}) naar {self._attr_target_temperature}°C"
            await self._set_trvs(DEFAULT_FROST_TEMP)
            await self._set_ac(HVACMode.COOL, self._attr_target_temperature)
        elif needs_heat:
            if use_ac_decision:
                # Heat via AC (with ceiling stratification offset)
                ac_setpoint = round(
                    self._attr_target_temperature + self._ac_temp_offset, 1
                )
                offset_note = (
                    f" (AC setpoint {ac_setpoint}°C incl. +{self._ac_temp_offset}°C plafond-offset)"
                    if self._ac_temp_offset != 0
                    else ""
                )
                self._active_heat_source = HEAT_SOURCE_AC_HEAT
                self._attr_hvac_action = HVACAction.HEATING
                self._demand_active = False
                self._action_summary = (
                    f"Verwarmen via Airco ({self._ac_entity}) naar {self._attr_target_temperature}°C{offset_note}. "
                    f"TRV's blijven gesloten (7.0°C), Master ketel blijft uit."
                )
                await self._set_trvs(DEFAULT_FROST_TEMP)
                await self._set_ac(HVACMode.HEAT, ac_setpoint)
            else:
                # Heat via Gas / Radiators
                self._active_heat_source = HEAT_SOURCE_GAS
                self._attr_hvac_action = HVACAction.HEATING
                self._demand_active = True
                self._last_trv_open_time = now
                self._action_summary = (
                    f"Verwarmen via CV-ketel / radiatoren. TRV's geopend naar {self._attr_target_temperature}°C, "
                    f"Master thermostaat geactiveerd. [Reden geen airco: {self._ac_block_reason}]"
                )
                await self._set_trvs(self._attr_target_temperature)
                await self._set_ac(HVACMode.OFF)
        else:
            # Idle / Temperature reached
            self._active_heat_source = HEAT_SOURCE_IDLE
            self._attr_hvac_action = HVACAction.IDLE
            self._demand_active = False
            self._action_summary = f"Rust: doeltemperatuur ({self._attr_target_temperature}°C) is bereikt"
            await self._set_trvs(self._attr_target_temperature)
            await self._set_ac(HVACMode.OFF)

        # 7b. Weekly TRV Valve Exercise (Anti-calcification)
        if self._valve_exercise_enabled and self._trvs and not effective_paused:
            if (now - self._last_trv_open_time) >= timedelta(
                days=VALVE_EXERCISE_INTERVAL_DAYS
            ):
                self._valve_exercise_until = now + timedelta(
                    minutes=VALVE_EXERCISE_DURATION_MINUTES
                )
                self._last_trv_open_time = now

        if (
            self._valve_exercise_until is not None
            and now < self._valve_exercise_until
            and not self._demand_active
            and not effective_paused
        ):
            await self._set_trvs(25.0)
            self._action_summary = (
                f"{self._action_summary} [Wekelijkse TRV-klepoefening actief tot "
                f"{self._valve_exercise_until.strftime('%H:%M')} (ketel blijft uit)]"
            )

        # 7c. Continuous Heating Anomaly Check (Stuck heating / unmonitored open window)
        if self._attr_hvac_action == HVACAction.HEATING:
            if self._heating_started_at is None:
                self._heating_started_at = now
                self._heating_start_temp = self._attr_current_temperature
            else:
                elapsed_hours = (
                    now - self._heating_started_at
                ).total_seconds() / 3600.0
                if elapsed_hours >= DEFAULT_MAX_CONTINUOUS_HEAT_HOURS:
                    temp_gain = (
                        self._attr_current_temperature - self._heating_start_temp
                        if (
                            self._attr_current_temperature is not None
                            and self._heating_start_temp is not None
                        )
                        else 0.0
                    )
                    if temp_gain <= 0.2:
                        self.hass.async_create_task(
                            self.coordinator.async_send_anomaly_warning(
                                self._room_id,
                                self._attr_name or "Kamer",
                                "continuous_heat",
                                f"⚠️ HA Heating: Langdurig verwarmen ({self._attr_name})",
                                f"Langdurig verwarmen zonder temperatuurstijging in '{self._attr_name}' "
                                f"({elapsed_hours:.1f} uur onafgebroken actief, {self._heating_start_temp}°C -> {self._attr_current_temperature}°C). "
                                f"Controleer of een raam openstaat of de verwarming geblokkeerd is.",
                            )
                        )
                    self._heating_started_at = now
                    self._heating_start_temp = self._attr_current_temperature
        else:
            self._heating_started_at = None
            self._heating_start_temp = None

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
        """Command all TRVs in this room to the desired temperature if not already set."""
        for trv in self._trvs:
            st = self.hass.states.get(trv)
            if (
                st is not None
                and isinstance(st.state, str)
                and st.state not in ("unavailable", "unknown")
            ):
                curr_target = st.attributes.get("temperature") if st.attributes else None
                if isinstance(curr_target, (int, float, str)):
                    try:
                        if abs(float(curr_target) - temp) < 0.05:
                            self._last_commanded_trv_temps[trv] = temp
                            continue
                    except (ValueError, TypeError):
                        pass
            elif self._last_commanded_trv_temps.get(trv) == temp:
                continue

            try:
                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {"entity_id": trv, "temperature": temp},
                    blocking=False,
                )
                self._last_commanded_trv_temps[trv] = temp
            except Exception as err:
                _LOGGER.error("Failed to set temperature for TRV '%s': %s", trv, err)

    async def _set_ac(self, mode: HVACMode, temp: float | None = None) -> None:
        """Command the room AC unit if state or target temperature differs."""
        if not self._ac_entity:
            return

        mode_val = mode.value if hasattr(mode, "value") else str(mode)
        target_key = (mode_val, round(temp, 1) if temp is not None else None)

        st = self.hass.states.get(self._ac_entity)
        if (
            st is not None
            and isinstance(st.state, str)
            and st.state not in ("unavailable", "unknown")
        ):
            if st.state == mode_val:
                if mode == HVACMode.OFF:
                    self._last_commanded_ac_state = target_key
                    return
                curr_target = st.attributes.get("temperature") if st.attributes else None
                if temp is None or (
                    isinstance(curr_target, (int, float, str))
                    and abs(float(curr_target) - temp) < 0.05
                ):
                    self._last_commanded_ac_state = target_key
                    return
        elif self._last_commanded_ac_state == target_key:
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
            self._last_commanded_ac_state = target_key
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
            # Diagnostic attributes for debugging and transparency
            "diagnostic_target_reason": self._reason,
            "diagnostic_demand_reason": self._demand_reason,
            "diagnostic_ac_eligible": (self._ac_entity is not None and not is_quiet and self._attr_preset_mode != PRESET_SLEEP),
            "diagnostic_ac_block_reason": self._ac_block_reason,
            "diagnostic_arbitrage_reason": coord_data.get("arbitrage_reason", ""),
            "diagnostic_action_summary": self._action_summary,
            "diagnostic_master_status": (
                self._master_controller.get_status_description(now)
                if self._master_controller
                else "Geen master gekoppeld"
            ),
            "manual_override_temp": self._manual_override_temp,
            "manual_override_until": (
                self._manual_override_until.isoformat()
                if self._manual_override_until
                else None
            ),
            "boost_until": (
                self._boost_until.isoformat() if self._boost_until else None
            ),
            "pre_boost_preset": self._pre_boost_preset,
            "last_trv_open_time": (
                self._last_trv_open_time.isoformat()
                if self._last_trv_open_time
                else None
            ),
            "valve_exercise_active": bool(
                self._valve_exercise_until and now < self._valve_exercise_until
            ),
            "rapid_drop_paused": bool(
                self._rapid_drop_pause_until and now < self._rapid_drop_pause_until
            ),
            "auto_away_active": coord_data.get("is_auto_away", False),
            "solar_buffer_active": coord_data.get("solar_buffer_active", False),
            "solar_buffer_reason": coord_data.get("solar_buffer_reason", ""),
            "ac_temp_offset": self._ac_temp_offset,
        }

    async def async_will_remove_from_hass(self) -> None:
        """Handle removal."""
        if self._master_controller:
            self._master_controller.unregister_room(self._room_id)
        self.coordinator.window_manager.cleanup(self._room_id)
        await super().async_will_remove_from_hass()

