/* Smart Flow — dev dashboard
   อ่าน 2 ช่องทางจาก backend: socket `spawn` / `traffic_state` + REST `GET /api/stats`
   ไม่แปลงความหมายของข้อมูลใด ๆ แค่แสดงผล — การตัดสินสถานะเกิดที่ ai-worker แล้ว

   3 หน้า สลับด้วย hash: #overview (ภาพรวมสด) · #state (ตารางทุกหน้าต่าง) · #json (payload ดิบ)
   **ทุก render ทำงานแม้หน้านั้นถูกซ่อนอยู่** — ข้อมูลไหลเข้ามาตลอดไม่ว่าจะเปิดหน้าไหนค้างไว้ */

(function () {
  'use strict';

  var VEHICLE_TYPES = ['car', 'truck', 'motorcycle', 'bus'];
  var TRAFFIC_STATES = ['normal', 'high_density', 'slow_moving', 'standstill'];
  var MAX_FEED_ROWS = 50;
  var MAX_WINDOWS = 120; // 120 ช่วง x 10 วินาที = 20 นาที — พอสำหรับไล่อ่านทั้งรัน
  var MAX_LOG_ROWS = 100;
  var MAX_SPARK_POINTS = 30;
  var SPARK_W = 140;
  var SPARK_H = 40;
  var SPARK_PAD = 3; // กันเส้นชนขอบบน/ล่างของ viewBox

  var PAGES = {
    overview: { title: 'Live Monitor', sub: 'Realtime feed from AI Worker · Prototype' },
    state: { title: 'Traffic state', sub: 'Every window with its measured values and verdict' },
    json: { title: 'Raw payloads', sub: 'Everything arriving on the spawn and traffic_state channels' },
  };
  var DEFAULT_PAGE = 'overview';

  var windows = []; // payload traffic_state ที่ได้รับ เรียงตามเวลา — ใช้ทั้ง timeline และตารางหน้า state
  var zoneCards = {}; // ชื่อโซน -> element ที่สร้างไว้แล้ว (ไม่สร้างใหม่ทุกรอบ กันกระพริบ)
  var rawLog = []; // {channel, at, payload} ใหม่สุดอยู่หน้า array
  var logTotals = { spawn: 0, traffic_state: 0 }; // นับสะสมจริง ไม่ใช่แค่ที่ยังเก็บไว้
  var logFilter = 'all';
  var lastStateAt = null;

  var el = function (id) {
    return document.getElementById(id);
  };

  // ---------------------------------------------------------------- router

  function showPage(name) {
    if (!PAGES[name]) name = DEFAULT_PAGE;

    Object.keys(PAGES).forEach(function (key) {
      el('page-' + key).hidden = key !== name;
    });

    Array.prototype.forEach.call(document.querySelectorAll('.nav a'), function (link) {
      link.classList.toggle('active', link.dataset.page === name);
    });

    el('page-title').textContent = PAGES[name].title;
    el('page-sub').textContent = PAGES[name].sub;
  }

  function currentPage() {
    return window.location.hash.replace(/^#/, '') || DEFAULT_PAGE;
  }

  window.addEventListener('hashchange', function () {
    showPage(currentPage());
  });

  // ---------------------------------------------------------------- socket

  var socket = io();

  socket.on('connect', function () {
    el('status').classList.add('online');
    el('status-label').textContent = 'connected';
  });

  socket.on('disconnect', function () {
    el('status').classList.remove('online');
    el('status-label').textContent = 'disconnected — retrying…';
  });

  socket.on('spawn', function (event) {
    addFeedRow(event);
    logRaw('spawn', event, describeSpawn(event));
    fetchStats();
  });

  socket.on('traffic_state', function (payload) {
    windows.push(payload);
    if (windows.length > MAX_WINDOWS) windows.shift();
    lastStateAt = Date.now();

    renderCurrentState(payload);
    renderTimeline();
    renderZones(payload);
    renderStatePage();
    logRaw('traffic_state', payload, describeWindow(payload));
    el('stat-windows').textContent = String(windows.length);
  });

  // ---------------------------------------------------------------- current state

  function renderCurrentState(payload) {
    el('state-chip').dataset.state = payload.trafficState;
    el('state-name').textContent = payload.trafficState.replace(/_/g, ' ');
    el('state-window').textContent =
      payload.windowStartSec.toFixed(0) + '–' + payload.windowEndSec.toFixed(0) + 's';
  }

  function renderStateAge() {
    if (lastStateAt === null) return;
    var secs = Math.round((Date.now() - lastStateAt) / 1000);
    el('state-age').textContent = secs < 1 ? 'just now' : secs + 's ago';
  }

  setInterval(renderStateAge, 1000);

  // ---------------------------------------------------------------- timeline

  /** คำตัดสินของโซนนั้น — worker ก่อน 1.5.0 ไม่ส่งมา ให้ตกกลับไปใช้ค่ารวม */
  function zoneStateOf(w, name) {
    var zone = w.zones[name];
    return (zone && zone.trafficState) || w.trafficState;
  }

  function renderTimeline() {
    el('timeline-empty').hidden = true;
    el('timeline-wrap').hidden = false;

    var rows = el('timeline-rows');
    rows.textContent = '';

    // แถบละโซน — ช่วงที่ขาออกติดแต่ขาเข้าโล่ง แถบเดียวจะมองไม่เห็นเลย
    zoneNames().forEach(function (name) {
      var row = document.createElement('div');
      row.className = 'tl-row';
      row.appendChild(span('tl-label', name));

      var bar = document.createElement('div');
      bar.className = 'timeline';

      windows.forEach(function (w) {
        var seg = document.createElement('div');
        seg.className = 'seg';
        seg.dataset.state = zoneStateOf(w, name);
        // สีอย่างเดียวแยกสถานะข้างเคียงยากถ้าตาบอดสี — tooltip จึงบอกชื่อสถานะเสมอ
        seg.title = describeZoneWindow(w, name);
        bar.appendChild(seg);
      });

      row.appendChild(bar);
      rows.appendChild(row);
    });

    var first = windows[0];
    var last = windows[windows.length - 1];
    el('timeline-start').textContent = first.windowStartSec.toFixed(0) + 's';
    el('timeline-end').textContent = last.windowEndSec.toFixed(0) + 's';
    el('timeline-note').textContent =
      windows.length + (windows.length === 1 ? ' window' : ' windows');
  }

  function describeZoneWindow(w, name) {
    var zone = w.zones[name];
    var head =
      w.windowStartSec.toFixed(0) + '–' + w.windowEndSec.toFixed(0) + 's · ' + name + ' · ';
    if (!zone) return head + 'no data';
    return (
      head +
      zoneStateOf(w, name) +
      ' · occ ' +
      zone.occupancy.toFixed(2) +
      ' · veh ' +
      zone.vehicleFlowRate.toFixed(1) +
      '/min'
    );
  }

  function describeWindow(w) {
    var parts = Object.keys(w.zones).map(function (name) {
      return name + ' ' + w.zones[name].occupancy.toFixed(2);
    });
    return (
      w.windowStartSec.toFixed(0) +
      '–' +
      w.windowEndSec.toFixed(0) +
      's · ' +
      w.trafficState +
      ' · occ ' +
      parts.join(' / ')
    );
  }

  function describeSpawn(event) {
    return event.trackId + ' · ' + event.type + ' · ' + event.direction;
  }

  // ---------------------------------------------------------------- zones

  function renderZones(payload) {
    el('zones-empty').hidden = true;

    // สร้างการ์ดจากโซนที่ payload ส่งมาจริง ไม่ fix เป็น in/out
    // เพราะถนนทางเดียวมีโซนเดียวได้ตาม docs/data-contract.md §2d
    Object.keys(payload.zones).forEach(function (name) {
      var zone = payload.zones[name];
      var card = zoneCards[name] || createZoneCard(name);

      card.occ.textContent = zone.occupancy.toFixed(2);
      card.veh.textContent = zone.vehicleFlowRate.toFixed(1);
      // motorcycleFlowRate ไม่บังคับใน contract 1.4.0 — worker รุ่นเก่าไม่ส่งมา
      card.mc.textContent = (zone.motorcycleFlowRate || 0).toFixed(1);

      var state = zoneStateOf(payload, name);
      card.verdict.dataset.state = state;
      card.verdictText.textContent = state.replace(/_/g, ' ');

      card.history.push(zone.occupancy);
      if (card.history.length > MAX_SPARK_POINTS) card.history.shift();
      drawSparkline(card);
    });
  }

  function createZoneCard(name) {
    var node = document.createElement('div');
    node.className = 'card zone';
    node.innerHTML =
      '<div class="zone-head"><span class="zone-name"></span>' +
      '<span class="verdict"><i></i><span class="verdict-text">—</span></span></div>' +
      '<div class="zone-main">' +
      '<div><div class="zone-occ">—</div><div class="zone-occ-label">occupancy</div></div>' +
      '<div class="spark-wrap">' +
      '<svg class="spark" width="' + SPARK_W + '" height="' + SPARK_H + '" ' +
      'viewBox="0 0 ' + SPARK_W + ' ' + SPARK_H + '" aria-hidden="true"></svg>' +
      '<div class="spark-range"></div>' +
      '</div></div>' +
      '<div class="zone-flows">' +
      '<div class="flow is-key"><div class="k">vehicle flow /min</div><div class="v">—</div></div>' +
      '<div class="flow"><div class="k">motorcycle /min</div><div class="v">—</div></div>' +
      '</div>';

    node.querySelector('.zone-name').textContent = name;

    var flows = node.querySelectorAll('.flow .v');
    var card = {
      node: node,
      occ: node.querySelector('.zone-occ'),
      veh: flows[0],
      mc: flows[1],
      svg: node.querySelector('.spark'),
      range: node.querySelector('.spark-range'),
      verdict: node.querySelector('.verdict'),
      verdictText: node.querySelector('.verdict-text'),
      history: [],
    };

    zoneCards[name] = card;
    el('zone-grid').appendChild(node);
    return card;
  }

  function drawSparkline(card) {
    var values = card.history;
    if (values.length < 2) {
      card.svg.innerHTML = '';
      card.range.textContent = 'collecting…';
      return;
    }

    var min = Math.min.apply(null, values);
    var max = Math.max.apply(null, values);
    var span = max - min || 1; // ค่าคงที่ทั้งชุด -> วาดเป็นเส้นตรงกลางแทนหารศูนย์
    var usable = SPARK_H - SPARK_PAD * 2;

    var points = values.map(function (v, i) {
      var x = (i / (values.length - 1)) * SPARK_W;
      var y = SPARK_H - SPARK_PAD - ((v - min) / span) * usable;
      return x.toFixed(1) + ',' + y.toFixed(1);
    });

    var tail = points[points.length - 1].split(',');
    card.svg.innerHTML =
      '<polyline fill="none" stroke="var(--accent)" stroke-width="2" ' +
      'stroke-linejoin="round" stroke-linecap="round" points="' + points.join(' ') + '" />' +
      '<circle cx="' + tail[0] + '" cy="' + tail[1] + '" r="3" fill="var(--accent)" />';

    card.range.textContent = 'min ' + min.toFixed(2) + ' · max ' + max.toFixed(2);
  }

  // ---------------------------------------------------------------- state page

  /** ชื่อโซนทั้งหมดที่เคยเห็น — หัวตารางสร้างจากอันนี้ ไม่ fix เป็น in/out */
  function zoneNames() {
    var seen = [];
    windows.forEach(function (w) {
      Object.keys(w.zones).forEach(function (name) {
        if (seen.indexOf(name) === -1) seen.push(name);
      });
    });
    return seen;
  }

  function renderStatePage() {
    el('state-empty').hidden = true;
    el('state-table-wrap').hidden = false;
    renderStateSummary();
    renderStateTable(zoneNames());
  }

  function renderStateSummary() {
    var counts = {};
    windows.forEach(function (w) {
      counts[w.trafficState] = (counts[w.trafficState] || 0) + 1;
    });

    var total = windows.length || 1;
    var box = el('state-summary');
    box.textContent = '';

    // แสดงครบทั้ง 4 สถานะเสมอแม้จะเป็น 0 เพื่อให้เลย์เอาต์นิ่งและเห็นว่าอะไรยังไม่เคยเกิด
    TRAFFIC_STATES.forEach(function (state) {
      var n = counts[state] || 0;
      var card = document.createElement('div');
      card.className = 'card stat state-sum';
      card.dataset.state = state;
      card.innerHTML =
        '<div class="label"><i></i></div><div class="value"></div><div class="sub"></div>';
      card.querySelector('.label').appendChild(document.createTextNode(state.replace(/_/g, ' ')));
      card.querySelector('.value').textContent = String(n);
      card.querySelector('.sub').textContent =
        Math.round((n / total) * 100) + '% of ' + windows.length;
      box.appendChild(card);
    });
  }

  function renderStateTable(names) {
    var head = el('state-thead');
    head.textContent = '';
    var hr = document.createElement('tr');
    hr.appendChild(th('window'));
    names.forEach(function (name) {
      hr.appendChild(th(name + ' occ', 'zone-sep'));
      hr.appendChild(th(name + ' veh'));
      hr.appendChild(th(name + ' mc'));
      hr.appendChild(th(name + ' state'));
    });
    hr.appendChild(th('overall', 'zone-sep'));
    head.appendChild(hr);

    var body = el('state-tbody');
    body.textContent = '';

    // เรียงเก่า -> ใหม่ ให้ตรงกับ timeline และกับผลที่ replay --fast พิมพ์
    windows.forEach(function (w) {
      var tr = document.createElement('tr');

      // วินาทีดิบไว้เทียบกับ log ของ replay · m:ss ไว้เลื่อนหาในวิดีโอ
      var win = document.createElement('td');
      win.className = 'win';
      win.appendChild(
        span('sec', w.windowStartSec.toFixed(0) + '–' + w.windowEndSec.toFixed(0) + 's')
      );
      win.appendChild(span('mmss', mmss(w.windowStartSec) + '–' + mmss(w.windowEndSec)));
      tr.appendChild(win);

      names.forEach(function (name) {
        var z = w.zones[name];
        tr.appendChild(td(z ? z.occupancy.toFixed(2) : '—', 'zone-sep'));
        tr.appendChild(td(z ? z.vehicleFlowRate.toFixed(1) : '—'));
        tr.appendChild(td(z ? (z.motorcycleFlowRate || 0).toFixed(1) : '—'));
        tr.appendChild(z ? verdictCell(zoneStateOf(w, name)) : td('—'));
      });

      tr.appendChild(verdictCell(w.trafficState, 'zone-sep'));

      body.appendChild(tr);
    });
  }

  function verdictCell(state, cls) {
    var cell = document.createElement('td');
    if (cls) cell.className = cls;
    var chip = document.createElement('span');
    chip.className = 'verdict';
    chip.dataset.state = state;
    chip.innerHTML = '<i></i>';
    chip.appendChild(document.createTextNode(state.replace(/_/g, ' ')));
    cell.appendChild(chip);
    return cell;
  }

  /** 130.0 -> "2:10" — ปัดวินาทีรวมก่อนค่อยหาร ไม่งั้น 119.7 จะกลายเป็น "1:60" */
  function mmss(sec) {
    var total = Math.round(sec);
    var s = total % 60;
    return Math.floor(total / 60) + ':' + (s < 10 ? '0' : '') + s;
  }

  function th(text, cls) {
    var node = document.createElement('th');
    node.textContent = text;
    if (cls) node.className = cls;
    return node;
  }

  function td(text, cls) {
    var node = document.createElement('td');
    node.textContent = text;
    if (cls) node.className = cls;
    return node;
  }

  // ---------------------------------------------------------------- json page

  function logRaw(channel, payload, summary) {
    logTotals[channel] += 1;
    el('count-' + channel).textContent = String(logTotals[channel]);
    el('count-all').textContent = String(logTotals.spawn + logTotals.traffic_state);

    var entry = { channel: channel, at: Date.now(), payload: payload, summary: summary };
    rawLog.unshift(entry);
    if (rawLog.length > MAX_LOG_ROWS) rawLog.pop();

    if (logFilter !== 'all' && logFilter !== channel) return;

    el('json-empty').hidden = true;
    var list = el('json-log');
    list.prepend(buildLogRow(entry));
    while (list.childElementCount > MAX_LOG_ROWS) {
      list.removeChild(list.lastElementChild);
    }
  }

  function buildLogRow(entry) {
    var row = document.createElement('div');
    row.className = 'log-row';

    var head = document.createElement('div');
    head.className = 'log-head';
    head.appendChild(span('time', new Date(entry.at).toLocaleTimeString()));

    var badge = span('channel', entry.channel);
    badge.dataset.channel = entry.channel;
    head.appendChild(badge);
    head.appendChild(span('summary', entry.summary));

    var pre = document.createElement('pre');
    pre.textContent = JSON.stringify(entry.payload, null, 2);

    row.appendChild(head);
    row.appendChild(pre);
    return row;
  }

  function renderLog() {
    var shown = rawLog.filter(function (entry) {
      return logFilter === 'all' || entry.channel === logFilter;
    });

    var list = el('json-log');
    list.textContent = '';
    shown.forEach(function (entry) {
      list.appendChild(buildLogRow(entry));
    });

    el('json-empty').hidden = shown.length > 0;
    el('json-empty').textContent = rawLog.length
      ? 'Nothing on this channel yet.'
      : 'Nothing received yet…';
  }

  el('json-filter').addEventListener('click', function (ev) {
    var btn = ev.target.closest('button');
    if (!btn) return;
    logFilter = btn.dataset.filter;
    Array.prototype.forEach.call(this.querySelectorAll('button'), function (b) {
      b.classList.toggle('active', b === btn);
    });
    renderLog();
  });

  // ---------------------------------------------------------------- feed

  function addFeedRow(event) {
    el('feed-empty').hidden = true;

    var row = document.createElement('details');
    row.className = 'feed-row flash';

    var summary = document.createElement('summary');
    summary.appendChild(span('time', event.timestamp ? timeOf(event.timestamp) : '—'));

    var chip = span('chip', event.type);
    chip.dataset.type = event.type;
    summary.appendChild(chip);

    summary.appendChild(span('track', event.trackId));
    summary.appendChild(span('dir', event.direction));
    summary.appendChild(
      span('conf', typeof event.confidence === 'number' ? event.confidence.toFixed(2) : '—')
    );

    var pre = document.createElement('pre');
    pre.textContent = JSON.stringify(event, null, 2);

    row.appendChild(summary);
    row.appendChild(pre);

    var list = el('feed-list');
    list.prepend(row);
    while (list.childElementCount > MAX_FEED_ROWS) {
      list.removeChild(list.lastElementChild);
    }
  }

  function span(cls, text) {
    var node = document.createElement('span');
    node.className = cls;
    node.textContent = text;
    return node;
  }

  function timeOf(iso) {
    var d = new Date(iso);
    return isNaN(d.getTime()) ? '—' : d.toLocaleTimeString();
  }

  // ---------------------------------------------------------------- stats

  function buildTypeRows() {
    var body = el('type-rows');
    VEHICLE_TYPES.forEach(function (type) {
      var tr = document.createElement('tr');
      var cell = document.createElement('td');
      var chip = span('chip', type);
      chip.dataset.type = type;
      cell.appendChild(chip);
      tr.appendChild(cell);

      ['in', 'out', 'total'].forEach(function (key) {
        var node = document.createElement('td');
        node.id = 'stat-' + type + '-' + key;
        if (key === 'total') node.className = 'total';
        node.textContent = '—';
        tr.appendChild(node);
      });

      body.appendChild(tr);
    });
  }

  function renderStats(stats) {
    el('stat-all').textContent = stats.totals.all;
    el('stat-in').textContent = stats.totals.in;
    el('stat-out').textContent = stats.totals.out;
    el('meta-camera').textContent = stats.cameraId || '—';
    el('meta-since').textContent = stats.since ? timeOf(stats.since) : '—';

    VEHICLE_TYPES.forEach(function (type) {
      var counts = stats.byType[type] || { in: 0, out: 0 };
      el('stat-' + type + '-in').textContent = counts.in;
      el('stat-' + type + '-out').textContent = counts.out;
      el('stat-' + type + '-total').textContent = counts.in + counts.out;
    });
  }

  function fetchStats() {
    fetch('/api/stats')
      .then(function (res) {
        return res.json();
      })
      .then(renderStats)
      .catch(function (err) {
        console.error('[dashboard] fetch /api/stats failed:', err);
      });
  }

  el('reset-btn').addEventListener('click', function () {
    if (!window.confirm('Reset all in-memory counters to zero?')) return;
    fetch('/api/stats/reset', { method: 'POST' })
      .then(fetchStats)
      .catch(function (err) {
        console.error('[dashboard] reset failed:', err);
      });
  });

  // ---------------------------------------------------------------- start

  buildTypeRows();
  renderStateSummary(); // ให้ชิปสรุป 4 สถานะขึ้นตั้งแต่ยังไม่มีข้อมูล
  showPage(currentPage());
  fetchStats();
})();
