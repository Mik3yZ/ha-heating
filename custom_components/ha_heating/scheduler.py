"""Scheduler and 2-week cycle manager with calendar vacation overrides."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging

from .const import (
    CYCLE_ANCHOR_DATE,
    CYCLE_EXTERNAL_ENTITY,
    CYCLE_ISO_EVEN_ODD,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_HOLIDAY,
    PRESET_SLEEP,
)

_LOGGER = logging.getLogger(__name__)


class HeatingScheduler:
    """Manages week cycle determination, calendar vacation checks, and preset resolutions."""

    def __init__(
        self,
        cycle_type: str = CYCLE_ISO_EVEN_ODD,
        cycle_anchor_date_str: str | None = None,
        calendar_filter: str | None = None,
    ) -> None:
        """Initialize scheduler."""
        self.cycle_type = cycle_type
        self.cycle_anchor_date_str = cycle_anchor_date_str
        self.calendar_filter = (
            calendar_filter.lower().strip() if calendar_filter else None
        )

        self._anchor_date: date | None = None
        if self.cycle_anchor_date_str:
            try:
                self._anchor_date = datetime.strptime(
                    self.cycle_anchor_date_str, "%Y-%m-%d"
                ).date()
            except ValueError:
                _LOGGER.warning(
                    "Invalid anchor date format: %s. Expected YYYY-MM-DD",
                    self.cycle_anchor_date_str,
                )

    def determine_week_cycle(
        self, current_dt: datetime, external_entity_state: str | None = None
    ) -> str:
        """Determine if current time is 'week_a' or 'week_b'.

        Returns 'week_a' or 'week_b'.
        """
        if self.cycle_type == CYCLE_EXTERNAL_ENTITY and external_entity_state:
            state_lower = external_entity_state.lower().strip()
            if any(term in state_lower for term in ["a", "1", "one", "even"]):
                return "week_a"
            return "week_b"

        if self.cycle_type == CYCLE_ANCHOR_DATE and self._anchor_date:
            days_diff = (current_dt.date() - self._anchor_date).days
            week_idx = (days_diff // 7) % 2
            return "week_a" if week_idx == 0 else "week_b"

        # Default: CYCLE_ISO_EVEN_ODD
        iso_week = current_dt.isocalendar()[1]
        return "week_a" if iso_week % 2 == 0 else "week_b"

    def is_vacation_active(
        self,
        calendar_state: str | None,
        calendar_attributes: dict | None = None,
    ) -> bool:
        """Check if vacation override is currently active on the configured calendar."""
        if not calendar_state or calendar_state.lower() != "on":
            return False

        if not self.calendar_filter:
            # If no filter word specified, any active calendar event triggers vacation mode
            return True

        if calendar_attributes:
            message = str(calendar_attributes.get("message", "")).lower()
            description = str(calendar_attributes.get("description", "")).lower()
            if self.calendar_filter in message or self.calendar_filter in description:
                return True

        return False

    def resolve_target_temperature(
        self,
        current_dt: datetime,
        preset_mode: str | None,
        is_vacation: bool,
        active_week: str,
        schedule_a_state: str | None,
        schedule_b_state: str | None,
        preset_temps: dict[str, float],
        manual_override_temp: float | None = None,
        manual_override_until: datetime | None = None,
    ) -> tuple[float, str]:
        """Resolve the current target temperature and active reason.

        Returns (target_temp: float, reason: str).
        """
        # 1. Manual override takes priority until expiration
        if manual_override_temp is not None:
            if manual_override_until is None or current_dt < manual_override_until:
                return manual_override_temp, "Manual override active"

        # 2. Vacation / Holiday Calendar override
        if is_vacation:
            holiday_temp = preset_temps.get(PRESET_HOLIDAY, 15.0)
            return holiday_temp, "Vacation calendar event active"

        # 3. Explicit preset mode requested by user (e.g. Boost, Away, Sleep)
        if preset_mode == PRESET_BOOST:
            return preset_temps.get(PRESET_BOOST, 22.0), "Preset: Boost"
        if preset_mode == PRESET_AWAY:
            return preset_temps.get(PRESET_AWAY, 15.0), "Preset: Away"
        if preset_mode == PRESET_SLEEP:
            return preset_temps.get(PRESET_SLEEP, 16.0), "Preset: Sleep"
        if preset_mode == PRESET_ECO:
            return preset_temps.get(PRESET_ECO, 18.0), "Preset: Eco"
        if preset_mode == PRESET_COMFORT:
            return preset_temps.get(PRESET_COMFORT, 20.5), "Preset: Comfort"

        # 4. Schedule-based determination according to active week
        active_schedule_state = (
            schedule_a_state if active_week == "week_a" else schedule_b_state
        )

        comfort_temp = preset_temps.get(PRESET_COMFORT, 20.5)
        eco_temp = preset_temps.get(PRESET_ECO, 18.0)

        if active_schedule_state is not None:
            if active_schedule_state.lower() == "on":
                return comfort_temp, f"Schedule ({active_week.upper()}): Comfort"
            return eco_temp, f"Schedule ({active_week.upper()}): Eco"

        # 5. Default fallback if no schedule helper attached
        return comfort_temp, "Default comfort setpoint"

