"""Master thermostat and heat demand aggregation with boiler anti-cycling."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant

from .const import (
    DEFAULT_HYSTERESIS_ON,
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
        boost_temp: float = DEFAULT_MASTER_BOOST_TEMP,
        idle_temp: float = DEFAULT_MASTER_IDLE_TEMP,
        min_cycle_duration_sec: int = DEFAULT_MIN_CYCLE_DURATION,
        min_off_duration_sec: int = DEFAULT_MIN_OFF_DURATION,
    ) -> None:
        """Initialize controller for a specific master thermostat."""
        self.hass = hass
        self.master_entity_id = master_entity_id
        self.control_mode = control_mode
        self.boost_temp = boost_temp
        self.idle_temp = idle_temp
        self.min_cycle_duration_sec = min_cycle_duration_sec
        self.min_off_duration_sec = min_off_duration_sec

        self.linked_rooms: set[str] = set()
        self.active_demanding_rooms: set[str] = set()

        self._is_active: bool = False
        self._last_state_change: datetime | None = None

    @property
    def is_heating_active(self) -> bool:
        """Return True if the master thermostat is currently calling for heat."""
        return self._is_active

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

    async def _activate_master(self) -> None:
        """Command master thermostat to generate heat."""
        if self.control_mode in (
            MASTER_MODE_SETPOINT_BOOST,
            MASTER_MODE_BOTH,
        ):
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": self.master_entity_id,
                    "temperature": self.boost_temp,
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

