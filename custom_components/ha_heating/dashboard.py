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
        "    panel: true",
        "    cards:",
        "      - type: vertical-stack",
        "        card_mod:",
        "          style: |",
        "            #root {",
        "              max-width: 1400px;",
        "              margin: 0 auto;",
        "              padding: 16px;",
        "              gap: 16px;",
        "            }",
        "        cards:",
        "          # 1. Centrale Systeem Header (volledige eerste rij, compact gecentreerd)",
        "          - type: custom:mushroom-chips-card",
        "            alignment: center",
        "            chips:",
        "              - type: template",
        f"                entity: {master_switch_ent}",
        "                icon: mdi:power",
        f"                icon_color: \"{{{{ 'green' if is_state('{master_switch_ent}', 'on') else 'red' }}}}\"",
        f"                content: \"{{{{ 'Systeem AAN' if is_state('{master_switch_ent}', 'on') else 'Systeem UIT' }}}}\"",
        "                tap_action:",
        "                  action: toggle",
        "              - type: template",
        f"                entity: {week_sensor}",
        "                icon: mdi:calendar-sync",
        "                icon_color: cyan",
        f"                content: \"{{{{ states('{week_sensor}') | replace('week_a', 'Week A') | replace('week_b', 'Week B') }}}}\"",
        "              - type: template",
        f"                entity: {arbitrage_sensor}",
        "                icon: mdi:scale-balance",
        "                icon_color: amber",
        f"                content: \"{{{{ states('{arbitrage_sensor}') }}}}\"",
        "              - type: template",
        f"                entity: {cop_sensor}",
        "                icon: mdi:heat-pump-outline",
        "                icon_color: light-blue",
        f"                content: \"{{{{ 'COP ' ~ states('{cop_sensor}') }}}}\"",
        "",
    ]

    # Group rooms by Area
    if rooms:
        areas: dict[str, list[dict[str, Any]]] = {}
        for room in rooms:
            aname = room.get("area_name")
            rname = room.get("name", "Kamer")
            if aname and aname != rname:
                group_key = aname
            else:
                group_key = ""
            areas.setdefault(group_key, []).append(room)

        has_named_areas = any(k for k in areas.keys())

        for group_name, area_rooms in areas.items():
            if group_name and (has_named_areas or len(areas) > 1):
                lines.extend([
                    f"          # --- Ruimte Groep: {group_name} ---",
                    "          - type: custom:mushroom-title-card",
                    f"            title: \"{group_name}\"",
                    "",
                ])

            num_rooms = len(area_rooms)
            cols = 3 if num_rooms in (3, 6) else (2 if num_rooms >= 2 else 1)

            lines.extend([
                "          # Kamers langs elkaar in grid",
                "          - type: grid",
                f"            columns: {cols}",
                "            square: false",
                "            cards:",
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
                    f"              # Kamer: {rname}",
                    "              - type: vertical-stack",
                    "                card_mod:",
                    "                  style: |",
                    "                    #root {",
                    "                      border: 1px solid var(--ha-card-border-color, var(--divider-color, rgba(127, 127, 127, 0.25)));",
                    "                      border-radius: var(--ha-card-border-radius, 16px);",
                    "                      padding: 12px;",
                    "                      background: var(--ha-card-background, var(--card-background-color, rgba(255, 255, 255, 0.04)));",
                    "                      box-shadow: var(--ha-card-box-shadow, none);",
                    "                      gap: 8px;",
                    "                    }",
                    "                    ha-card {",
                    "                      border: none !important;",
                    "                      box-shadow: none !important;",
                    "                      background: transparent !important;",
                    "                    }",
                    "                cards:",
                    "                  - type: custom:mushroom-climate-card",
                    f"                    entity: {climate_id}",
                    f"                    name: \"{rname}\"",
                    "                    icon: mdi:radiator",
                    "                    show_temperature_control: true",
                    "                    collapsible_controls: false",
                    "                    hvac_modes:",
                ])
                for m in hvac_modes:
                    lines.append(f"                      - {m}")

                # Preset buttons chips row
                lines.extend([
                    "                  # Snelle Preset Knoppen",
                    "                  - type: custom:mushroom-chips-card",
                    "                    alignment: center",
                    "                    chips:",
                    "                      - type: template",
                    "                        icon: mdi:fire",
                    f"                        icon_color: \"{{{{ 'red' if is_state_attr('{climate_id}', 'preset_mode', 'comfort') else 'grey' }}}}\"",
                    "                        content: \"Comfort\"",
                    "                        tap_action:",
                    "                          action: call-service",
                    "                          service: climate.set_preset_mode",
                    "                          target:",
                    f"                            entity_id: {climate_id}",
                    "                          data:",
                    "                            preset_mode: comfort",
                    "                      - type: template",
                    "                        icon: mdi:leaf",
                    f"                        icon_color: \"{{{{ 'green' if is_state_attr('{climate_id}', 'preset_mode', 'eco') else 'grey' }}}}\"",
                    "                        content: \"Eco\"",
                    "                        tap_action:",
                    "                          action: call-service",
                    "                          service: climate.set_preset_mode",
                    "                          target:",
                    f"                            entity_id: {climate_id}",
                    "                          data:",
                    "                            preset_mode: eco",
                    "                      - type: template",
                    "                        icon: mdi:bed",
                    f"                        icon_color: \"{{{{ 'purple' if is_state_attr('{climate_id}', 'preset_mode', 'sleep') else 'grey' }}}}\"",
                    "                        content: \"Slaap\"",
                    "                        tap_action:",
                    "                          action: call-service",
                    "                          service: climate.set_preset_mode",
                    "                          target:",
                    f"                            entity_id: {climate_id}",
                    "                          data:",
                    "                            preset_mode: sleep",
                    "                      - type: template",
                    "                        icon: mdi:home-export-outline",
                    f"                        icon_color: \"{{{{ 'blue' if is_state_attr('{climate_id}', 'preset_mode', 'away') else 'grey' }}}}\"",
                    "                        content: \"Afwezig\"",
                    "                        tap_action:",
                    "                          action: call-service",
                    "                          service: climate.set_preset_mode",
                    "                          target:",
                    f"                            entity_id: {climate_id}",
                    "                          data:",
                    "                            preset_mode: away",
                    "                      - type: template",
                    "                        icon: mdi:rocket-launch",
                    f"                        icon_color: \"{{{{ 'deep-orange' if is_state_attr('{climate_id}', 'preset_mode', 'boost') else 'grey' }}}}\"",
                    "                        content: \"Boost\"",
                    "                        tap_action:",
                    "                          action: call-service",
                    "                          service: climate.set_preset_mode",
                    "                          target:",
                    f"                            entity_id: {climate_id}",
                    "                          data:",
                    "                            preset_mode: boost",
                ])

                # Secondary chips for status, windows and TRVs
                lines.extend([
                    "                  # Status & Componenten",
                    "                  - type: custom:mushroom-chips-card",
                    "                    alignment: start",
                    "                    chips:",
                    "                      - type: template",
                    f"                        icon: \"{{{{ 'mdi:fire' if is_state_attr('{climate_id}', 'active_heat_source', 'gas') else ('mdi:snowflake' if is_state_attr('{climate_id}', 'active_heat_source', 'ac_cool') else ('mdi:heat-pump-outline' if is_state_attr('{climate_id}', 'active_heat_source', 'ac_heat') else ('mdi:window-open-variant' if is_state_attr('{climate_id}', 'active_heat_source', 'window_open') else 'mdi:power-sleep'))) }}}}\"",
                    f"                        icon_color: \"{{{{ 'red' if is_state_attr('{climate_id}', 'active_heat_source', 'gas') else ('blue' if is_state_attr('{climate_id}', 'active_heat_source', 'ac_cool') else ('orange' if is_state_attr('{climate_id}', 'active_heat_source', 'ac_heat') else 'grey')) }}}}\"",
                    f"                        content: \"{{{{ state_attr('{climate_id}', 'resolution_reason') | default('Rust') }}}}\"",
                ])

                for win in windows:
                    lines.extend([
                        "                      - type: template",
                        f"                        entity: {win}",
                        f"                        icon: \"{{{{ 'mdi:window-open-variant' if is_state('{win}', 'on') else ('mdi:alert-circle' if states('{win}') in ['unavailable', 'unknown'] else 'mdi:window-closed-variant') }}}}\"",
                        f"                        icon_color: \"{{{{ 'amber' if is_state('{win}', 'on') else ('red' if states('{win}') in ['unavailable', 'unknown'] else 'green') }}}}\"",
                        f"                        content: \"{{{{ 'Raam open' if is_state('{win}', 'on') else ('Offline!' if states('{win}') in ['unavailable', 'unknown'] else 'Dicht') }}}}\"",
                    ])

                for trv in trvs:
                    lines.extend([
                        "                      - type: entity",
                        f"                        entity: {trv}",
                        "                        name: \"Kraan\"",
                        "                        icon: mdi:radiator",
                    ])

                if ac_entity:
                    lines.extend([
                        "                      - type: entity",
                        f"                        entity: {ac_entity}",
                        "                        name: \"Airco\"",
                        "                        icon: mdi:air-conditioner",
                    ])

                lines.append("")
    else:
        lines.extend([
            "          # Geen kamers geconfigureerd",
            "          - type: markdown",
            "            title: Geen Kamers Gevonden",
            "            content: |",
            "              Er zijn nog geen kamers toegevoegd.",
            "              Ga naar **Instellingen > Apparaten & Diensten > Integratie toevoegen > HA Heating** om een kamer toe te voegen.",
            "",
        ])

    # Master Thermostats (Centrale Ketel)
    if masters:
        lines.extend([
            "          # Master Thermostaten (Ketelkoppeling)",
            "          - type: custom:mushroom-title-card",
            "            title: \"Centrale Verwarming\"",
            "            subtitle: \"Master Thermostaat (Vraaggestuurd)\"",
            "          - type: grid",
            "            columns: 2",
            "            square: false",
            "            cards:",
        ])
        for m in masters:
            lines.extend([
                "              - type: vertical-stack",
                "                card_mod:",
                "                  style: |",
                "                    #root {",
                "                      border: 1px solid var(--ha-card-border-color, var(--divider-color, rgba(127, 127, 127, 0.25)));",
                "                      border-radius: var(--ha-card-border-radius, 16px);",
                "                      padding: 12px;",
                "                      background: var(--ha-card-background, var(--card-background-color, rgba(255, 255, 255, 0.04)));",
                "                      box-shadow: var(--ha-card-box-shadow, none);",
                "                    }",
                "                    ha-card {",
                "                      border: none !important;",
                "                      box-shadow: none !important;",
                "                      background: transparent !important;",
                "                    }",
                "                cards:",
                "                  - type: custom:mushroom-climate-card",
                f"                    entity: {m}",
                "                    name: \"Master Thermostaat\"",
                "                    icon: mdi:water-boiler",
                "                    show_temperature_control: true",
                "                    collapsible_controls: false",
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

    # View 3: Diagnostiek & Debug (Keuzeboom en besluitvorming per kamer)
    lines.extend([
        "  # View 3: Diagnostiek & Keuzeboom",
        "  - title: Diagnostiek & Debug",
        "    path: debug",
        "    icon: mdi:bug-check-outline",
        "    cards:",
        "      - type: custom:mushroom-title-card",
        "        title: \"Diagnostiek & Keuzeboom\"",
        "        subtitle: \"Inzicht in besluitvorming: waarom verwarmt een kamer en welke bron is actief?\"",
        "",
        "      # Algemene Systeemstatus & Master Thermostaat",
        "      - type: entities",
        "        title: \"Centrale Systeemstatus & Ketel\"",
        "        show_header_toggle: false",
        "        entities:",
        f"          - entity: {master_switch_ent}",
        "            name: \"Hoofdschakelaar\"",
        f"          - entity: {week_sensor}",
        "            name: \"Actieve Cyclus\"",
        f"          - entity: {arbitrage_sensor}",
        "            name: \"Algemeen Arbitrage Advies\"",
        f"          - entity: {cop_sensor}",
        "            name: \"Airco COP\"",
    ])

    for m in masters:
        lines.append(f"          - entity: {m}\n            name: \"Master Thermostaat (Ketel)\"")

    lines.append("")

    # Per room decision tree and diagnostics
    if rooms:
        for idx, room in enumerate(rooms, start=1):
            rname = room.get("name", f"Kamer {idx}")
            aname = room.get("area_name", "Kamer")
            climate_id = room.get("climate_id")
            trvs = room.get("trvs", [])
            windows = room.get("windows", [])
            ac_entity = room.get("ac_entity")

            lines.extend([
                f"      # --- Diagnostiek: {rname} ---",
                "      - type: custom:mushroom-title-card",
                f"        title: \"Kamer: {rname}\"",
                f"        subtitle: \"Ruimte: {aname}\"",
                "",
                "      - type: markdown",
                f"        title: \"Besluitvorming: {rname}\"",
                "        content: |",
                f"          ### 🎯 1. Doeltemperatuur & Modus",
                f"          * **Doeltemperatuur:** `{{{{ state_attr('{climate_id}', 'temperature') }}}}°C` (Preset: **{{{{ state_attr('{climate_id}', 'preset_mode') | default('onbekend') | upper }}}}**)",
                f"          * **Motivatie doel:** *{{{{ state_attr('{climate_id}', 'diagnostic_target_reason') | default('Niet beschikbaar') }}}}*",
                f"          * **Huidige temperatuur:** `{{{{ state_attr('{climate_id}', 'current_temperature') }}}}°C`",
                "",
                f"          ### ⚡ 2. Warmtevraag (Verwarmen nodig?)",
                f"          * **Warmtevraag actief:** **{{{{ 'JA' if state_attr('{climate_id}', 'heat_demand_active') or is_state_attr('{climate_id}', 'active_heat_source', 'ac_heat') else 'NEE' }}}}**",
                f"          * **Motivatie vraag:** *{{{{ state_attr('{climate_id}', 'diagnostic_demand_reason') | default('Niet beschikbaar') }}}}*",
                f"          * **Raamsensor status:** {{{{ '⚠️ Open (Verwarming gepauzeerd)' if state_attr('{climate_id}', 'window_paused') else '✅ Dicht' }}}}",
                "",
                f"          ### ⚖️ 3. Keuze Warmtebron (Gas vs. Airco)",
                f"          * **Gekozen warmtebron:** **{{{{ '🔥 Gas / CV-ketel' if is_state_attr('{climate_id}', 'active_heat_source', 'gas') else ('❄️ Airco Verwarmen' if is_state_attr('{climate_id}', 'active_heat_source', 'ac_heat') else ('💨 Airco Koelen' if is_state_attr('{climate_id}', 'active_heat_source', 'ac_cool') else ('🪟 Gepauzeerd (Raam open)' if is_state_attr('{climate_id}', 'active_heat_source', 'window_open') else '😴 Rust / Uit'))) }}}}**",
                f"          * **Waarom deze bron gekozen?**",
                f"            > {{{{ state_attr('{climate_id}', 'diagnostic_ac_block_reason') | default('Niet beschikbaar') }}}}",
                f"          * **Kosten per thermische kWh:**",
                f"            * Gas: `€{{{{ state_attr('{climate_id}', 'thermal_cost_gas') | default('-') }}}}/kWh`",
                f"            * Airco: `€{{{{ state_attr('{climate_id}', 'thermal_cost_electric') | default('-') }}}}/kWh` (COP {{{{ state_attr('{climate_id}', 'airco_cop') | default('-') }}}})",
                "",
                f"          ### 🛠️ 4. Status van Actuatoren",
                f"          * **Actiesamenvatting:** *{{{{ state_attr('{climate_id}', 'diagnostic_action_summary') | default('-') }}}}*",
                f"          * **Radiatorkranen (TRV's):** {{{{ 'Geopend (' ~ state_attr('{climate_id}', 'temperature') ~ '°C)' if is_state_attr('{climate_id}', 'active_heat_source', 'gas') else 'Dicht (Vorstbeveiliging 7°C)' }}}}",
                f"          * **Master Thermostaat (Ketel):** {{{{ state_attr('{climate_id}', 'diagnostic_master_status') | default('Geen master') }}}}",
                "",
                "      - type: entities",
                f"        title: \"Live Entiteiten: {rname}\"",
                "        show_header_toggle: false",
                "        entities:",
                f"          - entity: {climate_id}",
                f"            name: \"Klimaat Entiteit\"",
            ])
            for trv in trvs:
                lines.append(f"          - entity: {trv}\n            name: \"Radiatorkraan (TRV)\"")
            for win in windows:
                lines.append(f"          - entity: {win}\n            name: \"Raamsensor\"")
            if ac_entity:
                lines.append(f"          - entity: {ac_entity}\n            name: \"Airco Entiteit\"")
            lines.append("")

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

    # Save to /config/lovelace/ha_heating_dashboard.yaml
    try:
        config_dir = Path(getattr(hass.config, "config_dir", "/config"))
        lovelace_dir = config_dir / "lovelace"
        lovelace_dir.mkdir(parents=True, exist_ok=True)
        target_path = lovelace_dir / "ha_heating_dashboard.yaml"

        existing_content = None
        if target_path.exists():
            try:
                existing_content = target_path.read_text(encoding="utf-8")
            except Exception as err:
                _LOGGER.debug("Could not read existing dashboard file: %s", err)

        # Only proceed with writing and notification if content has actually changed
        if existing_content is not None and existing_content.strip() == yaml_content.strip():
            _LOGGER.debug("Dashboard YAML unchanged; skipping file write and notification")
            return yaml_content

        target_path.write_text(yaml_content, encoding="utf-8")
        _LOGGER.info("Wrote generated dashboard to %s", target_path)

        # Notify user in Home Assistant without full YAML dump
        await hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": "HA Heating Dashboard Bijgewerkt 🌡️",
                "message": (
                    "Er is een actueel Lovelace Dashboard aangemaakt op basis van je HA Heating configuratie!\n\n"
                    "Bestand: `/config/lovelace/ha_heating_dashboard.yaml`\n\n"
                    "Je kunt dit bestand direct gebruiken in je Home Assistant dashboard (via YAML-modus of dashboard toevoegen).\n\n"
                    "Tip voor `configuration.yaml`:\n"
                    "```yaml\n"
                    "lovelace:\n"
                    "  mode: storage\n"
                    "  dashboards:\n"
                    "    ha-heating:\n"
                    "      mode: yaml\n"
                    "      title: HA Heating\n"
                    "      icon: mdi:home-thermometer\n"
                    "      show_in_sidebar: true\n"
                    "      filename: lovelace/ha_heating_dashboard.yaml\n"
                    "```"
                ),
                "notification_id": "ha_heating_dashboard",
            },
            blocking=False,
        )
    except Exception as err:
        _LOGGER.warning("Could not write dashboard file to disk: %s", err)

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
