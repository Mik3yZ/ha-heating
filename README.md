# HA Heating (Home Assistant)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**HA Heating** is een modulaire, flexibele en universeel configureerbare Home Assistant integratie voor slimme klimaatbeheersing (verwarmen en koelen).

De integratie is ontworpen om onafhankelijk van specifieke hardware te werken (geschikt voor Zigbee TRVs, Moes, Tuya, Tado, Shelly, Z-Wave, WiFi airconditioners, etc.) en lost veelvoorkomende uitdagingen op in hybride huishoudens.

---

## 🌟 Belangrijkste Functies

1. **Kamer- en Zonebeheer (Multi-TRV)**:
   - Maak virtuele kamers aan die automatisch één of meerdere thermostaatkranen (TRVs) synchroniseren.
   - Temperatuurmeting via een losse kamersensor of automatisch berekend als het gemiddelde van alle TRVs.
2. **Optionele Master-Thermostaat Koppeling (Warmtevraag / Call for Heat)**:
   - Ideaal voor situaties met twee thermostaten:
     - Bijv. beneden vloerverwarming (rechtstreeks op de ketel).
     - Boven een centrale thermostaat (zoals de **Moes BHT-002GCLZB**) die de ketel moet inschakelen zodra een radiator warmte vraagt.
   - Keuze uit:
     - **Setpoint Boost**: Verhoogt de master-temperatuur bij warmtevraag en zet hem terug naar ruststand (bijv. 15°C) zodra alle kamers op temperatuur zijn.
     - **HVAC Switch**: Schakelt de master-thermostaat tussen `heat` en `off`.
     - **Gecombineerd**: Beide tegelijk.
   - Ingebouwde **anti-pendelbescherming** (instelbare minimale brandtijd en rusttijd voor de ketel).
3. **Raam- en Deursensoren met Vertraging**:
   - Koppel `binary_sensor` contactsensoren per kamer.
   - Instelbare uitschakelvertraging (bijv. 30 seconden) om te voorkomen dat even snel luchten direct de ketel stillegt.
   - Automatisch herstel van doeltemperatuur en schema zodra alle ramen weer dicht zijn.
4. **2-Wekelijkse Planning & Vakantie-Overrides**:
   - Ondersteunt 2-wekelijkse roosters (**Week A / Week B**) via ISO even/oneven week, een startdatum, of een externe sensor.
   - Volledige integratie met Home Assistant **Schedule Helpers** (voor visuele tijdblokken in de UI).
   - Koppeling met een **Kalender** (Lokale kalender, Google Calendar, iCal): zodra er een vakantie-event actief is, schakelt het systeem automatisch over naar de vakantietemperatuur.
5. **Hybride Arbitrage: Gas (CV) vs. Elektra (Airco)**:
   - Vergelijkt continu de kosten per thermische kWh op basis van dynamische tarieven (Nordpool, Tibber, Frank Energie, etc.).
   - Automatische schatting van de **COP** van de airco op basis van de actuele buitentemperatuur.
   - **Zonne-energie voorrang**: Bij overschot/teruglevering verwarmt de airco gratis en krijgt deze automatisch voorrang.
   - **Stille uren / Quiet Hours**: Instelbare tijdsblokken (bijv. 22:00 - 07:00) en blokkade bij de `Sleep`-preset, zodat in slaapkamers 's nachts altijd geruisloze radiatoren worden gebruikt i.p.v. blazende airco's.
6. **Inclusief Dashboard & Custom Lovelace Card**:
   - Bevat een kant-en-klare custom card (`ha-heating-card`) met statusbadges (🔥 Gas, ⚡ Airco, 🪟 Raam Open), snelle preset-knoppen en temperatuurknoppen (`+` / `-`).
   - Bevat een compleet dashboardtemplate voor een centraal energie- en keteloverzicht.

---

## 📦 Installatie

### Optie 1: Handmatig
1. Download of kloon deze repository.
2. Kopieer de map `custom_components/ha_heating` naar de `config/custom_components/` map van je Home Assistant installatie.
3. Herstart Home Assistant.

