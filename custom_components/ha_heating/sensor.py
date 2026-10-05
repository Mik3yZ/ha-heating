"""Sensor platform exposing energy arbitrage and system state for dashboards."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENTRY_TYPE, DOMAIN, ENTRY_TYPE_HUB
from .coordinator import HAHeatingCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for the HA Heating hub."""
    if entry.data.get(CONF_ENTRY_TYPE) != ENTRY_TYPE_HUB:
        return

    coordinator: HAHeatingCoordinator = hass.data[DOMAIN]["coordinator"]

    entities = [
        HAHeatingSystemSensor(coordinator, "active_week", "Actieve Week", icon="mdi:calendar-week"),
        HAHeatingSystemSensor(coordinator, "airco_cop", "Airco COP", icon="mdi:heat-pump-outline"),
        HAHeatingSystemSensor(coordinator, "thermal_cost_gas", "Thermische Kosten Gas", unit="€/kWh", state_class=SensorStateClass.MEASUREMENT, icon="mdi:fire"),
        HAHeatingSystemSensor(coordinator, "thermal_cost_electric", "Thermische Kosten Airco", unit="€/kWh", state_class=SensorStateClass.MEASUREMENT, icon="mdi:lightning-bolt"),
        HAHeatingSystemSensor(coordinator, "arbitrage_reason", "Arbitrage Advies", icon="mdi:scale-balance"),
    ]

    async_add_entities(entities)


class HAHeatingSystemSensor(CoordinatorEntity[HAHeatingCoordinator], SensorEntity):
    """Sensor exposing coordinator telemetry."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HAHeatingCoordinator,
        key: str,
        name: str,
        unit: str | None = None,
        state_class: SensorStateClass | None = None,
        icon: str | None = None,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"ha_heating_hub_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "hub")},
            name="HA Heating Central Hub",
            manufacturer="HA Heating",
            model="Central Hub",
        )
        if unit:
            self._attr_native_unit_of_measurement = unit
        if state_class:
            self._attr_state_class = state_class
        if icon:
            self._attr_icon = icon

    @property
    def native_value(self) -> str | float | None:
        """Return the current value."""
        data = self.coordinator.data or {}
        val = data.get(self._key)
        if isinstance(val, float):
            return round(val, 3)
        return val

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed attributes for sensor inspection."""
        data = self.coordinator.data or {}
        if self._key == "arbitrage_reason":
            return {
                "should_use_ac": data.get("should_use_ac"),
                "airco_cop": data.get("airco_cop"),
                "thermal_cost_gas": data.get("thermal_cost_gas"),
                "thermal_cost_electric": data.get("thermal_cost_electric"),
                "solar_export": data.get("solar_export"),
                "outdoor_temp": data.get("outdoor_temp"),
            }
        return {}


