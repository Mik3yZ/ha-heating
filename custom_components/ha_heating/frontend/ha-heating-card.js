/**
 * HA Heating Custom Lovelace Card
 * Custom card for individual rooms managed by the ha_heating integration.
 */

class HAHeatingCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define an entity (e.g. climate.slaapkamer_heating)');
    }
    this._config = config;
  }

  set hass(hass) {
    this._hass = hass;
    const entityId = this._config.entity;
    const stateObj = hass.states[entityId];

    if (!stateObj) {
      this.shadowRoot.innerHTML = `<ha-card><div style="padding: 16px; color: var(--error-color, red);">Entiteit niet gevonden: ${entityId}</div></ha-card>`;
      return;
    }

    this._render(stateObj);
  }

  _render(stateObj) {
    const attrs = stateObj.attributes || {};
    const friendlyName = this._config.name || attrs.friendly_name || 'Kamer';
    const currentTemp = attrs.current_temperature !== undefined && attrs.current_temperature !== null ? `${attrs.current_temperature.toFixed(1)}°C` : '--';
    const targetTemp = attrs.temperature !== undefined && attrs.temperature !== null ? `${attrs.temperature.toFixed(1)}°C` : '--';
    const currentPreset = attrs.preset_mode || 'comfort';
    const activeSource = attrs.active_heat_source || 'idle';
    const isWindowOpen = attrs.window_open || false;
    const isWindowPaused = attrs.window_paused || false;
    const activeWeek = (attrs.active_week || 'week_a').toUpperCase();
    const resolutionReason = attrs.resolution_reason || '';
    const isQuietHours = attrs.ac_quiet_hours_active || false;

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
    this.shadowRoot.getElementById('btn-minus').onclick = () => this._adjustTemp(-0.5, attrs.temperature);
    this.shadowRoot.getElementById('btn-plus').onclick = () => this._adjustTemp(0.5, attrs.temperature);

    const buttons = this.shadowRoot.querySelectorAll('.preset-btn');
    buttons.forEach((btn) => {
      btn.onclick = () => {
        const preset = btn.getAttribute('data-preset');
        this._setPreset(preset);
      };
    });
  }

  _adjustTemp(delta, currentTarget) {
    if (currentTarget === undefined || currentTarget === null) return;
    const newTemp = Math.round((currentTarget + delta) * 2) / 2;
    this._hass.callService('climate', 'set_temperature', {
      entity_id: this._config.entity,
      temperature: newTemp,
    });
  }

  _setPreset(preset) {
    this._hass.callService('climate', 'set_preset_mode', {
      entity_id: this._config.entity,
      preset_mode: preset,
    });
  }

  getCardSize() {
    return 3;
  }
}

customElements.define('ha-heating-card', HAHeatingCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'ha-heating-card',
  name: 'HA Heating Room Card',
  description: 'Mooie en interactieve controlekaart voor kamers geregeld door HA Heating.',
});

