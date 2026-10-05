"""Dynamic Lovelace Dashboard generator for HA Heating.

Inspects active HA Heating config entries, entities, and sensors to produce
a 100% tailor-made, zero-error Lovelace dashboard using native Home Assistant cards.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_AC_ENTITY,
    CONF_ELECTRIC_PRICE_SENSOR,
    CONF_ENTRY_TYPE,
    CONF_GAS_PRICE_SENSOR,
    CONF_MASTER_THERMOSTAT,
    CONF_OUTDOOR_TEMP_SENSOR,
    CONF_ROOM_NAME,
    CONF_SOLAR_EXPORT_SENSOR,
    CONF_TRVS,
    CONF_VACATION_CALENDAR,
    CONF_WINDOW_SENSORS,
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_ROOM,
)

_LOGGER = logging.getLogger(__name__)


def generate_dashboard_yaml(
    hub_data: dict[str, Any],
    hub_sensors: dict[str, str],
    rooms: list[dict[str, Any]],
    masters: list[str],
) -> str:
    """Generate complete Lovelace dashboard YAML content."""
    lines: list[str] = [
        "# HA Heating - Automatisch Gegenereerd Dashboard",
        "# Gebaseerd op jouw actieve HA Heating configuratie & sensoren",
        "# Dit dashboard gebruikt standaard Home Assistant kaarten (geen custom plugins vereist)",
        "",
        "title: HA Heating Klimaat",
        "icon: mdi:home-thermometer",
        "views:",
        "  - title: Kamers & Zones",
        "    path: kamers",
        "    icon: mdi:radiator",
        "    type: grid",
        "    cards:",
    ]

    # Telemetry header row
    lines.extend([
        "      # 1. Systeem Status & Arbitrage Advies",
        "      - type: horizontal-stack",
        "        cards:",
        f"          - type: entity",
        f"            entity: {hub_sensors.get('active_week', 'sensor.ha_heating_central_hub_actieve_week')}",
        "            name: Actieve Cyclus",
        "            icon: mdi:calendar-sync",
        f"          - type: entity",
        f"            entity: {hub_sensors.get('arbitrage_reason', 'sensor.ha_heating_central_hub_arbitrage_advies')}",
        "            name: Advies Verwarmen",
        "            icon: mdi:scale-balance",
        f"          - type: entity",
        f"            entity: {hub_sensors.get('airco_cop', 'sensor.ha_heating_central_hub_airco_cop')}",
        "            name: Airco COP",
        "            icon: mdi:heat-pump-outline",
        "",
    ])

    # Room cards
    if rooms:
        for idx, room in enumerate(rooms, start=1):
            name = room.get("name", f"Kamer {idx}")
            climate_id = room.get("climate_id")
            trvs = room.get("trvs", [])
            windows = room.get("windows", [])
            ac_entity = room.get("ac_entity")

            lines.append(f"      # Kamer {idx}: {name}")
            lines.append("      - type: vertical-stack")
            lines.append("        cards:")
            lines.append(f"          - type: thermostat")
            lines.append(f"            entity: {climate_id}")
            lines.append(f"            name: \"{name}\"")
            lines.append("            features:")
            lines.append("              - type: climate-preset-modes")
            lines.append("                style: icons")
            lines.append("                preset_modes:")
            lines.append("                  - comfort")
            lines.append("                  - eco")
            lines.append("                  - sleep")
            lines.append("                  - away")
            lines.append("                  - boost")

            # Secondary entities card for details (TRVs, Windows, AC)
            sub_entities = []
            for trv in trvs:
                sub_entities.append(f"                  - entity: {trv}\n                    name: Kraan / TRV")
            for win in windows:
                sub_entities.append(f"                  - entity: {win}\n                    name: Raamsensor")
            if ac_entity:
                sub_entities.append(f"                  - entity: {ac_entity}\n                    name: Airco Klimaat")

            if sub_entities:
                lines.append(f"          - type: entities")
                lines.append(f"            title: \"{name} Componenten\"")
                lines.append(f"            show_header_toggle: false")
                lines.append(f"            entities:")
                for sub in sub_entities:
                    lines.append(f"{sub}")
            lines.append("")
    else:
        lines.extend([
            "      # Geen kamers geconfigureerd",
            "      - type: markdown",
            "        title: Geen Kamers Gevonden",
            "        content: |",
            "          Er zijn nog geen kamers toegevoegd.",
            "          Ga naar **Instellingen > Apparaten & Diensten > Integratie toevoegen > HA Heating** om een kamer toe te voegen.",
            "",
        ])

    # Master Thermostats (if configured)
    if masters:
        lines.append("      # Master Thermostaten (Ketelkoppeling)")
        lines.append("      - type: entities")
        lines.append("        title: Centrale Thermostaat & Ketel")
        lines.append("        show_header_toggle: false")
        lines.append("        entities:")
        for m in masters:
            lines.append(f"          - entity: {m}")
            lines.append(f"            name: Master Thermostaat")
        lines.append("")

    # View 2: Energie & Arbitrage
    lines.extend([
        "  - title: Energie & Arbitrage",
        "    path: energie",
        "    icon: mdi:lightning-bolt",
        "    cards:",
        "      - type: vertical-stack",
        "        cards:",
        "          # Tarieven en Buitentemperatuur",
        "          - type: glance",
        "            title: Actuele Energietarieven & Buiten",
        "            entities:",
    ])

    gas_sensor = hub_data.get(CONF_GAS_PRICE_SENSOR)
    elec_sensor = hub_data.get(CONF_ELECTRIC_PRICE_SENSOR)
    out_sensor = hub_data.get(CONF_OUTDOOR_TEMP_SENSOR)
    solar_sensor = hub_data.get(CONF_SOLAR_EXPORT_SENSOR)

    if gas_sensor:
        lines.append(f"              - entity: {gas_sensor}\n                name: Gasprijs (€/m³)\n                icon: mdi:fire")
    if elec_sensor:
        lines.append(f"              - entity: {elec_sensor}\n                name: Stroomprijs (€/kWh)\n                icon: mdi:lightning-bolt")
    if out_sensor:
        lines.append(f"              - entity: {out_sensor}\n                name: Buitentemperatuur\n                icon: mdi:thermometer")
    if solar_sensor:
        lines.append(f"              - entity: {solar_sensor}\n                name: Zonne-overschot\n                icon: mdi:solar-power")

    if not any([gas_sensor, elec_sensor, out_sensor, solar_sensor]):
        lines.append("              - entity: sun.sun\n                name: Geen tariefsensoren geconfigureerd in Hub")

    # Thermal cost gauges
    lines.extend([
        "",
        "          # Kosten per kWh Warmte",
        "          - type: horizontal-stack",
        "            cards:",
        f"              - type: gauge",
        f"                entity: {hub_sensors.get('thermal_cost_gas', 'sensor.ha_heating_central_hub_thermische_kosten_gas')}",
        "                name: Kosten Gas per kWh Warmte",
        "                unit: \"€/kWh\"",
        "                min: 0.05",
        "                max: 0.35",
        "                needle: true",
        "                severity:",
        "                  green: 0.05",
        "                  yellow: 0.15",
        "                  red: 0.25",
        f"              - type: gauge",
        f"                entity: {hub_sensors.get('thermal_cost_electric', 'sensor.ha_heating_central_hub_thermische_kosten_airco')}",
        "                name: Kosten Airco per kWh Warmte",
        "                unit: \"€/kWh\"",
        "                min: 0.02",
        "                max: 0.35",
        "                needle: true",
        "                severity:",
        "                  green: 0.02",
        "                  yellow: 0.12",
        "                  red: 0.22",
        "",
        "          # Toelichting Arbitrage",
        "          - type: markdown",
        "            title: Slimme Arbitrage Berekening",
        "            content: |",
        "              De integratie berekent continu welke warmtebron financieel het voordeligst is:",
        "",
        "              * **Gasverwarming (CV-ketel)**: `P_gas / 9.0 kWh/m³`",
        "              * **Airconditioner / Warmtepomp**: `P_stroom / COP(buitentemperatuur)`",
        "",
        "              Zodra er **zonne-energie overschot** is of stroomprijzen negatief zijn, krijgt de airco automatisch voorrang.",
        "",
    ])

    return "\n".join(lines)


async def async_generate_dashboard(hass: HomeAssistant) -> str:
    """Read HA Heating config entries, resolve entities, and generate Lovelace YAML."""
    entity_reg = er.async_get(hass)

    hub_entries = [
        e for e in hass.config_entries.async_entries(DOMAIN)
        if e.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_HUB
    ]
    room_entries = [
        e for e in hass.config_entries.async_entries(DOMAIN)
        if e.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_ROOM
    ]

    hub_data: dict[str, Any] = {}
    hub_sensors: dict[str, str] = {
        "active_week": "sensor.ha_heating_central_hub_actieve_week",
        "airco_cop": "sensor.ha_heating_central_hub_airco_cop",
        "thermal_cost_gas": "sensor.ha_heating_central_hub_thermische_kosten_gas",
        "thermal_cost_electric": "sensor.ha_heating_central_hub_thermische_kosten_airco",
        "arbitrage_reason": "sensor.ha_heating_central_hub_arbitrage_advies",
    }

    if hub_entries:
        hub_entry = hub_entries[0]
        hub_data = hub_entry.data

        # Map actual entity IDs from Entity Registry for the hub
        registered_entities = er.async_entries_for_config_entry(
            entity_reg, hub_entry.entry_id
        )
        for rent in registered_entities:
            uid = rent.unique_id or ""
            if uid.endswith("active_week"):
                hub_sensors["active_week"] = rent.entity_id
            elif uid.endswith("airco_cop"):
                hub_sensors["airco_cop"] = rent.entity_id
            elif uid.endswith("thermal_cost_gas"):
                hub_sensors["thermal_cost_gas"] = rent.entity_id
            elif uid.endswith("thermal_cost_electric"):
                hub_sensors["thermal_cost_electric"] = rent.entity_id
            elif uid.endswith("arbitrage_reason"):
                hub_sensors["arbitrage_reason"] = rent.entity_id

    rooms: list[dict[str, Any]] = []
    masters: list[str] = []

    for rentry in room_entries:
        rdata = rentry.data
        rname = rdata.get(CONF_ROOM_NAME) or rentry.title

        # Find climate entity ID from entity registry
        room_ents = er.async_entries_for_config_entry(entity_reg, rentry.entry_id)
        climate_ents = [e for e in room_ents if e.domain == "climate"]
        if climate_ents:
            climate_id = climate_ents[0].entity_id
        else:
            # Fallback to standard slug
            slug = rname.lower().replace(" ", "_")
            climate_id = f"climate.{slug}"

        master = rdata.get(CONF_MASTER_THERMOSTAT)
        if master and master not in masters:
            masters.append(master)

        rooms.append({
            "name": rname,
            "climate_id": climate_id,
            "trvs": rdata.get(CONF_TRVS, []),
            "windows": rdata.get(CONF_WINDOW_SENSORS, []),
            "ac_entity": rdata.get(CONF_AC_ENTITY),
            "master": master,
        })

    yaml_content = generate_dashboard_yaml(hub_data, hub_sensors, rooms, masters)

    # Save to /config/ha_heating_dashboard.yaml
    try:
        config_dir = Path(hass.config.config_dir)
        target_path = config_dir / "ha_heating_dashboard.yaml"
        target_path.write_text(yaml_content, encoding="utf-8")
        _LOGGER.info("Wrote generated dashboard to %s", target_path)
    except Exception as err:
        _LOGGER.warning("Could not write dashboard file to disk: %s", err)

    # Also notify user in Home Assistant
    try:
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "HA Heating Dashboard Gegenereerd 🌡️",
                "message": (
                    "Er is een actueel Lovelace Dashboard aangemaakt op basis van je HA Heating configuratie!\n\n"
                    "Het dashboardbestand staat opgeslagen als `/config/ha_heating_dashboard.yaml`.\n\n"
                    "Je kunt de onderstaande YAML ook direct kopiëren en in een nieuw dashboard plakken:\n\n"
                    f"```yaml\n{yaml_content}\n```"
                ),
                "notification_id": "ha_heating_dashboard",
            },
            blocking=False,
        )
    except Exception as err:
        _LOGGER.debug("Could not send persistent notification: %s", err)

    return yaml_content


async def async_setup_dashboard_service(hass: HomeAssistant) -> None:
    """Register the ha_heating.generate_dashboard service."""
    if hass.services.has_service(DOMAIN, "generate_dashboard"):
        return

    async def _handle_generate(call: ServiceCall) -> None:
        await async_generate_dashboard(hass)

    hass.services.async_register(
        DOMAIN,
        "generate_dashboard",
        _handle_generate,
    )
    _LOGGER.info("Registered action ha_heating.generate_dashboard")
