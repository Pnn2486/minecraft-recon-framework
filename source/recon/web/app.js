(() => {
  'use strict';

  const TOKEN = document.querySelector('meta[name="recon-token"]').content;
  const SERVERS_KEY = 'recon-servers-v2';
  const UI_KEY = 'recon-ui-v2';
  const MAX_SERVERS = 100;

  const TOOLS = {
    ping: { title: 'Server status', desc: 'Check whether the server is online, which version it runs, who is playing and how fast it answers.', run: 'Check status' },
    query: { title: 'Server details', desc: 'Ask the server for its world, plugins and full player list. The server needs enable-query=true.', run: 'Get details' },
    rcon: { title: 'Console', desc: 'Send one console command. The server needs enable-rcon=true and you need the RCON password.', run: 'Send command' },
    ghost: { title: 'Test player', desc: 'Join an offline-mode server (online-mode=false) as a quiet test player and watch what the server sends.', run: 'Join as test player' },
  };
  const OPTION_IDS = ['command', 'preset', 'username', 'protocol_version', 'duration', 'timeout'];
  const OPTION_DEFAULTS = { command: 'list', username: 'AuditNode', protocol_version: 'auto', duration: '20', timeout: '5' };
  const QUERY_LABELS = {
    hostname: 'Name', gametype: 'Game type', game_id: 'Game', version: 'Version', plugins: 'Plugins',
    map: 'World', numplayers: 'Players online', maxplayers: 'Maximum players', hostip: 'Address', hostport: 'Port',
  };

  const $ = (id) => document.getElementById(id);
  let servers = [];
  let selectedId = null;
  let tool = 'ping';
  let busy = false;
  let editingId = null;

  function h(tag, props, ...kids) {
    const node = document.createElement(tag);
    if (props) {
      for (const [key, value] of Object.entries(props)) {
        if (key === 'class') node.className = value;
        else if (key === 'text') node.textContent = value;
        else node.setAttribute(key, value);
      }
    }
    for (const kid of kids.flat()) {
      if (kid === null || kid === undefined) continue;
      node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    }
    return node;
  }

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const clean = (text) => String(text).replace(/§./g, '');
  const isIcon = (value) => typeof value === 'string' && value.length < 200000 && /^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(value);

  async function api(path, options = {}) {
    const response = await fetch(path, { ...options, headers: { 'X-Recon-Token': TOKEN, 'Content-Type': 'application/json' } });
    let data = {};
    try { data = await response.json(); } catch (_) { /* not JSON */ }
    if (!response.ok) throw new Error(data.error || `The request failed (${response.status}).`);
    return data;
  }

  // ---- storage (never the password) ----
  function readJson(key, fallback) {
    try { const value = JSON.parse(localStorage.getItem(key)); return value === null || value === undefined ? fallback : value; } catch (_) { return fallback; }
  }
  function writeJson(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) { /* storage not available */ }
  }
  function saveServers() { writeJson(SERVERS_KEY, servers); }
  function saveUi() {
    const ui = { tool, selectedId };
    for (const id of OPTION_IDS) ui[id] = $(id).value;
    writeJson(UI_KEY, ui);
  }

  function sanitizeServer(raw) {
    if (!raw || typeof raw !== 'object') return null;
    const host = typeof raw.host === 'string' ? raw.host.trim().slice(0, 253) : '';
    const port = Number(raw.port);
    const rcon = Number(raw.rcon_port);
    if (!host || typeof raw.id !== 'string') return null;
    return {
      id: raw.id.slice(0, 40),
      name: (typeof raw.name === 'string' && raw.name.trim() ? raw.name.trim() : host).slice(0, 40),
      host,
      port: Number.isInteger(port) && port > 0 && port < 65536 ? port : 25565,
      rcon_port: Number.isInteger(rcon) && rcon > 0 && rcon < 65536 ? rcon : 25575,
      icon: isIcon(raw.icon) ? raw.icon : '',
      online: raw.online === true ? true : (raw.online === false ? false : null),
      players: typeof raw.players === 'string' ? raw.players.slice(0, 20) : '',
    };
  }

  const current = () => servers.find((s) => s.id === selectedId) || null;
  const newId = () => `s${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;

  // ---- icons ----
  function hueOf(text) {
    let hash = 0;
    for (const ch of text) hash = (hash * 31 + ch.codePointAt(0)) % 360;
    return hash;
  }

  function iconNode(server) {
    if (server.icon) return h('img', { src: server.icon, alt: '' });
    const letter = h('div', { class: 'letter', text: (Array.from(server.name)[0] || '?').toUpperCase() });
    letter.style.setProperty('--hue', String(hueOf(server.name + server.host)));
    return letter;
  }

  // ---- rendering the library ----
  function renderTiles() {
    const box = $('tiles');
    box.replaceChildren();
    for (const server of servers) {
      const dot = h('span', { class: `dot${server.online === true ? ' on' : (server.online === false ? ' off' : '')}` });
      const tile = h('button', {
        type: 'button', class: 'tile', role: 'option', 'data-id': server.id,
        'aria-selected': String(server.id === selectedId),
        'aria-label': `${server.name}, ${server.host}`,
      },
      h('span', { class: 'tile-icon' }, iconNode(server), dot),
      h('span', { class: 'tile-name', text: server.name }),
      h('span', { class: 'tile-sub', text: server.players || `${server.host}:${server.port}` }));
      box.append(tile);
    }
    const count = servers.length;
    $('count').textContent = count ? `${count} ${count === 1 ? 'server' : 'servers'}` : '';
    $('empty').hidden = count > 0;
    box.hidden = count === 0;
  }

  function renderSelected() {
    const server = current();
    $('selected').hidden = !server;
    $('no-selection').hidden = !!server;
    $('btn-edit').disabled = !server || busy;
    $('btn-remove').disabled = !server || busy;
    if (!server) return;
    $('sel-icon').replaceChildren(iconNode(server));
    $('sel-name').textContent = server.name;
    $('sel-addr').textContent = `${server.host}:${server.port}`;
    const live = $('sel-status');
    live.className = `live${server.online === true ? ' on' : (server.online === false ? ' off' : '')}`;
    if (server.online === true) live.textContent = server.players ? `Online - ${server.players} players` : 'Online';
    else if (server.online === false) live.textContent = 'Not reachable at last check';
    else live.textContent = 'Not checked yet';
  }

  function renderTool() {
    for (const button of $('tool-list').querySelectorAll('.tool')) {
      button.setAttribute('aria-checked', String(button.dataset.tool === tool));
      button.tabIndex = button.dataset.tool === tool ? 0 : -1;
    }
    $('tool-desc').textContent = TOOLS[tool].desc;
    for (const field of document.querySelectorAll('[data-tools]')) {
      field.hidden = !field.dataset.tools.split(' ').includes(tool);
    }
    updateRun();
  }

  function updateRun() {
    const server = current();
    $('run').disabled = busy || !server || !$('authorized').checked;
    $('run-label').textContent = busy ? 'Running...' : TOOLS[tool].run;
    if (busy) $('run-sub').textContent = 'Please wait';
    else if (!server) $('run-sub').textContent = 'Select a server first';
    else if (!$('authorized').checked) $('run-sub').textContent = 'Tick the permission box';
    else $('run-sub').textContent = server.name;
  }

  function refresh() {
    renderTiles();
    renderSelected();
    renderTool();
  }

  function select(id) {
    if (busy) return;
    if (id !== selectedId) $('result').hidden = true;
    selectedId = id;
    for (const tile of $('tiles').querySelectorAll('.tile')) tile.setAttribute('aria-selected', String(tile.dataset.id === id));
    renderSelected();
    renderTool();
    saveUi();
  }

  function setTool(next) {
    if (!TOOLS[next] || busy) return;
    if (next !== tool) $('result').hidden = true;
    tool = next;
    renderTool();
    saveUi();
  }

  // ---- dialogs ----
  function openDialog(dialog) {
    if (typeof dialog.showModal === 'function') dialog.showModal();
    else dialog.setAttribute('open', '');
  }
  function closeDialog(dialog) {
    if (typeof dialog.close === 'function') dialog.close();
    else dialog.removeAttribute('open');
  }

  function openServerDialog(server) {
    editingId = server ? server.id : null;
    $('server-dialog-title').textContent = server ? 'Edit server' : 'Add server';
    $('f-name').value = server ? server.name : '';
    $('f-host').value = server ? server.host : '';
    $('f-port').value = server ? String(server.port) : '';
    $('f-rcon').value = server ? String(server.rcon_port) : '';
    $('f-error').hidden = true;
    openDialog($('server-dialog'));
    $('f-host').focus();
  }

  function portValue(text, fallback, label) {
    const trimmed = text.trim();
    if (!trimmed) return fallback;
    const value = Number(trimmed);
    if (!Number.isInteger(value) || value < 1 || value > 65535) throw new Error(`${label} must be a number from 1 to 65535.`);
    return value;
  }

  function saveServerForm(event) {
    event.preventDefault();
    try {
      const host = $('f-host').value.trim();
      if (!host) throw new Error('Enter the server address.');
      if (/[\s/\\]/.test(host)) throw new Error('The address must not contain spaces or slashes.');
      const port = portValue($('f-port').value, 25565, 'The game port');
      const rcon = portValue($('f-rcon').value, 25575, 'The RCON port');
      const name = $('f-name').value.trim() || host;
      const existing = servers.find((s) => s.id === editingId);
      if (existing) {
        if (existing.host !== host || existing.port !== port) { existing.icon = ''; existing.online = null; existing.players = ''; }
        Object.assign(existing, { name, host, port, rcon_port: rcon });
        selectedId = existing.id;
      } else {
        if (servers.length >= MAX_SERVERS) throw new Error('That is the maximum number of saved servers.');
        const server = { id: newId(), name, host, port, rcon_port: rcon, icon: '', online: null, players: '' };
        servers.push(server);
        selectedId = server.id;
      }
      saveServers();
      closeDialog($('server-dialog'));
      $('result').hidden = true;
      refresh();
      saveUi();
    } catch (error) {
      $('f-error').textContent = error.message;
      $('f-error').hidden = false;
    }
  }

  function askRemove() {
    const server = current();
    if (!server) return;
    $('confirm-text').textContent = `"${server.name}" will be removed from this list. The server itself is not touched.`;
    openDialog($('confirm-dialog'));
  }

  function doRemove() {
    servers = servers.filter((s) => s.id !== selectedId);
    selectedId = servers.length ? servers[0].id : null;
    saveServers();
    closeDialog($('confirm-dialog'));
    $('result').hidden = true;
    refresh();
    saveUi();
  }

  // ---- results ----
  function flatten(component) {
    if (component === null || component === undefined) return '';
    if (typeof component === 'string') return component;
    if (Array.isArray(component)) return component.map(flatten).join('');
    if (typeof component === 'object') {
      let text = typeof component.text === 'string' ? component.text : '';
      if (Array.isArray(component.extra)) text += component.extra.map(flatten).join('');
      return text;
    }
    return String(component);
  }

  function hint(message) {
    if (/refused|10061|Errno 111/i.test(message)) return 'Nothing accepted the connection. Check the address and port, and that the server is running.';
    if (/timed out|timeout/i.test(message)) return 'The server did not answer in time. It may be offline, behind a firewall, or the timeout is too short.';
    if (/getaddrinfo|Name or service|nodename|Errno -2|11001/i.test(message)) return 'That address could not be found. Check the spelling.';
    if (/Encryption Request|online-mode/i.test(message)) return 'This server needs real Minecraft accounts (online-mode=true). The test player can only join offline-mode servers.';
    if (/Authentication|Request ID/i.test(message)) return 'The server rejected the RCON password, or RCON is not enabled.';
    if (/UDP Query|enable-query/i.test(message)) return 'Query is off or blocked. Set enable-query=true on the server and allow UDP on the game port.';
    return '';
  }

  function stat(key, value, sub) {
    return h('div', { class: 'stat' }, h('div', { class: 'k', text: key }), h('div', { class: 'v', text: value }), sub ? h('div', { class: 's', text: sub }) : null);
  }

  function renderPing(data) {
    const version = data.version || {};
    const players = data.players || {};
    const body = h('div');
    const icon = isIcon(data.favicon) ? h('img', { class: 'server-icon', src: data.favicon, alt: 'Server icon' }) : h('div', { class: 'server-icon empty-icon', text: 'No icon' });
    body.append(h('div', { class: 'server' }, icon, h('div', { class: 'motd', text: clean(flatten(data.description)) || '(no description)' })));
    const readable = version.minecraft_versions ? `Minecraft ${version.minecraft_versions}` : '';
    const online = players.online !== undefined ? `${players.online} / ${players.max !== undefined ? players.max : '?'}` : '?';
    body.append(h('div', { class: 'stats' },
      stat('Version', clean(version.name || 'Unknown'), [readable, version.protocol !== undefined ? `protocol ${version.protocol}` : ''].filter(Boolean).join(' - ')),
      stat('Players', online),
      stat('Response time', data.latency_ms !== undefined ? `${data.latency_ms} ms` : 'Not measured')));
    const sample = Array.isArray(players.sample) ? players.sample.map((p) => clean(p && p.name ? p.name : '')).filter(Boolean) : [];
    if (sample.length) body.append(h('div', { class: 'sub-title', text: 'Players shown by the server' }), h('div', { class: 'tags' }, sample.map((name) => h('span', { class: 'tag', text: name }))));
    const raw = Object.assign({}, data);
    delete raw.favicon;
    body.append(h('details', null, h('summary', { text: 'Show raw data' }), h('pre', { class: 'log', text: JSON.stringify(raw, null, 2) })));
    return body;
  }

  function renderQuery(data) {
    const meta = data.metadata || {};
    const body = h('div');
    const keys = Object.keys(QUERY_LABELS).filter((key) => key in meta).concat(Object.keys(meta).filter((key) => !(key in QUERY_LABELS)));
    const rows = keys.map((key) => h('tr', null, h('th', { text: QUERY_LABELS[key] || key }), h('td', { text: clean(meta[key]) || 'None' })));
    body.append(h('table', { class: 'table' }, h('tbody', null, rows)));
    const players = Array.isArray(data.players) ? data.players : [];
    body.append(h('div', { class: 'sub-title', text: `Players online (${data.player_count !== undefined ? data.player_count : players.length})` }));
    body.append(players.length ? h('div', { class: 'tags' }, players.map((name) => h('span', { class: 'tag', text: clean(name) }))) : h('p', { class: 'dim', text: 'Nobody is online.' }));
    return body;
  }

  function renderGhost(lines) {
    const texts = lines.filter((l) => l.stream === 'out').map((l) => l.text);
    const body = h('div');
    const chat = [];
    const events = [];
    const facts = [];
    const census = [];
    for (const text of texts) {
      let m = /^\[CHAT\] (?:\d\d:\d\d:\d\d )?(packet 0x[0-9A-Fa-f]+ .*)$/.exec(text);
      if (m) { chat.push({ kind: 'undecoded', text: m[1] }); continue; }
      m = /^\[CHAT\] (?:\d\d:\d\d:\d\d )?(?:\((\w+)\) )?(.*)$/.exec(text);
      if (m) { chat.push({ kind: m[1] || 'chat', text: m[2] }); continue; }
      m = /^\[#\] packet (\w+) (0x[0-9A-F]+) count=(\d+) bytes=(\d+) name=(.*)$/.exec(text);
      if (m) { census.push(m.slice(1)); continue; }
      m = /^\[#\] ([^:]+): (.*)$/.exec(text);
      if (m) { facts.push([m[1], m[2]]); continue; }
      if (/^\[[+!]\]/.test(text)) events.push(text.replace(/^\[[+!]\]\s*/, ''));
    }
    body.append(h('div', { class: 'sub-title', text: `Chat seen by the test player (${chat.length})` }));
    if (chat.length) {
      body.append(h('div', { class: 'chat' }, chat.map((msg) => h('div', { class: `msg${msg.kind === 'undecoded' ? ' undecoded' : ''}` }, h('small', { text: msg.kind === 'undecoded' ? 'could not be decoded' : `${msg.kind} chat` }), msg.text))));
    } else {
      body.append(h('p', { class: 'dim', text: 'No chat arrived while the test player was connected.' }));
    }
    if (events.length) body.append(h('div', { class: 'sub-title', text: 'What happened' }), h('ul', { class: 'timeline' }, events.map((text) => h('li', { text }))));
    if (facts.length) {
      body.append(h('div', { class: 'sub-title', text: 'Advanced diagnostics' }), h('table', { class: 'table' }, h('tbody', null, facts.map(([k, v]) => h('tr', null, h('th', { text: k }), h('td', { text: v }))))));
    }
    if (census.length) {
      const head = h('tr', null, ['State', 'Packet', 'Count', 'Bytes', 'Meaning'].map((t) => h('th', { text: t })));
      body.append(h('div', { class: 'sub-title', text: 'Busiest packets' }), h('table', { class: 'table' }, h('tbody', null, head, census.map((row) => h('tr', null, row.map((cell) => h('td', { text: cell })))))));
    }
    body.append(h('details', null, h('summary', { text: 'Show raw output' }), h('pre', { class: 'log', text: texts.join('\n') })));
    return body;
  }

  function renderConsole(lines) {
    const texts = lines.filter((l) => l.stream === 'out').map((l) => l.text);
    const blocks = [];
    for (const text of texts) {
      const m = /^\[>\] (.*)$/.exec(text);
      if (m) blocks.push({ command: m[1], output: [] });
      else if (blocks.length) blocks[blocks.length - 1].output.push(text);
    }
    if (!blocks.length) return null;
    return h('div', null, blocks.map((block) => h('div', { class: 'cmd-block' }, h('div', { class: 'cmd-name', text: `> ${block.command}` }), h('pre', { class: 'log', text: block.output.join('\n') }))));
  }

  function rememberPing(server, data) {
    const players = data.players || {};
    server.online = true;
    server.players = players.online !== undefined ? `${players.online}/${players.max !== undefined ? players.max : '?'}` : '';
    if (isIcon(data.favicon)) server.icon = data.favicon;
    saveServers();
  }

  function startLog() {
    const log = h('pre', { class: 'log' });
    $('result-body').replaceChildren(log);
    return log;
  }

  function appendLines(log, lines) {
    for (const line of lines) log.append(h('span', { class: line.stream === 'err' ? 'err' : '' }, clean(line.text) + '\n'));
    while (log.childNodes.length > 1500) log.removeChild(log.firstChild);
    log.scrollTop = log.scrollHeight;
  }

  function setChip(kind, text) {
    const chip = $('result-chip');
    chip.className = `chip ${kind}`;
    chip.textContent = text;
  }

  function finish(snapshot, lines, log, server, ranTool) {
    const out = lines.filter((l) => l.stream === 'out').map((l) => l.text).join('\n');
    const errors = lines.filter((l) => l.stream === 'err').map((l) => l.text.replace(/^\[!\]\s*/, '')).filter(Boolean);
    const ok = snapshot.exit_code === 0;
    setChip(ok ? 'ok' : 'fail', ok ? `Done in ${snapshot.seconds} s` : 'Failed');
    if (ranTool === 'ping') {
      if (!ok) { server.online = false; server.players = ''; saveServers(); }
    }
    if (!ok) {
      const message = errors.join(' ') || 'The run did not finish.';
      const tip = hint(message);
      $('result-body').replaceChildren(
        h('div', { class: 'notice', role: 'alert' }, h('strong', { text: 'That did not work' }), tip ? h('span', { text: tip }) : null),
        h('details', { open: '' }, h('summary', { text: 'Technical details' }), log));
      return;
    }
    if (ranTool === 'ping' || ranTool === 'query') {
      try {
        const data = JSON.parse(out);
        if (ranTool === 'ping') rememberPing(server, data);
        $('result-body').replaceChildren(ranTool === 'ping' ? renderPing(data) : renderQuery(data));
        return;
      } catch (_) { /* fall through and show the text */ }
    }
    if (ranTool === 'ghost') {
      $('result-body').replaceChildren(renderGhost(lines));
      return;
    }
    if (ranTool === 'rcon') {
      const view = renderConsole(lines);
      if (view) { $('result-body').replaceChildren(view); return; }
    }
    if (snapshot.truncated) log.append(h('span', { class: 'dim', text: '(Output was cut off because it was very long.)\n' }));
    if (!lines.length) log.append(h('span', { class: 'dim', text: '(The server sent no text.)\n' }));
  }

  function collect(server) {
    const payload = { mode: tool, authorized: $('authorized').checked, host: server.host, timeout: $('timeout').value };
    if (tool === 'rcon') {
      payload.rcon_port = String(server.rcon_port);
      payload.password = $('password').value;
      payload.command = $('command').value;
      payload.preset = $('preset').value;
    } else {
      payload.port = String(server.port);
    }
    if (tool === 'ghost') {
      payload.username = $('username').value;
      payload.protocol_version = $('protocol_version').value;
      payload.duration = $('duration').value;
      payload.diagnostics = $('diagnostics').checked;
    }
    return payload;
  }

  async function run() {
    const server = current();
    if ($('run').disabled || !server) return;
    const ranTool = tool;
    busy = true;
    $('run').classList.add('busy');
    renderSelected();
    updateRun();
    $('result').hidden = false;
    $('result-title').textContent = `${TOOLS[ranTool].title} - ${server.name}`;
    setChip('run', 'Running');
    const log = startLog();
    const lines = [];
    try {
      const started = await api('/api/run', { method: 'POST', body: JSON.stringify(collect(server)) });
      let since = 0;
      for (;;) {
        const snapshot = await api(`/api/jobs/${started.job}?since=${since}`);
        since = snapshot.next;
        lines.push(...snapshot.lines);
        appendLines(log, snapshot.lines);
        if (snapshot.done) { finish(snapshot, lines, log, server, ranTool); break; }
        await sleep(350);
      }
    } catch (error) {
      setChip('fail', 'Not started');
      $('result-body').replaceChildren(h('div', { class: 'notice', role: 'alert' }, h('strong', { text: error.message })));
    } finally {
      busy = false;
      $('run').classList.remove('busy');
      refresh();
      $('result').scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }

  // ---- start-up ----
  async function loadVersions() {
    try {
      const data = await api('/api/versions');
      const select = $('protocol_version');
      for (const row of data.versions) {
        if (!row.supported) continue;
        select.append(h('option', { value: String(row.protocol) }, `${row.name} (protocol ${row.protocol})`));
      }
      const saved = readJson(UI_KEY, {}).protocol_version;
      if (saved && [...select.options].some((o) => o.value === saved)) select.value = saved;
    } catch (_) { /* the list stays on "Detect automatically" */ }
  }

  async function loadInfo() {
    try {
      const info = await api('/api/info');
      $('app-version').textContent = `Recon ${info.version}`;
      if (info.limits) {
        $('duration').max = String(info.limits.max_duration_seconds);
        $('timeout').max = String(info.limits.max_timeout_seconds);
      }
      if (info.defaults) {
        if (info.defaults.duration) $('duration').placeholder = String(info.defaults.duration);
        if (info.defaults.timeout) $('timeout').placeholder = String(info.defaults.timeout);
        if (info.defaults.username) $('username').placeholder = String(info.defaults.username);
      }
      for (const preset of info.presets || []) $('preset').append(h('option', { value: String(preset.name) }, String(preset.label)));
      const saved = readJson(UI_KEY, {}).preset;
      if (saved && [...$('preset').options].some((o) => o.value === saved)) $('preset').value = saved;
    } catch (_) { /* optional */ }
  }

  function moveTool(step) {
    const names = Object.keys(TOOLS);
    const next = names[(names.indexOf(tool) + step + names.length) % names.length];
    setTool(next);
    $('tool-list').querySelector(`[data-tool="${next}"]`).focus();
  }

  function moveTile(step) {
    if (!servers.length) return;
    const index = servers.findIndex((s) => s.id === selectedId);
    const next = servers[Math.min(servers.length - 1, Math.max(0, index + step))];
    select(next.id);
    const tile = $('tiles').querySelector(`[data-id="${next.id}"]`);
    if (tile) tile.focus();
  }

  function init() {
    const stored = readJson(SERVERS_KEY, []);
    servers = (Array.isArray(stored) ? stored : []).map(sanitizeServer).filter(Boolean).slice(0, MAX_SERVERS);
    const ui = readJson(UI_KEY, {});
    if (TOOLS[ui.tool]) tool = ui.tool;
    selectedId = servers.some((s) => s.id === ui.selectedId) ? ui.selectedId : (servers.length ? servers[0].id : null);
    for (const id of OPTION_IDS) {
      if (id === 'protocol_version' || id === 'preset') continue;
      $(id).value = (typeof ui[id] === 'string' && ui[id] !== '') ? ui[id] : OPTION_DEFAULTS[id];
    }

    $('tiles').addEventListener('click', (event) => {
      const tile = event.target.closest('.tile');
      if (tile) select(tile.dataset.id);
    });
    $('tiles').addEventListener('dblclick', (event) => {
      const tile = event.target.closest('.tile');
      if (tile) { select(tile.dataset.id); run(); }
    });
    $('tiles').addEventListener('keydown', (event) => {
      if (event.key === 'ArrowRight' || event.key === 'ArrowDown') { event.preventDefault(); moveTile(1); }
      else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') { event.preventDefault(); moveTile(-1); }
    });
    $('tool-list').addEventListener('click', (event) => {
      const button = event.target.closest('.tool');
      if (button) setTool(button.dataset.tool);
    });
    $('tool-list').addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowRight') { event.preventDefault(); moveTool(1); }
      else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') { event.preventDefault(); moveTool(-1); }
    });

    $('btn-add').addEventListener('click', () => { if (!busy) openServerDialog(null); });
    $('btn-add-empty').addEventListener('click', () => openServerDialog(null));
    $('btn-edit').addEventListener('click', () => { const server = current(); if (server && !busy) openServerDialog(server); });
    $('btn-remove').addEventListener('click', () => { if (!busy) askRemove(); });
    $('btn-help').addEventListener('click', () => openDialog($('help-dialog')));
    $('h-close').addEventListener('click', () => closeDialog($('help-dialog')));
    $('f-cancel').addEventListener('click', () => closeDialog($('server-dialog')));
    $('server-form').addEventListener('submit', saveServerForm);
    $('c-cancel').addEventListener('click', () => closeDialog($('confirm-dialog')));
    $('c-ok').addEventListener('click', doRemove);

    $('authorized').addEventListener('change', updateRun);
    for (const id of OPTION_IDS) $(id).addEventListener('change', saveUi);
    $('run').addEventListener('click', run);
    for (const id of ['password', 'command', 'username', 'duration', 'timeout']) {
      $(id).addEventListener('keydown', (event) => { if (event.key === 'Enter') run(); });
    }
    $('toggle-password').addEventListener('click', () => {
      const field = $('password');
      const show = field.type === 'password';
      field.type = show ? 'text' : 'password';
      $('toggle-password').textContent = show ? 'Hide' : 'Show';
      $('toggle-password').setAttribute('aria-pressed', String(show));
    });

    refresh();
    loadVersions().then(saveUi);
    loadInfo().then(saveUi);
  }

  init();
})();