### Optie 2: Via HACS (Aanbevolen)
1. Open HACS > Integraties > Drie puntjes rechtsboven > **Aangepaste repositories**.
2. Voeg de repository URL toe met categorie **Integratie**.
3. Klik op Installeren en herstart Home Assistant.

---

## ⚙️ Configuratie

Ga in Home Assistant naar **Instellingen > Apparaten & Diensten > Integratie toevoegen** en zoek naar **HA Heating**.

### Stap 1: Centraal Systeem (Hub)
Configureer de globale gegevens:
- **Gasprijs sensor (€/m³)** & **Stroomprijs sensor (€/kWh)** (bijv. van Tibber, EnergyZero, etc.)
- **Buitentemperatuur sensor** (voor de berekening van de actuele airco COP)
- **Zonne-energie overschot sensor** (optioneel, vermogen in Watt)
- **Vakantiekalender** (optioneel, bijv. `calendar.vakantie`)
- **Type 2-wekelijkse cyclus**: Even/Oneven ISO week of 14-daagse startdatum.

### Stap 2: Kamers Toevoegen
Voeg vervolgens voor elke gewenste ruimte een kamer toe:
- **Naam van de kamer** (bijv. Slaapkamer)
- **Thermostaatkranen (TRVs)**: Selecteer één of meerdere klimaatentiteiten.
- **Raamsensoren**: Selecteer de deursensoren in die kamer met de gewenste vertraging (bijv. 30 sec).
- **Master-thermostaat**: Selecteer de centrale thermostaat boven (bijv. `climate.thermostaat_boven`) en kies de sturingsmethode (*Setpoint Boost* of *HVAC switch*).
- **Airco (optioneel)**: Selecteer de airconditioner van de kamer en stel eventuele *Quiet Hours* in (bijv. 22:00 - 07:00).
- **Schedules**: Koppel eventueel een Week A en Week B schedule helper.
- **Doeltemperaturen**: Stel de standaardtemperaturen in voor Comfort, Eco, Nacht, Afwezig en Vakantie.

---

## 🎨 Dashboard & Lovelace Card

De integratie levert automatisch de **`ha-heating-card`** mee. 

### Kamerkaart toevoegen in je dashboard
Voeg een aangepaste kaart toe aan je dashboard met de volgende YAML:

```yaml
type: custom:ha-heating-card
entity: climate.slaapkamer_heating
name: 🛏️ Slaapkamer
```

### Volledig Dashboard Template
Bekijk het bestand [`custom_components/ha_heating/frontend/dashboard-template.yaml`](custom_components/ha_heating/frontend/dashboard-template.yaml) voor een compleet voorbeeld met:
- Kaarten voor alle kamers.
- Real-time energie-arbitrage meters (Kosten gas vs. kosten airco per kWh warmte).
- Status van de master-thermostaten en ketel.

---

## 🧮 De Energie Arbitrage Formule

De integratie berekent continu:

$$\text{Kosten}_{\text{gas}} = \frac{P_{\text{gas}}}{9{,}0} \quad (\text{HR-ketel rendement verwerkt})$$

$$\text{Kosten}_{\text{airco}} = \frac{P_{\text{stroom}}}{\text{COP}(T_{\text{buiten}})}$$

- Is $\text{Kosten}_{\text{airco}} < \text{Kosten}_{\text{gas}}$? $\rightarrow$ De kamer verwarmt via de airco.
- Is gas voordeliger of zijn stille uren actief? $\rightarrow$ De radiatorkranen openen en de master-thermostaat schakelt de ketel in.
- Is er zonne-energieoverschot ($>200\text{W}$)? $\rightarrow$ De stroomkosten zijn effectief nul en de airco heeft direct voorrang.

---

## 🧪 Tests Uitvoeren

De wiskundige berekeningen, scheduler, debounce timers en ketelbescherming zijn gedekt met unit tests:

```bash
python -m unittest tests/test_ha_heating.py
```

---

## 📄 Licentie

Gepubliceerd onder de MIT-licentie.
