"""HA Heating Integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
try:
    from homeassistant.components.http import StaticPathConfig
except ImportError:
    StaticPathConfig = None

from .const import CONF_ENTRY_TYPE, DOMAIN, ENTRY_TYPE_HUB, ENTRY_TYPE_ROOM
from .coordinator import HAHeatingCoordinator
from .dashboard import async_generate_dashboard, async_setup_dashboard_service

_LOGGER = logging.getLogger(__name__)

PLATFORMS_HUB: list[Platform] = [Platform.SENSOR, Platform.SWITCH]
PLATFORMS_ROOM: list[Platform] = [Platform.CLIMATE]


async def _async_register_lovelace_resource(hass: HomeAssistant, url: str) -> None:
    """Automatically register custom card in Lovelace resources if possible."""
    try:
        lovelace = hass.data.get("lovelace")
        if not lovelace:
            return
        resources = getattr(lovelace, "resources", None)
        if not resources:
            return
        if not resources.loaded:
            await resources.async_load()
        if not any(res.get("url", "").startswith(url) for res in resources.async_items()):
            await resources.async_create_item({"res_type": "module", "url": url})
            _LOGGER.info("Registered Lovelace resource: %s", url)
    except Exception as err:
        _LOGGER.debug("Could not auto-register Lovelace resource: %s", err)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the HA Heating component, dashboard service, and static frontend resources."""
    hass.data.setdefault(DOMAIN, {})

    # Register dashboard generator service
    await async_setup_dashboard_service(hass)

    # Register static path and Lovelace resource for custom card
    frontend_dir = Path(__file__).parent / "frontend"
    card_path = frontend_dir / "ha-heating-card.js"
    if card_path.exists():
        try:
            # Home Assistant 2024+ async_register_static_paths support
            if (
                hasattr(hass, "http")
                and hasattr(hass.http, "async_register_static_paths")
                and StaticPathConfig is not None
            ):
                await hass.http.async_register_static_paths([
                    StaticPathConfig("/ha_heating_card/ha-heating-card.js", str(card_path), False)
                ])
            elif hasattr(hass, "http") and hasattr(hass.http, "register_static_path"):
                hass.http.register_static_path("/ha_heating_card/ha-heating-card.js", str(card_path), False)
            _LOGGER.info("Registered static path for /ha_heating_card/ha-heating-card.js")

            await _async_register_lovelace_resource(hass, "/ha_heating_card/ha-heating-card.js")
        except Exception as err:
            _LOGGER.warning("Could not register frontend card static path: %s", err)

    return True


async def _async_forward_entry_setups(
    hass: HomeAssistant, entry: ConfigEntry, platforms: list[Platform]
) -> None:
    """Forward entry setups with backward compatibility for pre-2024.4 Home Assistant."""
    if hasattr(hass.config_entries, "async_forward_entry_setups"):
        await hass.config_entries.async_forward_entry_setups(entry, platforms)
    else:
        for platform in platforms:
            await hass.config_entries.async_forward_entry_setup(entry, platform)


async def _async_unload_platforms(
    hass: HomeAssistant, entry: ConfigEntry, platforms: list[Platform]
) -> bool:
    """Unload platforms with backward compatibility for pre-2024.4 Home Assistant."""
    if hasattr(hass.config_entries, "async_unload_platforms"):
        return await hass.config_entries.async_unload_platforms(entry, platforms)

    results = []
    for platform in platforms:
        results.append(
            await hass.config_entries.async_forward_entry_unload(entry, platform)
        )
    return all(results)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Heating from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    entry_type = entry.data.get(CONF_ENTRY_TYPE)

    # Ensure dashboard generator action is registered
    if not hass.services.has_service(DOMAIN, "generate_dashboard"):
        await async_setup_dashboard_service(hass)

    if entry_type == ENTRY_TYPE_HUB:
        coordinator = HAHeatingCoordinator(hass, entry.data, entry=entry)
        hass.data[DOMAIN]["coordinator"] = coordinator
        hass.data[DOMAIN]["hub_entry"] = entry

        await coordinator.async_setup()
        try:
            await coordinator.async_config_entry_first_refresh()
        except Exception as err:
            _LOGGER.debug("First refresh skipped or not needed: %s", err)
            await coordinator.async_refresh()

        await _async_forward_entry_setups(hass, entry, PLATFORMS_HUB)
    else:
        # Room entry requires coordinator to exist
        if "coordinator" not in hass.data[DOMAIN]:
            _LOGGER.warning(
                "Hub entry not initialized yet. Room '%s' may have limited coordination.",
                entry.title,
            )
        await _async_forward_entry_setups(hass, entry, PLATFORMS_ROOM)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Auto-generate or update dashboard based on active setup
    hass.async_create_task(async_generate_dashboard(hass))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_type = entry.data.get(CONF_ENTRY_TYPE)

    if entry_type == ENTRY_TYPE_HUB:
        unload_ok = await _async_unload_platforms(hass, entry, PLATFORMS_HUB)
        if unload_ok and "coordinator" in hass.data[DOMAIN]:
            hass.data[DOMAIN]["coordinator"].cleanup()
            del hass.data[DOMAIN]["coordinator"]
        return unload_ok

    return await _async_unload_platforms(hass, entry, PLATFORMS_ROOM)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry on options change."""
    await hass.config_entries.async_reload(entry.entry_id)

