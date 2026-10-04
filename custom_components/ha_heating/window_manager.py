"""Window open/close detection manager with configurable debounce timers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
import logging

from .const import DEFAULT_WINDOW_CLOSE_DELAY, DEFAULT_WINDOW_OPEN_DELAY

_LOGGER = logging.getLogger(__name__)


class WindowManager:
    """Manages open window detection and delays per room."""

    def __init__(
        self,
        open_delay_sec: int = DEFAULT_WINDOW_OPEN_DELAY,
        close_delay_sec: int = DEFAULT_WINDOW_CLOSE_DELAY,
    ) -> None:
        """Initialize WindowManager."""
        self.open_delay_sec = open_delay_sec
        self.close_delay_sec = close_delay_sec
        self._window_open_states: dict[str, bool] = {}
        self._active_timers: dict[str, asyncio.TimerHandle] = {}

    def get_is_room_paused(self, room_id: str) -> bool:
        """Return True if heating in this room is currently paused due to an open window."""
        return self._window_open_states.get(room_id, False)

    def handle_sensor_update(
        self,
        room_id: str,
        any_window_open: bool,
        loop: asyncio.AbstractEventLoop,
        on_state_change: Callable[[str, bool], None],
    ) -> None:
        """Handle a binary sensor state update for windows in a room."""
        # Cancel any pending timer for this room
        if room_id in self._active_timers:
            self._active_timers[room_id].cancel()
            del self._active_timers[room_id]

        current_paused = self._window_open_states.get(room_id, False)

        if any_window_open and not current_paused:
            # Window was opened. Schedule pause after open_delay_sec
            def _trigger_pause():
                self._window_open_states[room_id] = True
                if room_id in self._active_timers:
                    del self._active_timers[room_id]
                _LOGGER.info(
                    "Room '%s': Window open delay (%ss) elapsed -> Pausing heating",
                    room_id,
                    self.open_delay_sec,
                )
                on_state_change(room_id, True)

            _LOGGER.debug(
                "Room '%s': Window opened, delaying pause for %s seconds",
                room_id,
                self.open_delay_sec,
            )
            self._active_timers[room_id] = loop.call_later(
                self.open_delay_sec, _trigger_pause
            )

        elif not any_window_open and current_paused:
            # All windows were closed. Schedule resume after close_delay_sec
            def _trigger_resume():
                self._window_open_states[room_id] = False
                if room_id in self._active_timers:
                    del self._active_timers[room_id]
                _LOGGER.info(
                    "Room '%s': Window close delay (%ss) elapsed -> Resuming heating",
                    room_id,
                    self.close_delay_sec,
                )
                on_state_change(room_id, False)

            _LOGGER.debug(
                "Room '%s': Windows closed, delaying resume for %s seconds",
                room_id,
                self.close_delay_sec,
            )
            self._active_timers[room_id] = loop.call_later(
                self.close_delay_sec, _trigger_resume
            )

    def cleanup(self, room_id: str | None = None) -> None:
        """Cancel pending timers."""
        if room_id:
            if room_id in self._active_timers:
                self._active_timers[room_id].cancel()
                del self._active_timers[room_id]
        else:
            for timer in self._active_timers.values():
                timer.cancel()
            self._active_timers.clear()

