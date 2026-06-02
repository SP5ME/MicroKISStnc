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
