/**
 * HA Heating Custom Lovelace Card
 * Custom card for individual rooms or all rooms managed by the ha_heating integration.
 */

class HAHeatingCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._selectedEntity = null;
  }

  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    let entityId = this._config.entity;

    // Discover HA Heating rooms in Home Assistant
    const heatingClimates = Object.keys(hass.states).filter((id) => {
      if (!id.startsWith('climate.')) return false;
      const attrs = hass.states[id].attributes || {};
      return (
        attrs.active_heat_source !== undefined ||
        attrs.heat_demand_active !== undefined ||
        attrs.master_thermostat !== undefined ||
        (attrs.preset_modes && attrs.preset_modes.includes('comfort') && attrs.preset_modes.includes('boost'))
      );
    });

    // If no specific entity is configured, pick from discovered rooms
    if (!entityId) {
      if (heatingClimates.length > 0) {
        if (!this._selectedEntity || !heatingClimates.includes(this._selectedEntity)) {
          this._selectedEntity = heatingClimates[0];
        }
        entityId = this._selectedEntity;
      }
    } else {
      this._selectedEntity = entityId;
    }

    // If still no entity could be determined
    if (!entityId) {
      const allClimates = Object.keys(hass.states).filter((id) => id.startsWith('climate.'));
      this.shadowRoot.innerHTML = `
        <ha-card style="padding: 18px; color: var(--primary-text-color, #fff); font-family: sans-serif;">
          <h3 style="margin: 0 0 10px 0; display: flex; align-items: center; gap: 8px;">
            <span>ℹ️</span> HA Heating Kaart
          </h3>
          <p style="margin: 0 0 10px 0; font-size: 0.9rem; opacity: 0.85;">
            Er zijn nog geen specifieke HA Heating kamers gevonden. Geef een entiteit op via <code>entity: climate.&lt;naam&gt;</code> in de kaartconfiguratie.
          </p>
          <div style="font-size: 0.85rem; background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px;">
            <strong>Gevonden klimaatentiteiten:</strong>
            <ul style="margin: 6px 0 0 18px; padding: 0;">
              ${allClimates.map((c) => `<li><code>${c}</code></li>`).join('') || '<li>Geen klimaatentiteiten gevonden</li>'}
            </ul>
          </div>
        </ha-card>
      `;
      return;
    }

    const stateObj = hass.states[entityId];
    if (!stateObj) {
      const allClimates = Object.keys(hass.states).filter((id) => id.startsWith('climate.'));
      this.shadowRoot.innerHTML = `
        <ha-card style="padding: 18px; color: var(--primary-text-color, #fff); font-family: sans-serif;">
          <h3 style="margin: 0 0 10px 0; color: #ff5252;">⚠️ Entiteit niet gevonden: ${entityId}</h3>
          <p style="margin: 0 0 10px 0; font-size: 0.9rem; opacity: 0.85;">
            Controleer de naam van je kamer-thermostaat. Beschikbare klimaatentiteiten:
          </p>
          <ul style="margin: 0 0 0 18px; padding: 0; font-size: 0.85rem;">
            ${allClimates.map((c) => `<li><code>${c}</code></li>`).join('') || '<li>Geen klimaatentiteiten</li>'}
          </ul>
        </ha-card>
      `;
      return;
    }

    this._render(stateObj, entityId, heatingClimates);
  }

  _render(stateObj, entityId, availableClimates) {
    const attrs = stateObj.attributes || {};
    const friendlyName = this._config.name || attrs.friendly_name || 'Kamer';
    const currentTemp =
      attrs.current_temperature !== undefined && attrs.current_temperature !== null
        ? `${attrs.current_temperature.toFixed(1)}°C`
        : '--';
    const targetTemp =
      attrs.temperature !== undefined && attrs.temperature !== null
        ? `${attrs.temperature.toFixed(1)}°C`
        : '--';
    const currentPreset = attrs.preset_mode || 'comfort';
    const activeSource = attrs.active_heat_source || 'idle';
    const isWindowOpen = attrs.window_open || false;
    const isWindowPaused = attrs.window_paused || false;
    const activeWeek = (attrs.active_week || 'week_a').toUpperCase();
    const resolutionReason = attrs.resolution_reason || '';
    const isQuietHours = attrs.ac_quiet_hours_active || false;

    // Room switcher tabs (if multiple heating climates detected and card not locked to one)
    let tabsHtml = '';
    if (!this._config.entity && availableClimates && availableClimates.length > 1) {
      tabsHtml = `
        <div class="tabs-bar">
          ${availableClimates
            .map((cid) => {
              const cst = this._hass.states[cid];
              const cname = (cst && cst.attributes && cst.attributes.friendly_name) || cid.replace('climate.', '');
              const activeClass = cid === entityId ? 'active' : '';
              return `<button class="tab-btn ${activeClass}" data-entity="${cid}">${cname}</button>`;
            })
            .join('')}
        </div>
      `;
    }

    // Badges logic
    let sourceBadge = '';
    if (isWindowPaused || isWindowOpen) {
      sourceBadge = `<span class="badge badge-window">🪟 Raam Open (Gepauzeerd)</span>`;
    } else if (activeSource === 'gas') {
      sourceBadge = `<span class="badge badge-gas">🔥 Gas / CV Actief</span>`;
    } else if (activeSource === 'ac_heat') {
      sourceBadge = `<span class="badge badge-ac">⚡ Airco Verwarmt</span>`;
    } else if (activeSource === 'ac_cool') {
      sourceBadge = `<span class="badge badge-cool">❄️ Airco Koelt</span>`;
    } else {
      sourceBadge = `<span class="badge badge-idle">💤 Stand-by</span>`;
    }

    let quietBadge = isQuietHours ? `<span class="badge badge-quiet">🌙 Stille uren</span>` : '';

    const presets = [
      { id: 'comfort', label: 'Comfort', icon: '🛋️' },
      { id: 'eco', label: 'Eco', icon: '🌱' },
      { id: 'sleep', label: 'Nacht', icon: '🌙' },
      { id: 'away', label: 'Weg', icon: '🚪' },
      { id: 'boost', label: 'Boost', icon: '🚀' },
    ];

    const presetButtons = presets
      .map(
        (p) => `
        <button class="preset-btn ${currentPreset === p.id ? 'active' : ''}" data-preset="${p.id}">
          ${p.icon} ${p.label}
        </button>
      `
      )
      .join('');

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }
        ha-card {
          background: var(--ha-card-background, var(--card-background-color, #1c1c1e));
          border-radius: var(--ha-card-border-radius, 16px);
          box-shadow: var(--ha-card-box-shadow, 0 4px 12px rgba(0,0,0,0.15));
          padding: 18px;
          color: var(--primary-text-color, #fff);
          font-family: var(--paper-font-body1_-_font-family, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto);
        }
        .tabs-bar {
          display: flex;
          gap: 6px;
          overflow-x: auto;
          margin-bottom: 12px;
          padding-bottom: 4px;
        }
        .tab-btn {
          background: rgba(255, 255, 255, 0.08);
          border: 1px solid transparent;
          color: var(--secondary-text-color, #aaa);
          padding: 6px 12px;
          border-radius: 20px;
          font-size: 0.8rem;
          cursor: pointer;
          white-space: nowrap;
          transition: all 0.2s;
        }
        .tab-btn.active {
          background: var(--primary-color, #03a9f4);
          color: #fff;
          font-weight: 600;
        }
        .header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }
        .title {
          font-size: 1.25rem;
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .week-pill {
          font-size: 0.75rem;
          font-weight: 700;
          padding: 3px 8px;
          background: rgba(255, 255, 255, 0.12);
          border-radius: 12px;
          color: var(--secondary-text-color, #aaa);
        }
        .temp-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          background: rgba(255, 255, 255, 0.04);
          padding: 14px 18px;
          border-radius: 12px;
          margin-bottom: 14px;
        }
        .current-temp-block {
          display: flex;
          flex-direction: column;
        }
        .current-label {
          font-size: 0.8rem;
          color: var(--secondary-text-color, #aaa);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .current-val {
          font-size: 2.2rem;
          font-weight: 700;
          line-height: 1.1;
        }
        .target-temp-control {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .ctrl-btn {
          background: rgba(255, 255, 255, 0.1);
          color: var(--primary-text-color, #fff);
          border: none;
          width: 38px;
          height: 38px;
          border-radius: 50%;
          font-size: 1.2rem;
          font-weight: bold;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: background 0.2s, transform 0.1s;
        }
        .ctrl-btn:hover {
          background: rgba(255, 255, 255, 0.2);
        }
        .ctrl-btn:active {
          transform: scale(0.92);
        }
        .target-display {
          display: flex;
          flex-direction: column;
          align-items: center;
          min-width: 65px;
        }
        .target-val {
          font-size: 1.4rem;
          font-weight: 600;
          color: var(--primary-color, #03a9f4);
        }
        .badges-row {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-bottom: 14px;
        }
        .badge {
          display: inline-flex;
          align-items: center;
          padding: 4px 10px;
          border-radius: 20px;
          font-size: 0.82rem;
          font-weight: 600;
        }
        .badge-gas {
          background: rgba(255, 111, 0, 0.2);
          color: #ff9800;
          border: 1px solid rgba(255, 152, 0, 0.4);
        }
        .badge-ac {
          background: rgba(0, 200, 83, 0.2);
          color: #00e676;
          border: 1px solid rgba(0, 230, 118, 0.4);
        }
        .badge-cool {
          background: rgba(33, 150, 243, 0.2);
          color: #2196f3;
          border: 1px solid rgba(33, 150, 243, 0.4);
        }
        .badge-window {
          background: rgba(244, 67, 54, 0.2);
          color: #ff5252;
          border: 1px solid rgba(244, 67, 54, 0.4);
          animation: pulse 2s infinite;
        }
        .badge-quiet {
          background: rgba(156, 39, 176, 0.2);
          color: #ba68c8;
        }
        .badge-idle {
          background: rgba(255, 255, 255, 0.08);
          color: var(--secondary-text-color, #888);
        }
        @keyframes pulse {
          0% { opacity: 0.8; }
          50% { opacity: 1; }
          100% { opacity: 0.8; }
        }
        .presets-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(68px, 1fr));
          gap: 6px;
          margin-bottom: 12px;
        }
        .preset-btn {
          background: rgba(255, 255, 255, 0.06);
          border: 1px solid transparent;
          border-radius: 8px;
          padding: 8px 4px;
          color: var(--primary-text-color, #eee);
          font-size: 0.78rem;
          font-weight: 500;
          cursor: pointer;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
          transition: all 0.2s;
        }
        .preset-btn:hover {
          background: rgba(255, 255, 255, 0.12);
        }
        .preset-btn.active {
          background: var(--primary-color, #03a9f4);
          color: #fff;
          font-weight: 700;
          box-shadow: 0 2px 8px rgba(3, 169, 244, 0.4);
        }
        .footer {
          font-size: 0.75rem;
          color: var(--secondary-text-color, #888);
          display: flex;
          justify-content: space-between;
          border-top: 1px solid rgba(255, 255, 255, 0.08);
          padding-top: 8px;
        }
      </style>

      <ha-card>
        ${tabsHtml}
        <div class="header">
          <div class="title">
            <span>🌡️</span>
            <span>${friendlyName}</span>
          </div>
          <span class="week-pill">${activeWeek}</span>
        </div>

        <div class="temp-row">
          <div class="current-temp-block">
            <span class="current-label">Huidig</span>
            <span class="current-val">${currentTemp}</span>
          </div>
          <div class="target-temp-control">
            <button class="ctrl-btn" id="btn-minus">-</button>
            <div class="target-display">
              <span class="current-label">Doel</span>
              <span class="target-val">${targetTemp}</span>
            </div>
            <button class="ctrl-btn" id="btn-plus">+</button>
          </div>
        </div>

        <div class="badges-row">
          ${sourceBadge}
          ${quietBadge}
        </div>

        <div class="presets-grid">
          ${presetButtons}
        </div>

        <div class="footer">
          <span>${resolutionReason}</span>
          <span>${attrs.heat_demand_active ? '🔥 Ketelvraag' : ''}</span>
        </div>
      </ha-card>
    `;

    // Event listeners
    this.shadowRoot.getElementById('btn-minus').onclick = () =>
      this._adjustTemp(-0.5, attrs.temperature, entityId);
    this.shadowRoot.getElementById('btn-plus').onclick = () =>
      this._adjustTemp(0.5, attrs.temperature, entityId);

    const buttons = this.shadowRoot.querySelectorAll('.preset-btn');
    buttons.forEach((btn) => {
      btn.onclick = () => {
        const preset = btn.getAttribute('data-preset');
        this._setPreset(preset, entityId);
      };
    });

    const tabButtons = this.shadowRoot.querySelectorAll('.tab-btn');
    tabButtons.forEach((tbtn) => {
      tbtn.onclick = () => {
        this._selectedEntity = tbtn.getAttribute('data-entity');
        this.set_hass_internal();
      };
    });
  }

  set_hass_internal() {
    if (this._hass) {
      this.hass = this._hass;
    }
  }

  _adjustTemp(delta, currentTarget, entityId) {
    if (currentTarget === undefined || currentTarget === null) return;
    const newTemp = Math.round((currentTarget + delta) * 2) / 2;
    this._hass.callService('climate', 'set_temperature', {
      entity_id: entityId,
      temperature: newTemp,
    });
  }

  _setPreset(preset, entityId) {
    this._hass.callService('climate', 'set_preset_mode', {
      entity_id: entityId,
      preset_mode: preset,
    });
  }

  getCardSize() {
    return 3;
  }
}

if (!customElements.get('ha-heating-card')) {
  customElements.define('ha-heating-card', HAHeatingCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === 'ha-heating-card')) {
  window.customCards.push({
    type: 'ha-heating-card',
    name: 'HA Heating Room Card',
    description: 'Mooie en interactieve controlekaart voor kamers geregeld door HA Heating.',
  });
}
