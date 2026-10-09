"""Switch platform for HA Heating master on/off control."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENTRY_TYPE, DOMAIN, ENTRY_TYPE_HUB
from .coordinator import HAHeatingCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the master switch for the HA Heating hub."""
    if entry.data.get(CONF_ENTRY_TYPE) != ENTRY_TYPE_HUB:
        return

    coordinator: HAHeatingCoordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([HAHeatingMasterSwitch(coordinator)])


class HAHeatingMasterSwitch(CoordinatorEntity[HAHeatingCoordinator], SwitchEntity):
    """Master switch to enable or disable the entire HA Heating system."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HAHeatingCoordinator) -> None:
        """Initialize the master switch."""
        super().__init__(coordinator)
        self._attr_name = "Hoofdschakelaar"
        self._attr_unique_id = "ha_heating_hub_master_switch"
        self._attr_icon = "mdi:power"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "hub")},
            name="HA Heating Central Hub",
            manufacturer="HA Heating",
            model="Central Hub",
        )

    @property
    def is_on(self) -> bool:
        """Return True if HA Heating is enabled."""
        return self.coordinator.system_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on HA Heating."""
        await self.coordinator.async_set_system_enabled(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off HA Heating."""
        await self.coordinator.async_set_system_enabled(False)
        self.async_write_ha_state()

