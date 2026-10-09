"""Master thermostat and heat demand aggregation with boiler anti-cycling."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components.climate import HVACMode
from homeassistant.core import Event, HomeAssistant, callback

from .const import (
    DEFAULT_HYSTERESIS_ON,
    DEFAULT_MASTER_BOOST_OFFSET,
    DEFAULT_MASTER_BOOST_TEMP,
    DEFAULT_MASTER_IDLE_TEMP,
    DEFAULT_MIN_CYCLE_DURATION,
    DEFAULT_MIN_OFF_DURATION,
    MASTER_MODE_BOTH,
    MASTER_MODE_HVAC_SWITCH,
    MASTER_MODE_SETPOINT_BOOST,
)

_LOGGER = logging.getLogger(__name__)


class MasterThermostatController:
    """Controls a central/master thermostat based on aggregated room heat demands."""

    def __init__(
        self,
        hass: HomeAssistant,
        master_entity_id: str,
        control_mode: str = MASTER_MODE_SETPOINT_BOOST,
        boost_offset: float = DEFAULT_MASTER_BOOST_OFFSET,
        idle_temp: float = DEFAULT_MASTER_IDLE_TEMP,
        min_cycle_duration_sec: int = DEFAULT_MIN_CYCLE_DURATION,
        min_off_duration_sec: int = DEFAULT_MIN_OFF_DURATION,
        boost_temp: float | None = None,
        boost_fallback_temp: float = DEFAULT_MASTER_BOOST_TEMP,
    ) -> None:
        """Initialize controller for a specific master thermostat."""
        self.hass = hass
        self.master_entity_id = master_entity_id
        self.control_mode = control_mode
        self.idle_temp = idle_temp
        self.min_cycle_duration_sec = min_cycle_duration_sec
        self.min_off_duration_sec = min_off_duration_sec

        if boost_temp is not None:
            if boost_temp > 15.0:
                self.boost_fallback_temp = boost_temp
                self.boost_offset = DEFAULT_MASTER_BOOST_OFFSET
            else:
                self.boost_offset = boost_temp
                self.boost_fallback_temp = boost_fallback_temp
        else:
            self.boost_offset = boost_offset
            self.boost_fallback_temp = boost_fallback_temp

        self.linked_rooms: set[str] = set()
        self.active_demanding_rooms: set[str] = set()

        self._is_active: bool = False
        self._last_state_change: datetime | None = None
        self._unsub_listener = None

    @property
    def is_heating_active(self) -> bool:
        """Return True if the master thermostat is currently calling for heat."""
        return self._is_active

    def get_status_description(self, current_dt: datetime) -> str:
        """Return a human-readable status description including anti-cycling."""
        if self._is_active:
            rooms_str = ", ".join(list(self.active_demanding_rooms)) if self.active_demanding_rooms else "geen"
            if self._last_state_change:
                elapsed = (current_dt - self._last_state_change).total_seconds()
                if elapsed < self.min_cycle_duration_sec:
                    remaining = int(self.min_cycle_duration_sec - elapsed)
                    return f"Actief (vraag van: {rooms_str}), anti-cycling vergrendeld aan (nog {remaining}s)"
            return f"Actief (vraag van: {rooms_str})"
        else:
            if self._last_state_change:
                elapsed = (current_dt - self._last_state_change).total_seconds()
                if elapsed < self.min_off_duration_sec:
                    remaining = int(self.min_off_duration_sec - elapsed)
                    return f"Rust (geen vraag), anti-cycling vergrendeld uit (nog {remaining}s)"
            return "Rust (geen actieve warmtevraag vanuit kamers)"

    def get_diagnostics(self, current_dt: datetime) -> dict[str, Any]:
        """Return full diagnostics dictionary for master thermostat."""
        return {
            "master_entity_id": self.master_entity_id,
            "control_mode": self.control_mode,
            "is_active": self._is_active,
            "boost_offset": self.boost_offset,
            "current_boost_temp": self.calculate_boost_temp(),
            "idle_temp": self.idle_temp,
            "linked_rooms": list(self.linked_rooms),
            "active_demanding_rooms": list(self.active_demanding_rooms),
            "status_description": self.get_status_description(current_dt),
        }

    def register_room(self, room_id: str) -> None:
        """Register a room to this master thermostat."""
        self.linked_rooms.add(room_id)

    def unregister_room(self, room_id: str) -> None:
        """Unregister a room."""
        self.linked_rooms.discard(room_id)
        self.active_demanding_rooms.discard(room_id)

    async def update_room_demand(
        self,
        room_id: str,
        has_demand: bool,
        current_dt: datetime,
    ) -> None:
        """Update heat demand status for a linked room and adjust master thermostat if needed."""
        if room_id not in self.linked_rooms:
            return

        if has_demand:
            self.active_demanding_rooms.add(room_id)
        else:
            self.active_demanding_rooms.discard(room_id)

        target_active = len(self.active_demanding_rooms) > 0
        await self._apply_demand_state(target_active, current_dt)

    async def _apply_demand_state(
        self, target_active: bool, current_dt: datetime
    ) -> None:
        """Evaluate anti-cycling timers and apply state to master thermostat."""
        if target_active == self._is_active:
            return

        # Check anti-cycling rules
        if self._last_state_change is not None:
            time_since_change = (
                current_dt - self._last_state_change
            ).total_seconds()

            if self._is_active and not target_active:
                # Trying to turn off: check minimum run duration
                if time_since_change < self.min_cycle_duration_sec:
                    remaining = self.min_cycle_duration_sec - time_since_change
                    _LOGGER.info(
                        "Master '%s': Boiler minimum cycle duration active (remaining %.0fs), postponing turn off",
                        self.master_entity_id,
                        remaining,
                    )
                    return

            elif not self._is_active and target_active:
                # Trying to turn on: check minimum off duration
                if time_since_change < self.min_off_duration_sec:
                    remaining = self.min_off_duration_sec - time_since_change
                    _LOGGER.info(
                        "Master '%s': Boiler minimum off duration active (remaining %.0fs), postponing turn on",
                        self.master_entity_id,
                        remaining,
                    )
                    return

        # Apply state
        self._is_active = target_active
        self._last_state_change = current_dt

        _LOGGER.info(
            "Master '%s': Switching call for heat to %s (demanding rooms: %s)",
            self.master_entity_id,
            "ON" if target_active else "OFF",
            list(self.active_demanding_rooms),
        )

        try:
            if target_active:
                await self._activate_master()
            else:
                await self._deactivate_master()
        except Exception as err:
            _LOGGER.error(
                "Failed to command master thermostat '%s': %s",
                self.master_entity_id,
                err,
            )

    def calculate_boost_temp(self) -> float:
        """Calculate target setpoint as current_temperature + boost_offset (capped at max_temp)."""
        try:
            if self.hass and hasattr(self.hass, "states"):
                state = self.hass.states.get(self.master_entity_id)
                if state and state.attributes:
                    current_temp = state.attributes.get("current_temperature")
                    max_temp = float(state.attributes.get("max_temp", 35.0))
                    if current_temp is not None:
                        calc = float(current_temp) + self.boost_offset
                        return round(min(calc, max_temp), 1)
        except Exception as err:
            _LOGGER.debug(
                "Error calculating boost temp for %s: %s", self.master_entity_id, err
            )

        return self.boost_fallback_temp

    async def _activate_master(self) -> None:
        """Command master thermostat to generate heat."""
        if self.control_mode in (
            MASTER_MODE_SETPOINT_BOOST,
            MASTER_MODE_BOTH,
        ):
            target_temp = self.calculate_boost_temp()
            _LOGGER.info(
                "Master '%s': Activating heat demand with setpoint %.1f°C (+%.1f°C offset)",
                self.master_entity_id,
                target_temp,
                self.boost_offset,
            )
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": self.master_entity_id,
                    "temperature": target_temp,
                },
                blocking=True,
            )

        if self.control_mode in (MASTER_MODE_HVAC_SWITCH, MASTER_MODE_BOTH):
            await self.hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {
                    "entity_id": self.master_entity_id,
                    "hvac_mode": HVACMode.HEAT,
                },
                blocking=True,
            )

    async def _deactivate_master(self) -> None:
        """Command master thermostat to return to idle."""
        if self.control_mode in (
            MASTER_MODE_SETPOINT_BOOST,
            MASTER_MODE_BOTH,
        ):
            _LOGGER.info(
                "Master '%s': Returning setpoint to idle %.1f°C",
                self.master_entity_id,
                self.idle_temp,
            )
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": self.master_entity_id,
                    "temperature": self.idle_temp,
                },
                blocking=True,
            )

        if self.control_mode in (MASTER_MODE_HVAC_SWITCH, MASTER_MODE_BOTH):
            await self.hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {
                    "entity_id": self.master_entity_id,
                    "hvac_mode": HVACMode.OFF,
                },
                blocking=True,
            )

    async def async_handle_master_state_change(self) -> None:
        """Ensure setpoint stays above current temperature while demand is active."""
        if not self._is_active:
            return
        if self.control_mode not in (MASTER_MODE_SETPOINT_BOOST, MASTER_MODE_BOTH):
            return

        try:
            if not self.hass or not hasattr(self.hass, "states"):
                return
            state = self.hass.states.get(self.master_entity_id)
            if not state or not state.attributes:
                return

            current_temp = state.attributes.get("current_temperature")
            set_temp = state.attributes.get("temperature")
            max_temp = float(state.attributes.get("max_temp", 35.0))

            if current_temp is not None and set_temp is not None:
                current_temp = float(current_temp)
                set_temp = float(set_temp)
                # If current temp approaches setpoint within 0.5°C and not yet at max_temp
                if current_temp >= (set_temp - 0.5) and set_temp < max_temp:
                    new_target = round(min(current_temp + self.boost_offset, max_temp), 1)
                    if new_target > set_temp:
                        _LOGGER.info(
                            "Master '%s': Current temp (%.1f°C) approached setpoint (%.1f°C) with active demand. Bumping to %.1f°C",
                            self.master_entity_id,
                            current_temp,
                            set_temp,
                            new_target,
                        )
                        await self.hass.services.async_call(
                            "climate",
                            "set_temperature",
                            {
                                "entity_id": self.master_entity_id,
                                "temperature": new_target,
                            },
                            blocking=True,
                        )
        except Exception as err:
            _LOGGER.debug("Error in master thermostat setpoint maintenance: %s", err)

    def start_tracking(self) -> None:
        """Start tracking master thermostat state changes."""
        if self._unsub_listener is not None:
            return

        try:
            from homeassistant.helpers.event import async_track_state_change_event

            @callback
            def _handle_master_state_change(event: Event) -> None:
                if self._is_active:
                    self.hass.async_create_task(self.async_handle_master_state_change())

            if hasattr(self.hass, "bus"):
                self._unsub_listener = async_track_state_change_event(
                    self.hass, [self.master_entity_id], _handle_master_state_change
                )
        except Exception as err:
            _LOGGER.debug(
                "Could not attach state change tracker to master %s: %s",
                self.master_entity_id,
                err,
            )

    def stop_tracking(self) -> None:
        """Stop tracking master thermostat state changes."""
        if self._unsub_listener:
            try:
                self._unsub_listener()
            except Exception:
                pass
            self._unsub_listener = None

