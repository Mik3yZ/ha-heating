"""Dynamic Lovelace Dashboard generator for HA Heating.

Inspects active HA Heating config entries, entities, and sensors to produce
a modern, beautifully grouped Lovelace dashboard using Mushroom cards.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import area_registry as ar, entity_registry as er

from .const import (
    CONF_AC_ENTITY,
    CONF_AREA_ID,
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
    """Generate complete Lovelace dashboard YAML content with modern Mushroom styling."""
    master_switch_ent = hub_sensors.get(
        "master_switch", "switch.ha_heating_central_hub_hoofdschakelaar"
    )
    week_sensor = hub_sensors.get(
        "active_week", "sensor.ha_heating_central_hub_actieve_week"
    )
    arbitrage_sensor = hub_sensors.get(
        "arbitrage_reason", "sensor.ha_heating_central_hub_arbitrage_advies"
    )
    cop_sensor = hub_sensors.get(
        "airco_cop", "sensor.ha_heating_central_hub_airco_cop"
    )
    thermal_gas = hub_sensors.get(
        "thermal_cost_gas", "sensor.ha_heating_central_hub_thermische_kosten_gas"
    )
    thermal_elec = hub_sensors.get(
        "thermal_cost_electric", "sensor.ha_heating_central_hub_thermische_kosten_airco"
    )

    lines: list[str] = [
        "# HA Heating - Modern Lovelace Dashboard",
        "# Gebaseerd op jouw actieve HA Heating configuratie & entiteiten",
        "#",
        "# Tip: Installeer 'Mushroom' via HACS (HACS > Frontend > Mushroom)",
        "# voor de optimale moderne kaartweergave.",
        "",
        "title: HA Heating Klimaat",
        "icon: mdi:home-thermometer",
        "views:",
        "  - title: Kamers & Zones",
        "    path: kamers",
        "    icon: mdi:radiator",
        "    cards:",
        "      # 1. Centrale Systeem Header (Hoofdschakelaar & Status)",
        "      - type: custom:mushroom-chips-card",
        "        alignment: center",
        "        chips:",
        "          - type: template",
        f"            entity: {master_switch_ent}",
        "            icon: mdi:power",
        f"            icon_color: \"{{{{ 'green' if is_state('{master_switch_ent}', 'on') else 'red' }}}}\"",
        f"            content: \"{{{{ 'Systeem AAN' if is_state('{master_switch_ent}', 'on') else 'Systeem UIT' }}}}\"",
        "            tap_action:",
        "              action: toggle",
        "          - type: template",
        f"            entity: {week_sensor}",
        "            icon: mdi:calendar-sync",
        "            icon_color: cyan",
        f"            content: \"{{{{ states('{week_sensor}') | replace('week_a', 'Week A') | replace('week_b', 'Week B') }}}}\"",
        "          - type: template",
        f"            entity: {arbitrage_sensor}",
        "            icon: mdi:scale-balance",
        "            icon_color: amber",
        f"            content: \"{{{{ states('{arbitrage_sensor}') }}}}\"",
        "          - type: template",
        f"            entity: {cop_sensor}",
        "            icon: mdi:heat-pump-outline",
        "            icon_color: light-blue",
        f"            content: \"{{{{ 'COP ' ~ states('{cop_sensor}') }}}}\"",
        "",
    ]

    # Group rooms by Area
    if rooms:
        areas: dict[str, list[dict[str, Any]]] = {}
        for room in rooms:
            aname = room.get("area_name") or room.get("name") or "Kamers"
            areas.setdefault(aname, []).append(room)

        for aname, area_rooms in areas.items():
            count_str = f"{len(area_rooms)} kamer{'s' if len(area_rooms) > 1 else ''}"
            lines.extend([
                f"      # --- Ruimte Groep: {aname} ---",
                "      - type: custom:mushroom-title-card",
                f"        title: \"{aname}\"",
                f"        subtitle: \"{count_str} geconfigureerd\"",
                "",
            ])

            for room in area_rooms:
                rname = room.get("name", "Kamer")
                climate_id = room.get("climate_id")
                trvs = room.get("trvs", [])
                windows = room.get("windows", [])
                ac_entity = room.get("ac_entity")

                hvac_modes = ["heat", '"off"']
                if ac_entity:
                    hvac_modes.append("cool")

                lines.extend([
                    f"      # Kamer: {rname}",
                    "      - type: vertical-stack",
                    "        cards:",
                    "          - type: custom:mushroom-climate-card",
                    f"            entity: {climate_id}",
                    f"            name: \"{rname}\"",
                    "            icon: mdi:radiator",
                    "            show_temperature_control: true",
                    "            collapsible_controls: false",
                    "            hvac_modes:",
                ])
                for m in hvac_modes:
                    lines.append(f"              - {m}")

                # Preset buttons chips row
                lines.extend([
                    "          # Snelle Preset Knoppen",
                    "          - type: custom:mushroom-chips-card",
                    "            alignment: center",
                    "            chips:",
                    "              - type: template",
                    "                icon: mdi:fire",
                    f"                icon_color: \"{{{{ 'red' if is_state_attr('{climate_id}', 'preset_mode', 'comfort') else 'grey' }}}}\"",
                    "                content: \"Comfort\"",
                    "                tap_action:",
                    "                  action: call-service",
                    "                  service: climate.set_preset_mode",
                    "                  target:",
                    f"                    entity_id: {climate_id}",
                    "                  data:",
                    "                    preset_mode: comfort",
                    "              - type: template",
                    "                icon: mdi:leaf",
                    f"                icon_color: \"{{{{ 'green' if is_state_attr('{climate_id}', 'preset_mode', 'eco') else 'grey' }}}}\"",
                    "                content: \"Eco\"",
                    "                tap_action:",
                    "                  action: call-service",
                    "                  service: climate.set_preset_mode",
                    "                  target:",
                    f"                    entity_id: {climate_id}",
                    "                  data:",
                    "                    preset_mode: eco",
                    "              - type: template",
                    "                icon: mdi:bed",
                    f"                icon_color: \"{{{{ 'purple' if is_state_attr('{climate_id}', 'preset_mode', 'sleep') else 'grey' }}}}\"",
                    "                content: \"Slaap\"",
                    "                tap_action:",
                    "                  action: call-service",
                    "                  service: climate.set_preset_mode",
                    "                  target:",
                    f"                    entity_id: {climate_id}",
                    "                  data:",
                    "                    preset_mode: sleep",
                    "              - type: template",
                    "                icon: mdi:home-export-outline",
                    f"                icon_color: \"{{{{ 'blue' if is_state_attr('{climate_id}', 'preset_mode', 'away') else 'grey' }}}}\"",
                    "                content: \"Afwezig\"",
                    "                tap_action:",
                    "                  action: call-service",
                    "                  service: climate.set_preset_mode",
                    "                  target:",
                    f"                    entity_id: {climate_id}",
                    "                  data:",
                    "                    preset_mode: away",
                    "              - type: template",
                    "                icon: mdi:rocket-launch",
                    f"                icon_color: \"{{{{ 'deep-orange' if is_state_attr('{climate_id}', 'preset_mode', 'boost') else 'grey' }}}}\"",
                    "                content: \"Boost\"",
                    "                tap_action:",
                    "                  action: call-service",
                    "                  service: climate.set_preset_mode",
                    "                  target:",
                    f"                    entity_id: {climate_id}",
                    "                  data:",
                    "                    preset_mode: boost",
                ])

                # Secondary chips for status, windows and TRVs
                lines.extend([
                    "          # Status & Componenten",
                    "          - type: custom:mushroom-chips-card",
                    "            alignment: start",
                    "            chips:",
                    "              - type: template",
                    f"                icon: \"{{{{ 'mdi:fire' if is_state_attr('{climate_id}', 'active_heat_source', 'gas') else ('mdi:snowflake' if is_state_attr('{climate_id}', 'active_heat_source', 'ac_cool') else ('mdi:heat-pump-outline' if is_state_attr('{climate_id}', 'active_heat_source', 'ac_heat') else ('mdi:window-open-variant' if is_state_attr('{climate_id}', 'active_heat_source', 'window_open') else 'mdi:power-sleep'))) }}}}\"",
                    f"                icon_color: \"{{{{ 'red' if is_state_attr('{climate_id}', 'active_heat_source', 'gas') else ('blue' if is_state_attr('{climate_id}', 'active_heat_source', 'ac_cool') else ('orange' if is_state_attr('{climate_id}', 'active_heat_source', 'ac_heat') else 'grey')) }}}}\"",
                    f"                content: \"{{{{ state_attr('{climate_id}', 'resolution_reason') | default('Rust') }}}}\"",
                ])

                for win in windows:
                    lines.extend([
                        "              - type: template",
                        f"                entity: {win}",
                        f"                icon: \"{{{{ 'mdi:window-open-variant' if is_state('{win}', 'on') else ('mdi:alert-circle' if states('{win}') in ['unavailable', 'unknown'] else 'mdi:window-closed-variant') }}}}\"",
                        f"                icon_color: \"{{{{ 'amber' if is_state('{win}', 'on') else ('red' if states('{win}') in ['unavailable', 'unknown'] else 'green') }}}}\"",
                        f"                content: \"{{{{ 'Raam open' if is_state('{win}', 'on') else ('Offline!' if states('{win}') in ['unavailable', 'unknown'] else 'Dicht') }}}}\"",
                    ])

                for trv in trvs:
                    lines.extend([
                        "              - type: entity",
                        f"                entity: {trv}",
                        "                name: \"Kraan\"",
                        "                icon: mdi:radiator",
                    ])

                if ac_entity:
                    lines.extend([
                        "              - type: entity",
                        f"                entity: {ac_entity}",
                        "                name: \"Airco\"",
                        "                icon: mdi:air-conditioner",
                    ])

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

    # Master Thermostats (Centrale Ketel)
    if masters:
        lines.extend([
            "      # Master Thermostaten (Ketelkoppeling)",
            "      - type: custom:mushroom-title-card",
            "        title: \"Centrale Verwarming\"",
            "        subtitle: \"Master Thermostaat (Vraaggestuurd)\"",
            "      - type: vertical-stack",
            "        cards:",
        ])
        for m in masters:
            lines.extend([
                "          - type: custom:mushroom-climate-card",
                f"            entity: {m}",
                "            name: \"Master Thermostaat\"",
                "            icon: mdi:water-boiler",
                "            show_temperature_control: true",
                "            collapsible_controls: false",
            ])
        lines.append("")

    # View 2: Energie & Arbitrage
    lines.extend([
        "  - title: Energie & Arbitrage",
        "    path: energie",
        "    icon: mdi:lightning-bolt",
        "    cards:",
        "      - type: custom:mushroom-title-card",
        "        title: \"Energie & Arbitrage\"",
        "        subtitle: \"Realtime kostenvergelijking tussen gas en airco warmtepomp\"",
        "",
        "      # Actuele Tarieven & Sensoren",
        "      - type: horizontal-stack",
        "        cards:",
    ])

    gas_sensor = hub_data.get(CONF_GAS_PRICE_SENSOR)
    elec_sensor = hub_data.get(CONF_ELECTRIC_PRICE_SENSOR)
    out_sensor = hub_data.get(CONF_OUTDOOR_TEMP_SENSOR)
    solar_sensor = hub_data.get(CONF_SOLAR_EXPORT_SENSOR)

    sensor_cards = []
    if gas_sensor:
        sensor_cards.append((gas_sensor, "Gasprijs", "mdi:fire", "red"))
    if elec_sensor:
        sensor_cards.append((elec_sensor, "Stroomprijs", "mdi:lightning-bolt", "amber"))
    if out_sensor:
        sensor_cards.append((out_sensor, "Buitentemp", "mdi:thermometer", "blue"))
    if solar_sensor:
        sensor_cards.append((solar_sensor, "Zonne-overschot", "mdi:solar-power", "green"))

    if sensor_cards:
        for ent, sname, sicon, scolor in sensor_cards:
            lines.extend([
                "          - type: custom:mushroom-entity-card",
                f"            entity: {ent}",
                f"            name: \"{sname}\"",
                f"            icon: {sicon}",
                f"            icon_color: {scolor}",
            ])
    else:
        lines.extend([
            "          - type: custom:mushroom-entity-card",
            "            entity: sun.sun",
            "            name: \"Geen tariefsensoren ingesteld\"",
            "            icon: mdi:information-outline",
        ])

    lines.extend([
        "",
        "      # Kosten per kWh Thermische Warmte",
        "      - type: horizontal-stack",
        "        cards:",
        "          - type: gauge",
        f"            entity: {thermal_gas}",
        "            name: \"Kosten Gas per kWh Warmte\"",
        "            unit: \"€/kWh\"",
        "            min: 0.05",
        "            max: 0.35",
        "            needle: true",
        "            severity:",
        "              green: 0.05",
        "              yellow: 0.15",
        "              red: 0.25",
        "          - type: gauge",
        f"            entity: {thermal_elec}",
        "            name: \"Kosten Airco per kWh Warmte\"",
        "            unit: \"€/kWh\"",
        "            min: 0.02",
        "            max: 0.35",
        "            needle: true",
        "            severity:",
        "              green: 0.02",
        "              yellow: 0.12",
        "              red: 0.22",
        "",
        "      # Toelichting Arbitrage Formule",
        "      - type: markdown",
        "        title: \"Slimme Arbitrage Berekening\"",
        "        content: |",
        "          De integratie berekent continu welke warmtebron financieel het voordeligst is:",
        "",
        "          * **Gasverwarming (CV-ketel)**: `P_gas / 9.0 kWh/m³`",
        "          * **Airconditioner / Warmtepomp**: `P_stroom / COP(buitentemperatuur)`",
        "",
        "          Zodra er **zonne-energie overschot** is of stroomprijzen negatief zijn, krijgt de airco automatisch voorrang.",
        "",
    ])

    return "\n".join(lines)


async def async_generate_dashboard(hass: HomeAssistant) -> str:
    """Read HA Heating config entries, resolve entities, and generate Lovelace YAML."""
    entity_reg = er.async_get(hass)
    try:
        area_reg = ar.async_get(hass)
    except Exception:
        area_reg = None

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
        "master_switch": "switch.ha_heating_central_hub_hoofdschakelaar",
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
            if uid.endswith("master_switch") or rent.domain == "switch":
                hub_sensors["master_switch"] = rent.entity_id
            elif uid.endswith("active_week"):
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
        area_id = rdata.get(CONF_AREA_ID)
        area_name = None
        if area_reg and area_id:
            try:
                area = area_reg.async_get_area(area_id)
                if area:
                    area_name = area.name
            except Exception:
                pass
        if not area_name:
            area_name = rname

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
            "area_name": area_name,
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
                    "Er is een modern Lovelace Dashboard aangemaakt op basis van je HA Heating configuratie!\n\n"
                    "Het dashboardbestand staat opgeslagen als `/config/ha_heating_dashboard.yaml`.\n\n"
                    "Tip: Installeer **Mushroom** via HACS voor de beste visuele weergave.\n\n"
                    "Je kunt de YAML ook direct kopiëren en in een dashboard plakken:\n\n"
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
