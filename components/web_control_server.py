#!/usr/bin/env python3
"""Lightweight local web UI server for MicroKISStnc v5."""

import json
import logging
import threading
import ipaddress
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>MicroKISStnc Remote Control</title>
  <style>
    :root {
      --bg-top: #081019;
      --bg-bottom: #111a1f;
      --panel: rgba(18, 31, 37, 0.86);
      --panel-strong: #14242e;
      --line: #2c4a57;
      --text: #e4ecf0;
      --muted: #95abb5;
      --ok: #80e76a;
      --warn: #ffb266;
      --accent: #61c1ff;
      --active: #00d09f;
      --monitor-bg: #030507;
    }
    body[data-theme="light"] {
      --bg-top: #eaf5fb;
      --bg-bottom: #d9ecf7;
      --panel: rgba(250, 253, 255, 0.95);
      --panel-strong: #f2f9ff;
      --line: #8eb2c7;
      --text: #0e2230;
      --muted: #415f72;
      --ok: #1f8a3f;
      --warn: #a05b0b;
      --accent: #0b86cf;
      --active: #0e9675;
      --monitor-bg: #eef7ff;
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      background:
        radial-gradient(800px 320px at 85% -10%, rgba(0, 208, 159, 0.16), transparent 60%),
        radial-gradient(700px 360px at -10% 120%, rgba(97, 193, 255, 0.18), transparent 58%),
        linear-gradient(170deg, var(--bg-top), var(--bg-bottom));
      font-family: "Trebuchet MS", "Segoe UI", sans-serif;
    }
    .shell {
      max-width: 1260px;
      margin: 0 auto;
      padding: 18px;
    }
    .hero {
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 18px;
      background: linear-gradient(180deg, rgba(31, 51, 60, 0.86), rgba(16, 28, 34, 0.9));
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.35);
      animation: rise 450ms ease-out;
    }
    @keyframes rise {
      from {
        opacity: 0;
        transform: translateY(10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }
    .hero h1 {
      margin: 0;
      font-size: clamp(24px, 5vw, 38px);
      letter-spacing: 0.02em;
    }
    .hero-row {
      margin-top: 6px;
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      color: var(--muted);
      font-size: 13px;
    }
    .status-pill {
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid #3b6272;
      background: rgba(3, 10, 14, 0.6);
      font-family: Consolas, monospace;
    }
    .layout {
      margin-top: 14px;
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(12, minmax(0, 1fr));
    }
    .panel {
      border: 1px solid var(--line);
      border-radius: 14px;
      background: var(--panel);
      backdrop-filter: blur(2px);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.22);
      padding: 14px;
      animation: rise 500ms ease-out;
    }
    .panel h2 {
      margin: 0 0 12px 0;
      font-size: 13px;
      letter-spacing: 0.1em;
      color: #a8ccd8;
    }
    .panel-devices { grid-column: span 8; }
    .panel-ptt { grid-column: span 4; }
    .panel-monitor { grid-column: span 12; }
    .two-col {
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .field {
      margin-bottom: 10px;
    }
    label {
      display: block;
      margin-bottom: 4px;
      font-size: 11px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.07em;
    }
    select,
    input[type="text"],
    input[type="number"],
    button {
      width: 100%;
      border-radius: 8px;
      border: 1px solid #345866;
      background: #0a1419;
      color: var(--text);
      font: 600 13px Consolas, monospace;
      padding: 10px;
      transition: border-color 120ms ease, transform 90ms ease;
    }
    select:hover,
    input[type="text"]:hover,
    input[type="number"]:hover,
    button:hover {
      border-color: var(--accent);
    }
    body[data-theme="light"] select,
    body[data-theme="light"] input[type="text"],
    body[data-theme="light"] input[type="number"],
    body[data-theme="light"] button {
      background: #ffffff;
      color: #0e2230;
      border-color: #8fb2c7;
    }
    button:active {
      transform: scale(0.985);
    }
    .inline {
      display: flex;
      gap: 8px;
      align-items: center;
    }
    .inline > * { flex: 1; }
    .meter {
      height: 16px;
      border-radius: 7px;
      border: 1px solid #2f4e5a;
      background: #061015;
      overflow: hidden;
      margin-top: 4px;
    }
    .meter > span {
      display: block;
      height: 100%;
      width: 0;
      transition: width 120ms linear;
      background: linear-gradient(90deg, #4adf89 0%, #8ce364 45%, #ffb266 100%);
    }
    .meta {
      font-family: Consolas, monospace;
      font-size: 12px;
      color: #bdd0d8;
      margin-top: 3px;
    }
    .tone-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      align-items: stretch;
    }
    .tone-btn {
      min-height: 42px;
      height: 42px;
      line-height: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      white-space: nowrap;
    }
    .tone-btn.active {
      border-color: #08d891;
      background: #003f34;
      color: #b7ffe5;
    }
    .checks {
      display: flex;
      gap: 14px;
      margin: 8px 0 12px;
      flex-wrap: wrap;
    }
    .checks label {
      margin: 0;
      display: flex;
      align-items: center;
      gap: 6px;
      text-transform: none;
      letter-spacing: 0;
      font-size: 13px;
      color: var(--text);
    }
    .monitor {
      border: 1px solid #26424f;
      border-radius: 10px;
      background: var(--monitor-bg);
      color: #36f96b;
      font: 12px/1.45 Consolas, monospace;
      padding: 10px;
      min-height: 220px;
      max-height: 340px;
      white-space: pre-wrap;
      overflow-y: auto;
    }
    .legend {
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 8px;
    }
    @media (max-width: 980px) {
      .panel-devices,
      .panel-ptt,
      .panel-monitor {
        grid-column: span 12;
      }
      .two-col {
        grid-template-columns: 1fr;
      }
      .tone-grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <h1>MicroKISStnc</h1>
      <div class="hero-row">
        <div class="status-pill" id="state-backend">Backend: ...</div>
        <div class="status-pill" id="state-kiss">KISS: ...</div>
        <div class="status-pill" id="state-build">Build: ...</div>
        <div class="status-pill" id="state-web">WEB: ...</div>
        <button type="button" id="config-toggle" class="status-pill" style="cursor:pointer; width:auto; padding:4px 12px;" onclick="toggleConfigSections()">Configuration</button>
        <button type="button" id="theme-toggle" class="status-pill" style="cursor:pointer; width:auto; padding:4px 12px;" onclick="toggleTheme()">Theme: Dark</button>
      </div>
    </section>

    <main class="layout">
      <section class="panel panel-devices" id="panel-devices">
        <h2>URZADZENIA IN/OUT</h2>
        <div class="two-col">
          <div>
            <div class="field">
              <label for="input-device">🎤 Audio INPUT (Microphones)</label>
              <div class="inline">
                <select id="input-device" onchange="setInputDevice(this.value)"></select>
                <button type="button" onclick="refreshDevices()">Refresh</button>
              </div>
              <div class="meta" id="input-device-status" style="margin-top: 6px; color: #a8ccd8;">-- not selected --</div>
            </div>
            <div class="field">
              <label>Signal Level (RX)</label>
              <div class="meter"><span id="rx-meter"></span></div>
              <div class="meta" id="rx-meta">Peak: 0.0% (-96.0 dBFS) | RMS: 0.0% (-96.0 dBFS)</div>
            </div>
          </div>

          <div>
            <div class="field">
              <label for="output-device">🔊 Audio OUTPUT (Speakers)</label>
              <div class="inline">
                <select id="output-device" onchange="setOutputDevice(this.value)"></select>
                <button type="button" onclick="refreshDevices()">Refresh</button>
              </div>
              <div class="meta" id="output-device-status" style="margin-top: 6px; color: #a8ccd8;">-- not selected --</div>
            </div>
            <div class="field">
              <label>Signal Level (TX)</label>
              <div class="meter"><span id="tx-meter"></span></div>
              <div class="meta" id="tx-meta">Peak: 0.0% (-96.0 dBFS) | RMS: 0.0% (-96.0 dBFS)</div>
            </div>
            <div class="field">
              <label>Test Tones</label>
              <div class="tone-grid">
                <button class="tone-btn" id="tone-1200" type="button" onclick="toggleTone('1200')">1200 Hz</button>
                <button class="tone-btn" id="tone-both" type="button" onclick="toggleTone('both')">Both</button>
                <button class="tone-btn" id="tone-2200" type="button" onclick="toggleTone('2200')">2200 Hz</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="panel panel-ptt" id="panel-ptt">
        <h2>PTT CONTROL</h2>
        <div class="field">
          <label for="ptt-mode">PTT Type (RIG/DTR/RTS/VOX)</label>
          <select id="ptt-mode" title="Wybiera sposób kluczowania PTT: RIG/CAT, DTR, RTS lub VOX (bez sterowania linią PTT)." onchange="setPTTMode(this.value)"></select>
        </div>

        <div class="field">
          <label for="ptt-path">Port PTT (szeregowy)</label>
          <select id="ptt-path" title="Port COM do kluczowania DTR/RTS." onchange="setPTTPath(this.value)"></select>
        </div>

        <div class="checks">
          <label><input id="check-ptt-invert" type="checkbox" title="Inverts DTR/RTS keying logic: LOW=TX, HIGH=RX." onchange="setPTTInvert()"/> ptt_active_low</label>
        </div>

        <div class="field">
          <label for="civaddr">Adres CI-V</label>
          <input id="civaddr" type="text" placeholder="0x00" title="Adres CI-V radia, np. 0xA4 dla IC-705." onchange="setCivAddr(this.value)"/>
        </div>

        <div class="checks">
          <label><input id="check-rts" type="checkbox" title="Wymusza stały stan RTS=ON." onchange="setPTTPins()"/> rts_state=ON</label>
          <label><input id="check-dts" type="checkbox" title="Wymusza stały stan DTR=ON." onchange="setPTTPins()"/> dtr_state=ON</label>
        </div>

        <div class="field">
          <label for="vox-delay">VOX Delay (legacy)</label>
          <input id="vox-delay" type="number" min="0" max="5000" step="10" onchange="setVoxDelay(this.value)"/>
        </div>

        <div class="field" id="hamlib-group">
          <label>Hamlib rigctld</label>
          <div class="inline" style="margin-bottom: 8px;">
            <select id="cat-connection" title="Transport CAT dla RIG: TCP (rigctld) lub Serial (bezpośrednio COM)." onchange="setCatConnectionMode(this.value)">
              <option value="TCP">TCP connection</option>
              <option value="SERIAL">Serial connection</option>
            </select>
          </div>
          <div class="inline" id="cat-serial-group" style="margin-bottom: 8px;">
            <select id="cat-serial-port" title="Port COM do komend CAT (CI-V) w trybie Serial." onchange="setCatSerialPath(this.value)"></select>
            <input id="cat-serial-baud" type="number" min="1200" max="115200" step="1200" title="Prędkość CAT; musi zgadzać się z ustawieniem radia." onchange="setCatSerialBaud(this.value)"/>
          </div>
          <div class="inline" style="margin-bottom: 8px;">
            <input id="hamlib-host" type="text" placeholder="127.0.0.1" title="Adres hosta rigctld (TCP)." onchange="setHamlibConfig()"/>
            <input id="hamlib-port" type="number" min="1" max="65535" step="1" title="Port rigctld, zwykle 4532." onchange="setHamlibConfig()"/>
            <button type="button" title="Testuje połączenie CAT zgodnie z aktualnym trybem." onclick="testHamlib()">Test</button>
          </div>
          <div class="meta" id="hamlib-status">Hamlib: not tested</div>
        </div>

        <div class="field" style="margin-top: 10px;">
          <button type="button" id="ptt-test-btn" onclick="togglePTTTest()" style="background:#2e7d32; border-color:#1b5e20; color:#fff; font-weight:700;">PTT TEST</button>
        </div>

        <div class="field" style="margin-top: 10px;">
          <label for="allow-ip-input">allow address (toggle)</label>
          <div class="inline" style="margin-bottom: 8px;">
            <input id="allow-ip-input" type="text" placeholder="0.0.0.0 lub 192.168.1.20" onkeydown="if(event.key==='Enter'){toggleAllowIp();}"/>
            <button type="button" onclick="toggleAllowIp()">Toggle</button>
          </div>
          <select id="allow-ip-list" title="Allowed remote IP list"></select>
          <div class="meta" id="allow-ip-status" style="margin-top: 6px;">Allowed IPs: --</div>
          <div class="meta" style="margin-top: 6px;">Localhost always allowed: 127.0.0.1, ::1 | CIDR supported: 192.168.1.0/24</div>
        </div>

        <div class="legend" id="ptt-active">PTT Active: no</div>
      </section>

      <section class="panel panel-monitor">
        <h2>MONITOR - Frame Log</h2>
        <div class="legend">Live RX/TX stream from desktop app</div>
        <div class="monitor" id="monitor">-- no data --</div>
      </section>
    </main>
  </div>

  <script>
    var toneActive = '';
    var configVisible = true;

    function norm(value, fallback) {
      return value === undefined || value === null ? fallback : value;
    }

    function applyTheme(theme) {
      var t = theme === 'light' ? 'light' : 'dark';
      document.body.setAttribute('data-theme', t);
      var btn = document.getElementById('theme-toggle');
      if (btn) {
        btn.textContent = t === 'light' ? 'Theme: Light' : 'Theme: Dark';
      }
      try {
        localStorage.setItem('mkiss_theme', t);
      } catch (_e) {}
    }

    function toggleTheme() {
      var current = document.body.getAttribute('data-theme') || 'dark';
      applyTheme(current === 'dark' ? 'light' : 'dark');
    }

    function applyConfigVisibility(visible) {
      configVisible = !!visible;
      var devices = document.getElementById('panel-devices');
      var ptt = document.getElementById('panel-ptt');
      var btn = document.getElementById('config-toggle');
      if (devices) devices.style.display = configVisible ? '' : 'none';
      if (ptt) ptt.style.display = configVisible ? '' : 'none';
      if (btn) btn.textContent = configVisible ? 'Configuration' : 'Configuration OFF';
      try {
        localStorage.setItem('mkiss_config_visible', configVisible ? '1' : '0');
      } catch (_e) {}
    }

    function toggleConfigSections() {
      applyConfigVisibility(!configVisible);
    }

    (function initTheme() {
      var saved = 'dark';
      try {
        saved = localStorage.getItem('mkiss_theme') || 'dark';
      } catch (_e) {}
      applyTheme(saved);
    })();

    (function initConfigVisibility() {
      var saved = '1';
      try {
        saved = localStorage.getItem('mkiss_config_visible') || '1';
      } catch (_e) {}
      applyConfigVisibility(saved !== '0');
    })();

    async function apiCall(method, endpoint, data) {
      var opts = { method: method, cache: 'no-store' };
      if (data !== undefined && data !== null) {
        opts.headers = { 'Content-Type': 'application/json' };
        opts.body = JSON.stringify(data);
      }
      try {
        var response = await fetch(endpoint, opts);
        if (!response.ok) {
          throw new Error('HTTP ' + response.status);
        }
        return await response.json();
      } catch (err) {
        console.error('API error', endpoint, err);
        return null;
      }
    }

    function populateSelect(selectId, options, selectedValue) {
      var select = document.getElementById(selectId);
      if (!select) {
        return;
      }

      var list = Array.isArray(options) ? options.filter(Boolean) : [];
      var isObjectList = list.length > 0 && typeof list[0] === 'object';
      var normalized = isObjectList
        ? list.map(function (item) { return { value: String(item.id), label: String(item.label || item.id) }; })
        : list.map(function (item) { return { value: String(item), label: String(item) }; });

      select.dataset.idBased = isObjectList ? 'true' : 'false';

      var existing = Array.from(select.options).map(function (o) { return o.value + '|' + o.textContent; });
      var incoming = normalized.map(function (o) { return o.value + '|' + o.label; });
      var changed = incoming.length !== existing.length || incoming.some(function (v, i) { return v !== existing[i]; });
      if (changed) {
        select.innerHTML = normalized.map(function (o) {
          return '<option value="' + o.value + '">' + o.label + '</option>';
        }).join('');
      }

      var selected = selectedValue !== undefined && selectedValue !== null ? String(selectedValue) : '';
      if (selected) {
        var found = false;
        for (var i = 0; i < select.options.length; i++) {
          if (select.options[i].value === selected) {
            select.value = selected;
            found = true;
            break;
          }
        }
        if (!found && isObjectList) {
          for (var j = 0; j < select.options.length; j++) {
            if (select.options[j].textContent.trim() === selected.trim()) {
              select.value = select.options[j].value;
              found = true;
              break;
            }
          }
        }
      }
    }

    function setMeter(id, metaId, peakPct, peakDbfs, rmsPct, rmsDbfs) {
      var peakValue = Number(norm(peakPct, 0));
      var rmsValue = Number(norm(rmsPct, 0));
      var peakClamped = Math.max(0, Math.min(100, peakValue));
      var rmsClamped = Math.max(0, Math.min(100, rmsValue));
      var peakDb = Number.isFinite(peakDbfs) ? peakDbfs : -96;
      var rmsDb = Number.isFinite(rmsDbfs) ? rmsDbfs : -96;

      document.getElementById(id).style.width = peakClamped.toFixed(1) + '%';
      document.getElementById(metaId).textContent =
        'Peak: ' + peakClamped.toFixed(1) + '% (' + peakDb.toFixed(1) + ' dBFS) | RMS: ' +
        rmsClamped.toFixed(1) + '% (' + rmsDb.toFixed(1) + ' dBFS)';
    }

    async function refresh() {
      var state = await apiCall('GET', '/api/state');
      if (!state) {
        document.getElementById('state-backend').textContent = 'Backend: offline';
        return;
      }

      document.getElementById('state-backend').textContent = 'Backend: running';
      document.getElementById('state-kiss').textContent = 'KISS: ' + norm(state.kiss_listen, '-');
      document.getElementById('state-build').textContent = 'Build: ' + norm(state.build, '-');
      document.getElementById('state-web').textContent = 'WEB: ' + norm(state.web_listen, location.host);

      var inputSel = state.input_device_id !== undefined && state.input_device_id !== null ? state.input_device_id : state.input_device;
      var outputSel = state.output_device_id !== undefined && state.output_device_id !== null ? state.output_device_id : state.output_device;
      populateSelect('input-device', norm(state.input_devices, []), norm(inputSel, ''));
      populateSelect('output-device', norm(state.output_devices, []), norm(outputSel, ''));
      populateSelect('ptt-mode', norm(state.ptt_modes, ['RIG', 'DTR', 'RTS', 'VOX']), norm(state.ptt_type || state.ptt_mode, 'VOX'));
      populateSelect('ptt-path', norm(state.ptt_paths, []).map(String), String(norm(state.ptt_path, '')));
      populateSelect('allow-ip-list', norm(state.allowed_ips, []).map(String), '');

      var inputDeviceSelect = document.getElementById('input-device');
      var outputDeviceSelect = document.getElementById('output-device');
      var inputLabel = inputDeviceSelect.value && inputDeviceSelect.options[inputDeviceSelect.selectedIndex]
        ? inputDeviceSelect.options[inputDeviceSelect.selectedIndex].textContent
        : '-- not selected --';
      var outputLabel = outputDeviceSelect.value && outputDeviceSelect.options[outputDeviceSelect.selectedIndex]
        ? outputDeviceSelect.options[outputDeviceSelect.selectedIndex].textContent
        : '-- not selected --';
      document.getElementById('input-device-status').textContent = '✓ ' + inputLabel;
      document.getElementById('output-device-status').textContent = '✓ ' + outputLabel;

      setMeter('rx-meter', 'rx-meta', state.rx_peak_pct, state.rx_peak_dbfs, state.rx_rms_pct, state.rx_rms_dbfs);
      setMeter('tx-meter', 'tx-meta', state.tx_peak_pct, state.tx_peak_dbfs, state.tx_rms_pct, state.tx_rms_dbfs);

      var monitorLines = Array.isArray(state.monitor_lines) ? state.monitor_lines : [];
      document.getElementById('monitor').textContent = monitorLines.length > 0
        ? monitorLines.join('\\n')
        : norm(state.last_monitor_line, '-- no data --');

      document.getElementById('check-rts').checked = !!state.use_rts;
      document.getElementById('check-dts').checked = !!state.use_dts;
      document.getElementById('check-ptt-invert').checked = !!state.ptt_active_low;
      document.getElementById('civaddr').value = String(norm(state.civaddr, '0x00'));

      var vox = document.getElementById('vox-delay');
      var voxValue = Number(norm(state.vox_delay_ms, 0));
      if (Number(vox.value) !== voxValue) {
        vox.value = String(voxValue);
      }

      document.getElementById('ptt-active').textContent = 'PTT Active: ' + (state.ptt_active ? 'yes' : 'no');
      var allowedIps = Array.isArray(state.allowed_ips) ? state.allowed_ips : [];
      document.getElementById('allow-ip-status').textContent = 'Allowed IPs: ' + (allowedIps.length ? allowedIps.join(', ') : '--');

      var pttType = String(norm(state.ptt_type || state.ptt_mode, 'VOX')).toUpperCase();
      var isSerial = pttType === 'DTR' || pttType === 'RTS';
      var isHamlib = pttType === 'RIG';
      var rigConnection = String(norm(state.rig_connection, 'TCP')).toUpperCase();
      var isCatSerial = isHamlib && rigConnection === 'SERIAL';
      var isCatTcp = isHamlib && rigConnection === 'TCP';

      document.getElementById('check-rts').disabled = !isSerial;
      document.getElementById('check-dts').disabled = !isSerial;
      document.getElementById('ptt-path').disabled = !isSerial;
      document.getElementById('check-ptt-invert').disabled = !isSerial;
      document.getElementById('vox-delay').disabled = true;
      document.getElementById('cat-connection').disabled = !isHamlib;
      document.getElementById('hamlib-host').disabled = !isCatTcp;
      document.getElementById('hamlib-port').disabled = !isCatTcp;
      document.getElementById('hamlib-group').style.opacity = isHamlib ? '1' : '0.55';
      var pttBtnEl = document.getElementById('ptt-test-btn');
      if (pttBtnEl) {
        pttBtnEl.disabled = pttType === 'VOX';
      }

      populateSelect('cat-serial-port', norm(state.ptt_paths, []).map(String), String(norm(state.cat_serial_port, '')));
      document.getElementById('cat-connection').value = rigConnection;
      document.getElementById('cat-serial-port').disabled = !isCatSerial;
      document.getElementById('cat-serial-baud').disabled = !isCatSerial;
      document.getElementById('cat-serial-group').style.opacity = isCatSerial ? '1' : '0.55';

      var catBaudEl = document.getElementById('cat-serial-baud');
      var catBaud = Number(norm(state.cat_serial_baud, 19200));
      if (Number(catBaudEl.value) !== catBaud) {
        catBaudEl.value = String(catBaud);
      }

      var host = String(norm(state.hamlib_host, '127.0.0.1'));
      var port = Number(norm(state.hamlib_port, 4532));
      var hostEl = document.getElementById('hamlib-host');
      var portEl = document.getElementById('hamlib-port');
      if (hostEl.value !== host) hostEl.value = host;
      if (Number(portEl.value) !== port) portEl.value = String(port);

      toneActive = norm(state.tone_active, '');
      ['1200', 'both', '2200'].forEach(function (tone) {
        var btn = document.getElementById('tone-' + tone);
        if (btn) {
          btn.classList.toggle('active', toneActive === tone);
        }
      });

      var pttBtn = document.getElementById('ptt-test-btn');
      if (pttBtn) {
        var pttOn = !!state.ptt_active;
        pttBtn.dataset.active = pttOn ? '1' : '0';
        pttBtn.style.background = pttOn ? '#b71c1c' : '#2e7d32';
        pttBtn.style.borderColor = pttOn ? '#7f0000' : '#1b5e20';
      }
    }

    async function setInputDevice(value) {
      var select = document.getElementById('input-device');
      var payload = select.dataset.idBased === 'true'
        ? { device_id: Number(value) }
        : { device: value };
      await apiCall('POST', '/api/control/input-device', payload);
      await refresh();
    }

    async function setOutputDevice(value) {
      var select = document.getElementById('output-device');
      var payload = select.dataset.idBased === 'true'
        ? { device_id: Number(value) }
        : { device: value };
      await apiCall('POST', '/api/control/output-device', payload);
      await refresh();
    }

    async function setPTTMode(value) {
      await apiCall('POST', '/api/control/ptt-mode', { mode: value });
      await refresh();
    }

    async function setPTTPath(value) {
      if (!value) return;
      await apiCall('POST', '/api/control/ptt-path', { path: value });
      await refresh();
    }

    async function setPTTInvert() {
      await apiCall('POST', '/api/control/ptt-invert', {
        active_low: document.getElementById('check-ptt-invert').checked
      });
    }

    async function togglePTTTest() {
      var btn = document.getElementById('ptt-test-btn');
      var active = !!(btn && btn.dataset.active === '1');
      await apiCall('POST', '/api/control/ptt-test', { active: !active });
      await refresh();
    }

    async function setCivAddr(value) {
      var civaddr = String(value || '').trim();
      if (!civaddr) return;
      await apiCall('POST', '/api/control/civaddr', { civaddr: civaddr });
    }

    async function setPTTPins() {
      var isDisabled = document.getElementById('check-rts').disabled && document.getElementById('check-dts').disabled;
      if (isDisabled) return;
      await apiCall('POST', '/api/control/ptt-pins', {
        rts: document.getElementById('check-rts').checked,
        dts: document.getElementById('check-dts').checked
      });
    }

    async function setVoxDelay(value) {
      if (document.getElementById('vox-delay').disabled) return;
      await apiCall('POST', '/api/control/vox-delay', { delay_ms: Number(value) });
      await refresh();
    }

    async function setHamlibConfig(doTest) {
      var host = document.getElementById('hamlib-host').value || '127.0.0.1';
      var port = Number(document.getElementById('hamlib-port').value || 4532);
      var result = await apiCall('POST', '/api/control/hamlib-config', {
        host: host,
        port: port,
        test: !!doTest
      });
      var status = document.getElementById('hamlib-status');
      if (!result || result.ok === false) {
        status.textContent = 'Hamlib: offline';
        return;
      }
      status.textContent = doTest ? 'Hamlib: OK' : ('Hamlib: ' + host + ':' + port);
      if (doTest) {
        await refresh();
      }
    }

    async function setCatConnection(mode, test) {
      var modeValue = String(mode || document.getElementById('cat-connection').value || 'TCP').toUpperCase();
      var path = document.getElementById('cat-serial-port').value || '';
      var baud = Number(document.getElementById('cat-serial-baud').value || 19200);
      var result = await apiCall('POST', '/api/control/cat-connection', {
        mode: modeValue,
        path: path,
        baud: baud,
        test: !!test
      });
      var status = document.getElementById('hamlib-status');
      if (!result || result.ok === false) {
        status.textContent = modeValue === 'SERIAL' ? 'CAT serial: offline' : 'Hamlib TCP: offline';
      } else if (test) {
        status.textContent = modeValue === 'SERIAL'
          ? ('CAT serial: ' + (path || '-') + ' @ ' + baud)
          : 'Hamlib TCP: OK';
      }
      await refresh();
    }

    async function setCatConnectionMode(mode) {
      await setCatConnection(mode, false);
    }

    async function setCatSerialPath(value) {
      if (!value) return;
      await setCatConnection(null, false);
    }

    async function setCatSerialBaud(_value) {
      await setCatConnection(null, false);
    }

    async function testHamlib() {
      var mode = String(document.getElementById('cat-connection').value || 'TCP').toUpperCase();
      if (mode === 'SERIAL') {
        await setCatConnection(mode, true);
        return;
      }
      await setHamlibConfig(true);
    }

    async function refreshDevices() {
      await apiCall('POST', '/api/control/refresh-devices', {});
      await refresh();
    }

    async function toggleAllowIp() {
      var input = document.getElementById('allow-ip-input');
      var ip = String(input.value || '').trim();
      if (!ip) return;
      await apiCall('POST', '/api/control/allow-ip-toggle', { ip: ip });
      input.value = '';
      await refresh();
    }

    async function toggleTone(tone) {
      var payload = toneActive === tone ? 'stop' : tone;
      await apiCall('POST', '/api/control/tone', { tone: payload });
      await refresh();
    }

    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>
"""

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>MicroKISStnc Remote Control</title>
  <style>
    :root {
      --bg: #e8eef3;
      --panel: #ffffff;
      --panel-soft: #f4f7fa;
      --line: #c8d3dc;
      --text: #22313c;
      --muted: #5b7080;
      --accent: #2f83bd;
      --accent-soft: #dceaf7;
      --accent-strong: #0b4d7a;
      --monitor-bg: #07130d;
      --monitor-text: #38e36e;
      --shadow: 0 8px 22px rgba(20, 42, 60, 0.14);
      --radius: 14px;
      --control-radius: 8px;
    }
    * { box-sizing: border-box; }
    html, body { min-height: 100%; }
    body {
      margin: 0;
      color: var(--text);
      background:
        radial-gradient(900px 260px at 100% -10%, rgba(47, 131, 189, 0.13), transparent 55%),
        radial-gradient(700px 260px at 0% 100%, rgba(47, 141, 79, 0.08), transparent 56%),
        linear-gradient(180deg, #f3f7fb 0%, var(--bg) 100%);
      font-family: "Segoe UI", Tahoma, Arial, sans-serif;
    }
    a { color: var(--accent); }
    .shell { max-width: 1360px; margin: 0 auto; padding: 16px; }
    .hero {
      background: linear-gradient(180deg, #ffffff 0%, #f6f9fc 100%);
      border: 1px solid var(--line);
      border-radius: 18px;
      box-shadow: var(--shadow);
      padding: 18px 18px 16px;
      animation: rise 300ms ease-out;
    }
    @keyframes rise { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
    .hero-top { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; flex-wrap: wrap; }
    .eyebrow { margin: 0 0 4px; color: var(--muted); font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; }
    .hero h1 { margin: 0; font-size: clamp(26px, 5vw, 38px); line-height: 1.05; color: var(--accent-strong); }
    .hero-subtitle { margin: 6px 0 0; color: var(--muted); font-size: 14px; max-width: 760px; }
    .language-box {
      width: fit-content;
      min-width: 0;
      align-self: flex-start;
    }
    .language-box select {
      width: auto;
      min-width: 92px;
    }
    .status-pill {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 5px 11px; border-radius: 999px; border: 1px solid var(--line);
      background: #f8fbfe; color: var(--muted); font: 600 12px "Consolas", "Courier New", monospace; white-space: nowrap;
    }
    .tab-row { margin-top: 14px; display: flex; flex-wrap: wrap; gap: 8px; border-top: 1px solid #e1e8ee; padding-top: 14px; }
    .tab-btn {
      width: auto;
      flex: 0 0 auto;
      min-width: 130px;
      appearance: none; border: 1px solid var(--line); border-bottom: 3px solid transparent;
      background: #f2f4f6; color: #354b59; border-radius: 10px 10px 8px 8px;
      padding: 10px 16px; font: 600 13px "Segoe UI", sans-serif; cursor: pointer;
      transition: background 120ms ease, border-color 120ms ease, transform 90ms ease, color 120ms ease;
    }
    .tab-btn:hover { border-color: #b7c8d6; background: #e8eef3; }
    .tab-btn.active { background: var(--accent-soft); color: var(--accent-strong); border-bottom-color: var(--accent); transform: translateY(-1px); }
    .views { margin-top: 16px; }
    .view { display: none; gap: 16px; animation: rise 280ms ease-out; }
    .view.active { display: grid; }
    .grid-monitor, .grid-config, .grid-about { grid-template-columns: repeat(12, minmax(0, 1fr)); }
    .card {
      background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow);
      padding: 16px; min-width: 0;
    }
    .card-title {
      margin: 0 0 12px; color: var(--accent-strong); font-size: 13px; letter-spacing: 0.10em; text-transform: uppercase;
      display: flex; align-items: center; justify-content: space-between; gap: 12px;
    }
    .card-title span:last-child { color: var(--muted); text-transform: none; letter-spacing: 0; font-size: 12px; }
    .card-monitor { grid-column: span 12; }
    .card-audio { grid-column: span 7; }
    .card-ptt { grid-column: span 5; }
    .card-network { grid-column: span 6; }
    .card-web { grid-column: span 6; }
    .card-about { grid-column: span 12; }
    .two-col { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
    .stack { display: grid; gap: 12px; }
    .field { margin-bottom: 12px; }
    label {
      display: block; margin-bottom: 6px; font-size: 11px; color: var(--muted);
      text-transform: uppercase; letter-spacing: 0.08em;
    }
    select, input[type="text"], input[type="number"], button {
      width: 100%; border-radius: var(--control-radius); border: 1px solid #b7c8d6; background: #ffffff;
      color: var(--text); font: 600 13px "Segoe UI", sans-serif; padding: 10px 11px; min-height: 40px;
      transition: border-color 120ms ease, background 120ms ease, transform 90ms ease, box-shadow 120ms ease;
    }
    select:hover, input[type="text"]:hover, input[type="number"]:hover, button:hover { border-color: var(--accent); }
    select:focus, input[type="text"]:focus, input[type="number"]:focus, button:focus { outline: none; box-shadow: 0 0 0 3px rgba(47, 131, 189, 0.14); }
    button { cursor: pointer; }
    button:active { transform: translateY(1px); }
    .inline { display: flex; align-items: center; gap: 8px; }
    .inline > * { flex: 1; min-width: 0; }
    .mini-button { flex: 0 0 auto; width: auto; min-width: 96px; padding-inline: 14px; }
    .split-actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .split-actions > * { flex: 1 1 130px; }
    .meter { margin-top: 4px; height: 16px; border-radius: 8px; border: 1px solid #b7c8d6; background: #eef3f7; overflow: hidden; }
    .meter > span { display: block; width: 0; height: 100%; border-radius: 8px; background: linear-gradient(90deg, #7ac77d 0%, #4eb36e 56%, #d7a33a 100%); transition: width 120ms linear; }
    .meta { margin-top: 6px; color: var(--muted); font: 12px "Consolas", "Courier New", monospace; word-break: break-word; }
    .subtle { color: var(--muted); font-size: 12px; }
    .tone-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
    .tone-btn { min-height: 42px; display: flex; align-items: center; justify-content: center; text-align: center; }
    .tone-btn.active { background: var(--accent-soft); border-color: var(--accent); color: var(--accent-strong); }
    .checks { display: flex; flex-wrap: wrap; gap: 14px; margin: 8px 0 12px; }
    .checks label { margin: 0; display: flex; align-items: center; gap: 6px; color: var(--text); text-transform: none; letter-spacing: 0; font-size: 13px; }
    .checks input { width: auto; min-height: 0; }
    .monitor {
      border: 1px solid #b7c8d6; border-radius: 10px; background: var(--monitor-bg); color: var(--monitor-text);
      font: 12px/1.45 "Consolas", "Courier New", monospace; padding: 12px; min-height: 250px; max-height: 380px;
      white-space: pre-wrap; overflow-y: auto;
    }
    .monitor-header { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; flex-wrap: wrap; margin-bottom: 8px; }
    .monitor-summary { display: none; }
    .summary-box { border: 1px solid var(--line); border-radius: 12px; background: var(--panel-soft); padding: 12px; min-width: 0; }
    .summary-box h3 { margin: 0 0 6px; font-size: 12px; color: var(--accent-strong); text-transform: uppercase; letter-spacing: 0.08em; }
    .summary-box p { margin: 0; font-size: 13px; line-height: 1.45; color: var(--text); word-break: break-word; }
    .about-grid { display: grid; gap: 12px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .info-list { display: grid; gap: 8px; }
    .info-item { display: flex; justify-content: space-between; gap: 12px; border: 1px solid var(--line); background: var(--panel-soft); border-radius: 10px; padding: 10px 12px; font-size: 13px; }
    .info-item span:first-child { color: var(--muted); }
    .info-item span:last-child { color: var(--text); text-align: right; word-break: break-word; }
    @media (max-width: 1080px) {
      .card-audio, .card-ptt, .card-network, .card-web { grid-column: span 12; }
      .monitor-summary, .about-grid, .two-col { grid-template-columns: 1fr; }
    }
    @media (max-width: 720px) {
      .shell { padding: 12px; }
      .hero { padding: 14px; }
      .tab-row { gap: 6px; }
      .tab-btn { flex: 1 1 160px; }
      .inline { flex-direction: column; align-items: stretch; }
      .mini-button { width: 100%; }
      .tone-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header class="hero">
      <div class="hero-top">
        <div>
          <p class="eyebrow" id="hero-eyebrow">APRS TNC remote control</p>
          <h1>MicroKISStnc</h1>
          <p class="hero-subtitle" id="hero-subtitle">Web interface aligned with the desktop layout: status summary, configuration cards, and live monitor view.</p>
        </div>
        <div class="stack language-box">
          <label for="ui-language" id="language-label" style="margin-bottom: 6px;">Language</label>
          <select id="ui-language" onchange="setUiLanguage(this.value)"></select>
        </div>
      </div>
      <nav class="tab-row" aria-label="Sections">
        <button type="button" class="tab-btn active" id="tab-monitor" data-tab="monitor" onclick="setView('monitor')">Monitor</button>
        <button type="button" class="tab-btn" id="tab-config" data-tab="config" onclick="setView('config')">Configuration</button>
        <button type="button" class="tab-btn" id="tab-about" data-tab="about" onclick="setView('about')">About</button>
      </nav>
    </header>

    <main class="views">
      <section class="view active grid-monitor" id="view-monitor">
        <article class="card card-monitor">
          <div class="monitor-header">
            <div>
              <h2 class="card-title"><span id="monitor-title">Monitor</span><span></span></h2>
            </div>
          </div>
          <div class="monitor" id="monitor">-- no data --</div>
        </article>
      </section>

      <section class="view grid-config" id="view-config">
        <article class="card card-audio">
          <h2 class="card-title"><span id="audio-card-title">Devices IN/OUT</span><span id="audio-card-subtitle">Audio inputs, outputs, and test tones</span></h2>
          <div class="stack">
            <div class="field">
              <label for="input-device" id="input-device-label">Audio input</label>
              <div class="inline">
                <select id="input-device" onchange="setInputDevice(this.value)"></select>
                <button type="button" class="mini-button" id="refresh-input-btn" onclick="refreshDevices()">Refresh</button>
              </div>
              <div class="meta" id="input-device-status">Selected: --</div>
            </div>
            <div class="field">
              <label id="input-level-label">Input level</label>
              <div class="meter"><span id="rx-meter-card"></span></div>
            </div>
            <div class="field">
              <label for="output-device" id="output-device-label">Audio output</label>
              <div class="inline">
                <select id="output-device" onchange="setOutputDevice(this.value)"></select>
                <button type="button" class="mini-button" id="refresh-output-btn" onclick="refreshDevices()">Refresh</button>
              </div>
              <div class="meta" id="output-device-status">Selected: --</div>
            </div>
            <div class="field">
              <label id="output-level-label">Output level</label>
              <div class="meter"><span id="tx-meter-card"></span></div>
            </div>
            <div class="field">
              <label id="test-tones-label">Test tones</label>
              <div class="tone-grid">
                <button class="tone-btn" id="tone-1200" type="button" onclick="toggleTone('1200')">1200 Hz</button>
                <button class="tone-btn" id="tone-both" type="button" onclick="toggleTone('both')">Both</button>
                <button class="tone-btn" id="tone-2200" type="button" onclick="toggleTone('2200')">2200 Hz</button>
              </div>
            </div>
          </div>
        </article>

        <article class="card card-ptt">
          <h2 class="card-title"><span id="ptt-card-title">PTT control</span><span id="ptt-card-subtitle">Desktop PTT settings</span></h2>
          <div class="stack">
            <div class="field">
              <label for="ptt-mode" id="ptt-type-label">PTT type</label>
              <select id="ptt-mode" onchange="setPTTMode(this.value)"></select>
            </div>
            <div class="field">
              <label for="ptt-path" id="ptt-port-label">PTT port</label>
              <select id="ptt-path" onchange="setPTTPath(this.value)"></select>
            </div>
            <div class="checks">
              <label><input id="check-ptt-invert" type="checkbox" onchange="setPTTInvert()"/> <span id="ptt-active-low-label">PTT active low</span></label>
              <label><input id="check-rts" type="checkbox" onchange="setPTTPins()"/> <span id="rts-on-label">RTS state ON</span></label>
              <label><input id="check-dts" type="checkbox" onchange="setPTTPins()"/> <span id="dts-on-label">DTR state ON</span></label>
            </div>
            <div class="field">
              <label for="civaddr" id="civaddr-label">CI-V address</label>
              <input id="civaddr" type="text" placeholder="0x00" onchange="setCivAddr(this.value)"/>
            </div>
            <div class="field">
              <label for="tx-delay" id="tx-delay-label">TX delay</label>
              <input id="tx-delay" type="number" min="0" max="5000" step="10" onchange="setTxDelay(this.value)"/>
              <div class="subtle" id="tx-delay-hint">Mapped to the same timing control used by the desktop app.</div>
            </div>
            <div class="field">
              <label for="tx-tail" id="tx-tail-label">TX tail</label>
              <input id="tx-tail" type="number" min="0" max="5000" step="10" onchange="setTxTail(this.value)"/>
            </div>
            <div class="field" id="hamlib-group">
              <label id="hamlib-group-label">RIG / CAT control</label>
              <div class="split-actions">
                <select id="cat-connection" onchange="setCatConnectionMode(this.value)">
                  <option value="TCP" id="tcp-connection-option">TCP connection</option>
                  <option value="SERIAL" id="serial-connection-option">Serial connection</option>
                </select>
              </div>
              <div class="inline" id="cat-serial-group" style="margin-top: 8px;">
                <select id="cat-serial-port" onchange="setCatSerialPath(this.value)"></select>
                <input id="cat-serial-baud" type="number" min="1200" max="115200" step="1200" onchange="setCatSerialBaud(this.value)"/>
              </div>
              <div class="inline" style="margin-top: 8px;">
                <input id="hamlib-host" type="text" placeholder="127.0.0.1" onchange="setHamlibConfig()"/>
                <input id="hamlib-port" type="number" min="1" max="65535" step="1" onchange="setHamlibConfig()"/>
              </div>
              <div class="inline" style="margin-top: 8px;">
                <button type="button" id="hamlib-test-btn" onclick="testHamlib()">Test</button>
              </div>
              <div class="meta" id="hamlib-status">Hamlib: not tested</div>
            </div>
            <div class="field">
              <button type="button" id="ptt-test-btn" onclick="togglePTTTest()" style="background:#2f8d4f; border-color:#1f6c39; color:#fff; font-weight:700;">PTT TEST</button>
            </div>
          </div>
        </article>

        <article class="card card-network">
          <h2 class="card-title"><span id="kiss-network-title">KISS port</span><span id="kiss-network-subtitle">TCP and allowlist</span></h2>
          <div class="stack">
            <div class="info-list">
              <div class="info-item"><span id="kiss-port-info-label">KISS port</span><span id="kiss-port-info">--</span></div>
              <div class="info-item"><span id="listen-label">Listen</span><span id="kiss-listen-info">--</span></div>
            </div>
            <div class="field">
              <label for="kiss-port" id="kiss-port-label">KISS port</label>
              <div class="inline">
                <input id="kiss-port" type="number" min="1" max="65535" step="1" onchange="setKissPort(this.value)"/>
                <button type="button" class="mini-button" id="refresh-kiss-btn" onclick="refreshKissPort()">Refresh</button>
              </div>
            </div>
            <div class="field">
              <label for="allow-ip-input" id="allowed-addresses-label">Allowed addresses</label>
              <div class="inline">
                <input id="allow-ip-input" type="text" placeholder="0.0.0.0 or 192.168.1.20" onkeydown="if(event.key==='Enter'){toggleAllowIp();}"/>
                <button type="button" class="mini-button" id="toggle-allow-btn" onclick="toggleAllowIp()">Toggle</button>
              </div>
              <select id="allow-ip-list" style="margin-top: 8px;"></select>
              <div class="meta" id="allow-ip-status">Allowed IPs: --</div>
              <div class="subtle">Localhost is always allowed. CIDR ranges are supported.</div>
            </div>
          </div>
        </article>

      </section>

      <section class="view grid-about" id="view-about">
        <article class="card card-about">
          <h2 class="card-title"><span id="about-title">About application</span><span id="about-subtitle">Application details</span></h2>
          <div class="about-grid">
            <div class="summary-box">
              <h3 id="about-summary-title">MicroKISStnc</h3>
              <p id="about-summary-text">Desktop and web interfaces share the same backend state. The web page is styled to follow the desktop GUI language: light panels, blue accents, grouped controls, and a clear monitor surface.</p>
            </div>
            <div class="info-list">
              <div class="info-item"><span id="about-build-label">Build</span><span id="about-build">--</span></div>
              <div class="info-item"><span id="about-kiss-label">KISS server</span><span id="about-kiss">--</span></div>
              <div class="info-item"><span id="about-web-label">Web UI</span><span id="about-web">--</span></div>
              <div class="info-item"><span id="about-backend-label">Backend</span><span id="about-backend">--</span></div>
            </div>
          </div>
        </article>
      </section>
    </main>
  </div>

  <script>
    var toneActive = '';
    var currentLang = 'en';
    var LANGUAGE_OPTIONS = [
      { value: 'en', label: 'EN' },
      { value: 'de', label: 'DE' },
      { value: 'fr', label: 'FR' },
      { value: 'es', label: 'ES' },
      { value: 'pl', label: 'PL' }
    ];
    var I18N = {
      en: {
        hero_eyebrow: 'APRS TNC remote control',
        hero_subtitle: 'Web interface aligned with the desktop layout: status summary, configuration cards, and live monitor view.',
        language: 'Language',
        monitor: 'Monitor',
        configuration: 'Configuration',
        about: 'About',
        monitor_title: 'Monitor',
        audio_card_title: 'DEVICES IN/OUT',
        audio_card_subtitle: 'Audio inputs, outputs, and test tones',
        ptt_card_title: 'PTT CONTROL',
        ptt_card_subtitle: 'Desktop PTT settings',
        network_card_title: 'KISS port',
        network_card_subtitle: 'TCP and allowlist',
        about_title: 'About application',
        about_subtitle: 'Application details',
        input_device: 'Audio INPUT (Microphones):',
        output_device: 'Audio OUTPUT (Speakers):',
        input_level: 'Signal Level:',
        output_level: 'Signal Level:',
        test_tones: 'Test Tones:',
        ptt_type: 'PTT Type:',
        ptt_port: 'PTT serial port:',
        ptt_active_low: 'PTT active low',
        rts_on: 'RTS forced ON',
        dts_on: 'DTR forced ON',
        civaddr: 'CI-V address:',
        tx_delay: 'TX Delay (ms):',
        tx_tail: 'TX Tail (ms):',
        tx_delay_hint: 'Mapped to the same timing control used by the desktop app.',
        rig_cat_control: 'RIG / CAT Control',
        tcp_connection: 'TCP connection',
        serial_connection: 'Serial connection',
        hamlib_host: 'Hamlib Host:',
        port: 'Port:',
        test: 'Test',
        ptt_test: 'PTT TEST',
        kiss_port: 'KISS port',
        listen: 'Listen',
        allowed_addresses: 'Allowed addresses',
        allowed_placeholder: '0.0.0.0, 192.168.1.20 or 192.168.1.0/24',
        toggle: 'Add/Remove',
        localhost_hint: 'Localhost always allowed: 127.0.0.1, ::1 | You can add a single IP or CIDR network (e.g. 192.168.1.0/24)',
        build: 'Build',
        kiss_server: 'KISS server',
        web_ui: 'Web UI',
        backend: 'Backend',
        selected_prefix: 'Selected: ',
        not_selected: '-- not selected --',
        backend_running: 'running',
        backend_offline: 'offline',
        hamlib_not_tested: 'Hamlib: not tested',
        hamlib_offline: 'Hamlib: offline',
        hamlib_ok: 'Hamlib: OK',
        cat_serial_offline: 'CAT serial: offline',
        hamlib_tcp_offline: 'Hamlib TCP: offline',
        cat_serial_prefix: 'CAT serial: ',
        hamlib_tcp_ok: 'Hamlib TCP: OK',
        no_data: '-- no data --',
        about_summary: 'Desktop and web interfaces share the same backend state. The web page is styled to follow the desktop GUI language: light panels, blue accents, grouped controls, and a clear monitor surface.'
      },
      de: {
        hero_eyebrow: 'APRS TNC Fernsteuerung',
        hero_subtitle: 'Weboberfläche im gleichen Layout wie die Desktop-App: Status, Konfigurationskarten und Monitor.',
        language: 'Sprache',
        monitor: 'Monitor',
        configuration: 'Konfiguration',
        about: 'Info',
        monitor_title: 'Monitor',
        audio_card_title: 'GERÄTE IN/OUT',
        audio_card_subtitle: 'Audio-Eingänge, -Ausgänge und Testtöne',
        ptt_card_title: 'PTT-STEUERUNG',
        ptt_card_subtitle: 'PTT-Einstellungen der Desktop-App',
        network_card_title: 'KISS-Port',
        network_card_subtitle: 'TCP und Allowlist',
        about_title: 'Informationen zur Anwendung',
        about_subtitle: 'Anwendungsdetails',
        input_device: 'Audio INPUT (Mikrofone):',
        output_device: 'Audio OUTPUT (Lautsprecher):',
        input_level: 'Signalpegel:',
        output_level: 'Signalpegel:',
        test_tones: 'Testtöne:',
        ptt_type: 'PTT-Typ:',
        ptt_port: 'PTT-Seriellport:',
        ptt_active_low: 'PTT aktiv low',
        rts_on: 'RTS fest EIN',
        dts_on: 'DTR fest EIN',
        civaddr: 'CI-V-Adresse:',
        tx_delay: 'TX Delay (ms):',
        tx_tail: 'TX Tail (ms):',
        tx_delay_hint: 'Entspricht derselben Zeitsteuerung wie in der Desktop-App.',
        rig_cat_control: 'RIG / CAT Steuerung',
        tcp_connection: 'TCP-Verbindung',
        serial_connection: 'Serielle Verbindung',
        hamlib_host: 'Hamlib Host:',
        port: 'Port:',
        test: 'Test',
        ptt_test: 'PTT TEST',
        kiss_port: 'KISS-Port',
        listen: 'Lauschen',
        allowed_addresses: 'Erlaubte Adressen',
        allowed_placeholder: '0.0.0.0, 192.168.1.20 oder 192.168.1.0/24',
        toggle: 'Hinzufügen/Entfernen',
        localhost_hint: 'Localhost ist immer erlaubt: 127.0.0.1, ::1 | Sie können eine einzelne IP oder ein CIDR-Netz hinzufügen (z. B. 192.168.1.0/24)',
        build: 'Build',
        kiss_server: 'KISS-Server',
        web_ui: 'Web UI',
        backend: 'Backend',
        selected_prefix: 'Ausgewählt: ',
        not_selected: '-- nicht ausgewählt --',
        backend_running: 'läuft',
        backend_offline: 'offline',
        hamlib_not_tested: 'Hamlib: nicht getestet',
        hamlib_offline: 'Hamlib: offline',
        hamlib_ok: 'Hamlib: OK',
        cat_serial_offline: 'CAT seriell: offline',
        hamlib_tcp_offline: 'Hamlib TCP: offline',
        cat_serial_prefix: 'CAT seriell: ',
        hamlib_tcp_ok: 'Hamlib TCP: OK',
        no_data: '-- keine Daten --',
        about_summary: 'Desktop- und Web-Oberfläche nutzen denselben Backend-Status. Das Web folgt der Desktop-Optik mit hellen Karten, blauen Akzenten, Gruppen und einem klaren Monitorbereich.'
      },
      fr: {
        hero_eyebrow: 'Commande distante APRS TNC',
        hero_subtitle: "Interface web alignée sur la disposition du bureau : état, cartes de configuration et moniteur.",
        language: 'Langue',
        monitor: 'Moniteur',
        configuration: 'Configuration',
        about: 'A propos',
        monitor_title: 'Moniteur',
        audio_card_title: 'PÉRIPHÉRIQUES IN/OUT',
        audio_card_subtitle: 'Entrées/sorties audio et tonalités de test',
        ptt_card_title: 'CONTRÔLE PTT',
        ptt_card_subtitle: 'Réglages PTT du bureau',
        network_card_title: 'Port KISS',
        network_card_subtitle: 'TCP et liste autorisée',
        about_title: "Informations sur l'application",
        about_subtitle: "Détails de l'application",
        input_device: 'Audio INPUT (Microphones) :',
        output_device: 'Audio OUTPUT (Haut-parleurs) :',
        input_level: 'Niveau du signal :',
        output_level: 'Niveau du signal :',
        test_tones: 'Tonalités de test :',
        ptt_type: 'Type PTT :',
        ptt_port: 'Port série PTT :',
        ptt_active_low: 'PTT actif bas',
        rts_on: 'RTS forcé ON',
        dts_on: 'DTR forcé ON',
        civaddr: 'Adresse CI-V :',
        tx_delay: 'Délai TX (ms) :',
        tx_tail: 'Queue TX (ms) :',
        tx_delay_hint: "Même contrôle de temporisation que l'application de bureau.",
        rig_cat_control: 'Contrôle RIG / CAT',
        tcp_connection: 'Connexion TCP',
        serial_connection: 'Connexion série',
        hamlib_host: 'Hôte Hamlib :',
        port: 'Port :',
        test: 'Tester',
        ptt_test: 'TEST PTT',
        kiss_port: 'Port KISS',
        listen: 'Écoute',
        allowed_addresses: 'Adresses autorisées',
        allowed_placeholder: '0.0.0.0, 192.168.1.20 ou 192.168.1.0/24',
        toggle: 'Ajouter/Supprimer',
        localhost_hint: 'Localhost toujours autorisé : 127.0.0.1, ::1 | Vous pouvez ajouter une IP unique ou un réseau CIDR (par ex. 192.168.1.0/24)',
        build: 'Build',
        kiss_server: 'Serveur KISS',
        web_ui: 'Web UI',
        backend: 'Backend',
        selected_prefix: 'Sélectionné : ',
        not_selected: '-- non sélectionné --',
        backend_running: 'en cours',
        backend_offline: 'hors ligne',
        hamlib_not_tested: 'Hamlib : non testé',
        hamlib_offline: 'Hamlib : hors ligne',
        hamlib_ok: 'Hamlib : OK',
        cat_serial_offline: 'CAT série : hors ligne',
        hamlib_tcp_offline: 'Hamlib TCP : hors ligne',
        cat_serial_prefix: 'CAT série : ',
        hamlib_tcp_ok: 'Hamlib TCP : OK',
        no_data: '-- aucune donnée --',
        about_summary: "Les interfaces bureau et web partagent le même état backend. La page web suit le style du bureau : cartes claires, accents bleus, groupes de contrôles et zone moniteur nette."
      },
      es: {
        hero_eyebrow: 'Control remoto APRS TNC',
        hero_subtitle: 'Interfaz web alineada con el diseño de escritorio: estado, tarjetas de configuración y monitor.',
        language: 'Idioma',
        monitor: 'Monitor',
        configuration: 'Configuración',
        about: 'Acerca de',
        monitor_title: 'Monitor',
        audio_card_title: 'DISPOSITIVOS IN/OUT',
        audio_card_subtitle: 'Entradas, salidas y tonos de prueba',
        ptt_card_title: 'CONTROL PTT',
        ptt_card_subtitle: 'Ajustes PTT del escritorio',
        network_card_title: 'Puerto KISS',
        network_card_subtitle: 'TCP y lista permitida',
        about_title: 'Acerca de la aplicación',
        about_subtitle: 'Detalles de la aplicación',
        input_device: 'Audio INPUT (Micrófonos):',
        output_device: 'Audio OUTPUT (Altavoces):',
        input_level: 'Nivel de señal:',
        output_level: 'Nivel de señal:',
        test_tones: 'Tonos de prueba:',
        ptt_type: 'Tipo de PTT:',
        ptt_port: 'Puerto serie PTT:',
        ptt_active_low: 'PTT activo en bajo',
        rts_on: 'RTS forzado ON',
        dts_on: 'DTR forzado ON',
        civaddr: 'Dirección CI-V:',
        tx_delay: 'Retardo TX (ms):',
        tx_tail: 'Cola TX (ms):',
        tx_delay_hint: 'Usa el mismo control de temporización que la aplicación de escritorio.',
        rig_cat_control: 'Control RIG / CAT',
        tcp_connection: 'Conexión TCP',
        serial_connection: 'Conexión serie',
        hamlib_host: 'Host Hamlib:',
        port: 'Puerto:',
        test: 'Probar',
        ptt_test: 'PRUEBA PTT',
        kiss_port: 'Puerto KISS',
        listen: 'Escucha',
        allowed_addresses: 'Direcciones permitidas',
        allowed_placeholder: '0.0.0.0, 192.168.1.20 o 192.168.1.0/24',
        toggle: 'Agregar/Quitar',
        localhost_hint: 'Localhost siempre permitido: 127.0.0.1, ::1 | Puede agregar una IP única o una red CIDR (p. ej. 192.168.1.0/24)',
        build: 'Build',
        kiss_server: 'Servidor KISS',
        web_ui: 'Web UI',
        backend: 'Backend',
        selected_prefix: 'Seleccionado: ',
        not_selected: '-- no seleccionado --',
        backend_running: 'en ejecución',
        backend_offline: 'sin conexión',
        hamlib_not_tested: 'Hamlib: no probado',
        hamlib_offline: 'Hamlib: sin conexión',
        hamlib_ok: 'Hamlib: OK',
        cat_serial_offline: 'CAT serie: sin conexión',
        hamlib_tcp_offline: 'Hamlib TCP: sin conexión',
        cat_serial_prefix: 'CAT serie: ',
        hamlib_tcp_ok: 'Hamlib TCP: OK',
        no_data: '-- sin datos --',
        about_summary: 'Las interfaces de escritorio y web comparten el mismo estado del backend. La web sigue el estilo del escritorio: tarjetas claras, acentos azules, controles agrupados y una zona de monitor limpia.'
      },
      pl: {
        hero_eyebrow: 'Zdalne sterowanie APRS TNC',
        hero_subtitle: 'Interfejs web w układzie zgodnym z aplikacją desktopową: status, sekcje konfiguracji i monitor.',
        language: 'Język',
        monitor: 'Monitor',
        configuration: 'Konfiguracja',
        about: 'O aplikacji',
        monitor_title: 'Monitor',
        audio_card_title: 'URZĄDZENIA IN/OUT',
        audio_card_subtitle: 'Wejścia, wyjścia audio i tony testowe',
        ptt_card_title: 'KONTROLA PTT',
        ptt_card_subtitle: 'Ustawienia PTT z aplikacji desktopowej',
        network_card_title: 'Port KISS',
        network_card_subtitle: 'TCP i lista dozwolonych adresów',
        about_title: 'O aplikacji',
        about_subtitle: 'Szczegóły aplikacji',
        input_device: 'Audio INPUT (Mikrofony):',
        output_device: 'Audio OUTPUT (Głośniki):',
        input_level: 'Poziom sygnału:',
        output_level: 'Poziom sygnału:',
        test_tones: 'Tony testowe:',
        ptt_type: 'Typ PTT:',
        ptt_port: 'Port PTT (szeregowy):',
        ptt_active_low: 'PTT aktywne stanem niskim',
        rts_on: 'RTS wymuszone ON',
        dts_on: 'DTR wymuszone ON',
        civaddr: 'Adres CI-V:',
        tx_delay: 'TX Delay (ms):',
        tx_tail: 'TX Tail (ms):',
        tx_delay_hint: 'Używa tego samego sterowania czasem co aplikacja desktopowa.',
        rig_cat_control: 'Kontrola RIG / CAT',
        tcp_connection: 'Połączenie TCP',
        serial_connection: 'Połączenie szeregowe',
        hamlib_host: 'Host Hamlib:',
        port: 'Port:',
        test: 'Test',
        ptt_test: 'TEST PTT',
        kiss_port: 'Port KISS',
        listen: 'Nasłuch',
        allowed_addresses: 'Dozwolone adresy',
        allowed_placeholder: '0.0.0.0, 192.168.1.20 lub 192.168.1.0/24',
        toggle: 'Dodaj/Usuń',
        localhost_hint: 'Localhost zawsze dozwolony: 127.0.0.1, ::1 | Możesz dodać pojedyncze IP lub sieć CIDR (np. 192.168.1.0/24)',
        build: 'Wersja',
        kiss_server: 'Serwer KISS',
        web_ui: 'Web UI',
        backend: 'Backend',
        selected_prefix: 'Wybrano: ',
        not_selected: '-- nie wybrano --',
        backend_running: 'uruchomiony',
        backend_offline: 'offline',
        hamlib_not_tested: 'Hamlib: nie testowano',
        hamlib_offline: 'Hamlib: offline',
        hamlib_ok: 'Hamlib: OK',
        cat_serial_offline: 'CAT szeregowy: offline',
        hamlib_tcp_offline: 'Hamlib TCP: offline',
        cat_serial_prefix: 'CAT szeregowy: ',
        hamlib_tcp_ok: 'Hamlib TCP: OK',
        no_data: '-- brak danych --',
        about_summary: 'Interfejsy desktop i web korzystają z tego samego stanu backendu. Web zachowuje styl aplikacji desktopowej: jasne karty, niebieskie akcenty, grupowane kontrolki i czytelny monitor.'
      }
    };

    function t(key) {
      var lang = I18N[currentLang] ? currentLang : 'en';
      return (I18N[lang] && I18N[lang][key]) || (I18N.en && I18N.en[key]) || key;
    }

    function applyTranslations(lang) {
      currentLang = I18N[lang] ? lang : 'en';
      document.documentElement.lang = currentLang;
      var languageSelect = document.getElementById('ui-language');
      if (languageSelect) {
        var existing = Array.from(languageSelect.options).map(function (o) { return o.value + '|' + o.textContent; });
        var incoming = LANGUAGE_OPTIONS.map(function (o) { return o.value + '|' + o.label; });
        var changed = incoming.length !== existing.length || incoming.some(function (v, i) { return v !== existing[i]; });
        if (changed) {
          languageSelect.innerHTML = LANGUAGE_OPTIONS.map(function (o) {
            return '<option value="' + o.value + '">' + o.label + '</option>';
          }).join('');
        }
        languageSelect.value = currentLang;
      }

      var textMap = {
        'hero-eyebrow': 'hero_eyebrow',
        'hero-subtitle': 'hero_subtitle',
        'language-label': 'language',
        'tab-monitor': 'monitor',
        'tab-config': 'configuration',
        'tab-about': 'about',
        'monitor-title': 'monitor_title',
        'audio-card-title': 'audio_card_title',
        'audio-card-subtitle': 'audio_card_subtitle',
        'input-device-label': 'input_device',
        'input-level-label': 'input_level',
        'output-device-label': 'output_device',
        'output-level-label': 'output_level',
        'test-tones-label': 'test_tones',
        'ptt-card-title': 'ptt_card_title',
        'ptt-card-subtitle': 'ptt_card_subtitle',
        'ptt-type-label': 'ptt_type',
        'ptt-port-label': 'ptt_port',
        'ptt-active-low-label': 'ptt_active_low',
        'rts-on-label': 'rts_on',
        'dts-on-label': 'dts_on',
        'civaddr-label': 'civaddr',
        'tx-delay-label': 'tx_delay',
        'tx-tail-label': 'tx_tail',
        'tx-delay-hint': 'tx_delay_hint',
        'hamlib-group-label': 'rig_cat_control',
        'kiss-network-title': 'network_card_title',
        'kiss-network-subtitle': 'network_card_subtitle',
        'kiss-port-info-label': 'kiss_port',
        'listen-label': 'listen',
        'kiss-port-label': 'kiss_port',
        'allowed-addresses-label': 'allowed_addresses',
        'about-title': 'about_title',
        'about-subtitle': 'about_subtitle',
        'about-summary-text': 'about_summary',
        'about-build-label': 'build',
        'about-kiss-label': 'kiss_server',
        'about-web-label': 'web_ui',
        'about-backend-label': 'backend',
      };

      Object.keys(textMap).forEach(function (id) {
        var el = document.getElementById(id);
        if (el) {
          el.textContent = t(textMap[id]);
        }
      });

      var refreshInput = document.getElementById('refresh-input-btn');
      var refreshOutput = document.getElementById('refresh-output-btn');
      var refreshKiss = document.getElementById('refresh-kiss-btn');
      var toggleAllow = document.getElementById('toggle-allow-btn');
      var hamlibTest = document.getElementById('hamlib-test-btn');
      var pttTest = document.getElementById('ptt-test-btn');
      if (refreshInput) refreshInput.textContent = t('refresh');
      if (refreshOutput) refreshOutput.textContent = t('refresh');
      if (refreshKiss) refreshKiss.textContent = t('refresh');
      if (toggleAllow) toggleAllow.textContent = t('toggle');
      if (hamlibTest) hamlibTest.textContent = t('test');
      if (pttTest) pttTest.textContent = t('ptt_test');

      var tcpOpt = document.getElementById('tcp-connection-option');
      var serialOpt = document.getElementById('serial-connection-option');
      if (tcpOpt) tcpOpt.textContent = t('tcp_connection');
      if (serialOpt) serialOpt.textContent = t('serial_connection');

      var allowInput = document.getElementById('allow-ip-input');
      if (allowInput) allowInput.placeholder = t('allowed_placeholder');
      var hamlibHost = document.getElementById('hamlib-host');
      if (hamlibHost && !hamlibHost.placeholder) hamlibHost.placeholder = '127.0.0.1';

      var aboutTitle = document.getElementById('about-summary-title');
      if (aboutTitle) aboutTitle.textContent = 'MicroKISStnc';
    }

    async function setUiLanguage(value) {
      var lang = String(value || '').toLowerCase();
      if (!lang) return;
      await apiCall('POST', '/api/control/ui-language', { lang: lang });
      await refresh();
    }

    applyTranslations(currentLang);

    function norm(value, fallback) {
      return value === undefined || value === null || value === '' ? fallback : value;
    }

    function apiCall(method, endpoint, data) {
      var opts = { method: method, cache: 'no-store' };
      if (data !== undefined && data !== null) {
        opts.headers = { 'Content-Type': 'application/json' };
        opts.body = JSON.stringify(data);
      }
      return fetch(endpoint, opts)
        .then(function (response) {
          if (!response.ok) {
            throw new Error('HTTP ' + response.status);
          }
          return response.json();
        })
        .catch(function (err) {
          console.error('API error', endpoint, err);
          return null;
        });
    }

    function setView(viewName) {
      var next = ['monitor', 'config', 'about'].indexOf(viewName) >= 0 ? viewName : 'monitor';
      Array.from(document.querySelectorAll('.view')).forEach(function (view) {
        view.classList.toggle('active', view.id === 'view-' + next);
      });
      Array.from(document.querySelectorAll('.tab-btn')).forEach(function (btn) {
        btn.classList.toggle('active', btn.dataset.tab === next);
      });
      try { localStorage.setItem('mkiss_view', next); } catch (_e) {}
    }

    (function initView() {
      setView('monitor');
    })();

    function populateSelect(selectId, options, selectedValue) {
      var select = document.getElementById(selectId);
      if (!select) return;

      var list = Array.isArray(options) ? options.filter(Boolean) : [];
      var isObjectList = list.length > 0 && typeof list[0] === 'object';
      var normalized = isObjectList
        ? list.map(function (item) { return { value: String(item.id), label: String(item.label || item.id) }; })
        : list.map(function (item) { return { value: String(item), label: String(item) }; });

      select.dataset.idBased = isObjectList ? 'true' : 'false';
      var existing = Array.from(select.options).map(function (o) { return o.value + '|' + o.textContent; });
      var incoming = normalized.map(function (o) { return o.value + '|' + o.label; });
      var changed = incoming.length !== existing.length || incoming.some(function (v, i) { return v !== existing[i]; });
      if (changed) {
        select.innerHTML = normalized.map(function (o) {
          return '<option value="' + o.value + '">' + o.label + '</option>';
        }).join('');
      }

      var selected = selectedValue !== undefined && selectedValue !== null ? String(selectedValue) : '';
      if (!selected) return;
      for (var i = 0; i < select.options.length; i++) {
        if (select.options[i].value === selected) {
          select.value = selected;
          return;
        }
      }
      if (isObjectList) {
        for (var j = 0; j < select.options.length; j++) {
          if (select.options[j].textContent.trim() === selected.trim()) {
            select.value = select.options[j].value;
            return;
          }
        }
      }
    }

    function setMeter(id, metaId, peakPct, peakDbfs, rmsPct, rmsDbfs) {
      var peakValue = Number(norm(peakPct, 0));
      var rmsValue = Number(norm(rmsPct, 0));
      var peakClamped = Math.max(0, Math.min(100, peakValue));
      var rmsClamped = Math.max(0, Math.min(100, rmsValue));
      var peakDb = Number.isFinite(peakDbfs) ? peakDbfs : -96;
      var rmsDb = Number.isFinite(rmsDbfs) ? rmsDbfs : -96;
      var bar = document.getElementById(id);
      var meta = document.getElementById(metaId);
      if (bar) bar.style.width = peakClamped.toFixed(1) + '%';
      if (meta) {
        meta.textContent = 'Peak: ' + peakClamped.toFixed(1) + '% (' + peakDb.toFixed(1) + ' dBFS) | RMS: ' + rmsClamped.toFixed(1) + '% (' + rmsDb.toFixed(1) + ' dBFS)';
      }
    }

    function syncLevelCards() {
      var rx = document.getElementById('rx-meter');
      var tx = document.getElementById('tx-meter');
      var rxCard = document.getElementById('rx-meter-card');
      var txCard = document.getElementById('tx-meter-card');
      if (rxCard && rx) rxCard.style.width = rx.style.width || '0%';
      if (txCard && tx) txCard.style.width = tx.style.width || '0%';
    }

    function updateText(id, value) {
      var el = document.getElementById(id);
      if (el) el.textContent = value;
    }

    async function refresh() {
      var state = await apiCall('GET', '/api/state');
      if (!state) {
        applyTranslations(currentLang);
        updateText('about-backend', t('backend_offline'));
        return;
      }

      applyTranslations(state.ui_language || currentLang);

      updateText('build-info', norm(state.build, '-'));
      updateText('about-build', norm(state.build, '-'));
      updateText('about-kiss', norm(state.kiss_listen, '-'));
      updateText('about-web', norm(state.web_listen, location.host));
      updateText('about-backend', t('backend_running'));
      updateText('kiss-port-info', String(norm(state.kiss_port, '-')));
      updateText('kiss-listen-info', norm(state.kiss_listen, '-'));

      var inputSel = state.input_device_id !== undefined && state.input_device_id !== null ? state.input_device_id : state.input_device;
      var outputSel = state.output_device_id !== undefined && state.output_device_id !== null ? state.output_device_id : state.output_device;
      populateSelect('input-device', norm(state.input_devices, []), norm(inputSel, ''));
      populateSelect('output-device', norm(state.output_devices, []), norm(outputSel, ''));
      populateSelect('ptt-mode', norm(state.ptt_modes, ['RIG', 'DTR', 'RTS', 'VOX']), norm(state.ptt_type || state.ptt_mode, 'VOX'));
      populateSelect('ptt-path', norm(state.ptt_paths, []).map(String), String(norm(state.ptt_path, '')));
      populateSelect('allow-ip-list', norm(state.allowed_ips, []).map(String), '');
      populateSelect('cat-serial-port', norm(state.ptt_paths, []).map(String), String(norm(state.cat_serial_port, '')));

      var inputDeviceSelect = document.getElementById('input-device');
      var outputDeviceSelect = document.getElementById('output-device');
      var inputLabel = inputDeviceSelect && inputDeviceSelect.value && inputDeviceSelect.options[inputDeviceSelect.selectedIndex]
        ? inputDeviceSelect.options[inputDeviceSelect.selectedIndex].textContent
        : t('not_selected');
      var outputLabel = outputDeviceSelect && outputDeviceSelect.value && outputDeviceSelect.options[outputDeviceSelect.selectedIndex]
        ? outputDeviceSelect.options[outputDeviceSelect.selectedIndex].textContent
        : t('not_selected');
      updateText('input-device-status', t('selected_prefix') + inputLabel);
      updateText('output-device-status', t('selected_prefix') + outputLabel);

      var monitorLines = Array.isArray(state.monitor_lines) ? state.monitor_lines : [];
      updateText('monitor', monitorLines.length > 0 ? monitorLines.join('\\n') : norm(state.last_monitor_line, t('no_data')));
      var allowedIps = Array.isArray(state.allowed_ips) ? state.allowed_ips : [];
      updateText('allow-ip-status', t('allowed_addresses') + ': ' + (allowedIps.length ? allowedIps.join(', ') : '--'));

      var pttType = String(norm(state.ptt_type || state.ptt_mode, 'VOX')).toUpperCase();
      var isSerial = pttType === 'DTR' || pttType === 'RTS';
      var isHamlib = pttType === 'RIG';
      var rigConnection = String(norm(state.rig_connection, 'TCP')).toUpperCase();
      var isCatSerial = isHamlib && rigConnection === 'SERIAL';
      var isCatTcp = isHamlib && rigConnection === 'TCP';
      document.getElementById('check-rts').disabled = !isSerial;
      document.getElementById('check-dts').disabled = !isSerial;
      document.getElementById('ptt-path').disabled = !isSerial;
      document.getElementById('check-ptt-invert').disabled = !isSerial;
      document.getElementById('cat-connection').disabled = !isHamlib;
      document.getElementById('cat-serial-port').disabled = !isCatSerial;
      document.getElementById('cat-serial-baud').disabled = !isCatSerial;
      document.getElementById('hamlib-host').disabled = !isCatTcp;
      document.getElementById('hamlib-port').disabled = !isCatTcp;
      document.getElementById('hamlib-group').style.opacity = isHamlib ? '1' : '0.60';
      document.getElementById('cat-serial-group').style.opacity = isCatSerial ? '1' : '0.60';

      var pttBtnEl = document.getElementById('ptt-test-btn');
      if (pttBtnEl) {
        pttBtnEl.disabled = pttType === 'VOX';
        pttBtnEl.style.background = state.ptt_active ? '#b00020' : '#2f8d4f';
        pttBtnEl.style.borderColor = state.ptt_active ? '#7a0016' : '#1f6c39';
      }

      document.getElementById('check-rts').checked = !!state.use_rts;
      document.getElementById('check-dts').checked = !!state.use_dts;
      document.getElementById('check-ptt-invert').checked = !!state.ptt_active_low;
      document.getElementById('civaddr').value = String(norm(state.civaddr, '0x00'));
      document.getElementById('kiss-port').value = String(norm(state.kiss_port, ''));

      var txDelayEl = document.getElementById('tx-delay');
      var txDelayValue = Number(norm(state.tx_delay_ms, norm(state.vox_delay_ms, 0)));
      if (Number(txDelayEl.value) !== txDelayValue) txDelayEl.value = String(txDelayValue);
      var txTailEl = document.getElementById('tx-tail');
      var txTailValue = Number(norm(state.tx_tail_ms, 0));
      if (Number(txTailEl.value) !== txTailValue) txTailEl.value = String(txTailValue);

      var catBaudEl = document.getElementById('cat-serial-baud');
      var catBaud = Number(norm(state.cat_serial_baud, 19200));
      if (Number(catBaudEl.value) !== catBaud) catBaudEl.value = String(catBaud);

      document.getElementById('cat-connection').value = rigConnection;
      var host = String(norm(state.hamlib_host, '127.0.0.1'));
      var port = Number(norm(state.hamlib_port, 4532));
      var hostEl = document.getElementById('hamlib-host');
      var portEl = document.getElementById('hamlib-port');
      if (hostEl.value !== host) hostEl.value = host;
      if (Number(portEl.value) !== port) portEl.value = String(port);

      toneActive = norm(state.tone_active, '');
      ['1200', 'both', '2200'].forEach(function (tone) {
        var btn = document.getElementById('tone-' + tone);
        if (btn) btn.classList.toggle('active', toneActive === tone);
      });

      var hamlibStatus = document.getElementById('hamlib-status');
      if (hamlibStatus && (!hamlibStatus.textContent || hamlibStatus.textContent === 'Hamlib: not tested')) {
        hamlibStatus.textContent = t('hamlib_not_tested');
      }
    }

    async function setInputDevice(value) {
      var select = document.getElementById('input-device');
      var payload = select.dataset.idBased === 'true' ? { device_id: Number(value) } : { device: value };
      await apiCall('POST', '/api/control/input-device', payload);
      await refresh();
    }

    async function setOutputDevice(value) {
      var select = document.getElementById('output-device');
      var payload = select.dataset.idBased === 'true' ? { device_id: Number(value) } : { device: value };
      await apiCall('POST', '/api/control/output-device', payload);
      await refresh();
    }

    async function setPTTMode(value) { await apiCall('POST', '/api/control/ptt-mode', { mode: value }); await refresh(); }
    async function setPTTPath(value) { if (!value) return; await apiCall('POST', '/api/control/ptt-path', { path: value }); await refresh(); }
    async function setPTTInvert() { await apiCall('POST', '/api/control/ptt-invert', { active_low: document.getElementById('check-ptt-invert').checked }); await refresh(); }
    async function togglePTTTest() {
      var btn = document.getElementById('ptt-test-btn');
      var active = !!(btn && btn.dataset.active === '1');
      await apiCall('POST', '/api/control/ptt-test', { active: !active });
      await refresh();
    }
    async function setCivAddr(value) { var civaddr = String(value || '').trim(); if (!civaddr) return; await apiCall('POST', '/api/control/civaddr', { civaddr: civaddr }); await refresh(); }
    async function setPTTPins() { if (document.getElementById('check-rts').disabled && document.getElementById('check-dts').disabled) return; await apiCall('POST', '/api/control/ptt-pins', { rts: document.getElementById('check-rts').checked, dts: document.getElementById('check-dts').checked }); await refresh(); }
    async function setTxDelay(value) { await apiCall('POST', '/api/control/vox-delay', { delay_ms: Number(value) }); await refresh(); }
    async function setTxTail(value) { await apiCall('POST', '/api/control/tx-tail', { tail_ms: Number(value) }); await refresh(); }
    async function setKissPort(value) {
      var port = Number(value);
      if (!Number.isFinite(port)) return;
      await apiCall('POST', '/api/control/kiss-port', { port: port });
      await refresh();
    }
    async function refreshKissPort() { await refresh(); }

    async function setHamlibConfig(doTest) {
      var host = document.getElementById('hamlib-host').value || '127.0.0.1';
      var port = Number(document.getElementById('hamlib-port').value || 4532);
      var result = await apiCall('POST', '/api/control/hamlib-config', { host: host, port: port, test: !!doTest });
      var status = document.getElementById('hamlib-status');
      if (!result || result.ok === false) { status.textContent = t('hamlib_offline'); return; }
      status.textContent = doTest ? t('hamlib_ok') : ('Hamlib: ' + host + ':' + port);
      if (doTest) await refresh();
    }

    async function setCatConnection(mode, test) {
      var modeValue = String(mode || document.getElementById('cat-connection').value || 'TCP').toUpperCase();
      var path = document.getElementById('cat-serial-port').value || '';
      var baud = Number(document.getElementById('cat-serial-baud').value || 19200);
      var result = await apiCall('POST', '/api/control/cat-connection', { mode: modeValue, path: path, baud: baud, test: !!test });
      var status = document.getElementById('hamlib-status');
      if (!result || result.ok === false) {
        status.textContent = modeValue === 'SERIAL' ? t('cat_serial_offline') : t('hamlib_tcp_offline');
      } else if (test) {
        status.textContent = modeValue === 'SERIAL'
          ? (t('cat_serial_prefix') + (path || '-') + ' @ ' + baud)
          : t('hamlib_tcp_ok');
      }
      await refresh();
    }

    async function setCatConnectionMode(mode) { await setCatConnection(mode, false); }
    async function setCatSerialPath(value) { if (!value) return; await setCatConnection(null, false); }
    async function setCatSerialBaud(_value) { await setCatConnection(null, false); }
    async function testHamlib() {
      var mode = String(document.getElementById('cat-connection').value || 'TCP').toUpperCase();
      if (mode === 'SERIAL') { await setCatConnection(mode, true); return; }
      await setHamlibConfig(true);
    }
    async function refreshDevices() { await apiCall('POST', '/api/control/refresh-devices', {}); await refresh(); }
    async function toggleAllowIp() {
      var input = document.getElementById('allow-ip-input');
      var ip = String(input.value || '').trim();
      if (!ip) return;
      await apiCall('POST', '/api/control/allow-ip-toggle', { ip: ip });
      input.value = '';
      await refresh();
    }
    async function toggleTone(tone) { await apiCall('POST', '/api/control/tone', { tone: toneActive === tone ? 'stop' : tone }); await refresh(); }

    refresh();
    setInterval(refresh, 1000);
  </script>
</body>
</html>
"""


class WebControlServer:
    """Local web UI server with bidirectional control."""

    ALLOW_ALL_TOKEN = "0.0.0.0"
    LOCAL_ALWAYS_ALLOWED = {"127.0.0.1", "::1"}

    def __init__(
        self,
        host: str,
        port: int,
        get_status: Callable[[], Dict],
        api_handlers: Dict[str, Callable] = None,
        allowed_ips: Optional[set] = None,
        control_token: str = "",
        max_post_bytes: int = 16384,
    ):
        self.host = host
        self.port = port
        self.get_status = get_status
        self.api_handlers = api_handlers or {}
        self.allowed_ips = set(allowed_ips or [])
        self.control_token = str(control_token or "")
        self.max_post_bytes = max(512, int(max_post_bytes))
        self._server: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def _is_ip_allowed(self, ip: str) -> bool:
        """Check if remote IP is allowed by current allowlist."""
        if ip in self.LOCAL_ALWAYS_ALLOWED:
            return True
        if not self.allowed_ips:
            return True
        if self.ALLOW_ALL_TOKEN in self.allowed_ips:
            return True
        if ip in self.allowed_ips:
            return True

        # Support CIDR networks (e.g. 192.168.1.0/24) in allowlist.
        try:
            remote_ip = ipaddress.ip_address(ip)
        except ValueError:
            return False

        for entry in self.allowed_ips:
            if "/" not in entry:
                continue
            try:
                net = ipaddress.ip_network(entry, strict=False)
            except ValueError:
                continue
            if remote_ip in net:
                return True
        return False

    def start(self) -> bool:
        """Start HTTP server in a background thread."""
        if self._server is not None:
            return True

        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            def _json(self, payload: Dict, code: int = 200) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def _html(self, html: str, code: int = 200) -> None:
                body = html.encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path == "/":
                    self._html(INDEX_HTML)
                    return
                if parsed.path == "/api/state":
                    payload = server_ref.get_status()
                    payload["web_time"] = datetime.utcnow().isoformat() + "Z"
                    self._json(payload)
                    return
                if parsed.path == "/api/status":  # Backward compat alias
                    payload = server_ref.get_status()
                    payload["web_time"] = datetime.utcnow().isoformat() + "Z"
                    self._json(payload)
                    return
                self._json({"error": "not_found"}, code=404)

            def do_POST(self):
                parsed = urlparse(self.path)
                remote_ip = self.client_address[0] if self.client_address else ""
                if server_ref.allowed_ips and not server_ref._is_ip_allowed(remote_ip):
                    self._json({"ok": False, "error": "forbidden_ip"}, code=403)
                    return

                if server_ref.control_token:
                    token = self.headers.get("X-MicroKISS-Token", "")
                    if token != server_ref.control_token:
                        self._json({"ok": False, "error": "forbidden_token"}, code=403)
                        return

                content_length = int(self.headers.get("Content-Length", 0))
                if content_length > server_ref.max_post_bytes:
                    self._json({"ok": False, "error": "payload_too_large"}, code=413)
                    return
                body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
                
                try:
                    data = json.loads(body)
                except:
                    data = {}

                # Route to handler
                handler_key = parsed.path.replace("/api/control/", "").lower()
                if handler_key in server_ref.api_handlers:
                    try:
                        result = server_ref.api_handlers[handler_key](data)
                        self._json({"ok": True, "result": result})
                    except Exception as e:
                        logger.warning(f"[WEB] Handler {handler_key} error: {e}")
                        self._json({"ok": False, "error": str(e)}, code=400)
                else:
                    self._json({"error": "unknown_action"}, code=404)

            def log_message(self, _format: str, *args):
                logger.debug("[WEB] " + _format, *args)

        try:
            self._server = ThreadingHTTPServer((self.host, self.port), Handler)
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()
            logger.info(f"[WEB] Listening on http://{self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"[WEB] Failed to start on http://{self.host}:{self.port}: {e}")
            self._server = None
            self._thread = None
            return False

    def register_handler(self, action: str, callback: Callable) -> None:
        """Register a POST handler for /api/control/{action}."""
        self.api_handlers[action] = callback

    def stop(self) -> None:
        """Stop HTTP server and join thread."""
        if self._server is None:
            return

        try:
            self._server.shutdown()
            self._server.server_close()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)
            logger.info("[WEB] Server stopped")
        except Exception as e:
            logger.warning(f"[WEB] Stop error: {e}")
        finally:
            self._server = None
            self._thread = None
