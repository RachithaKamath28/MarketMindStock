/* =========================================================
   MarketMind theme helper (UI only).
   - keeps charts (Chart.js + Plotly) in sync with Dark/Light mode
   - smooth theme transition class
   - theme toggle + persistence for the login / register pages
   The main dashboard toggle itself still lives in
   marketmind_addons.js and uses the same localStorage key.
   ========================================================= */
(function () {
  'use strict';
  var KEY = 'marketmind-theme';
  var root = document.documentElement;

  function cssVar(name, fallback) {
    var v = getComputedStyle(root).getPropertyValue(name).trim();
    return v || fallback;
  }
  function isLight() { return root.dataset.theme === 'light'; }
  function pal() {
    var light = isLight();
    return {
      light: light,
      text: cssVar('--text-dim', light ? '#4a5d75' : '#93a6bf'),
      bright: cssVar('--text-bright', light ? '#0d1b2e' : '#f2f7fd'),
      panel: cssVar('--bg-raised', light ? '#ffffff' : '#0a111f'),
      border: cssVar('--border-strong', light ? '#c2d2e3' : '#2a4263'),
      grid: light ? 'rgba(70,100,140,0.14)' : 'rgba(130,172,224,0.12)',
      gridStrong: light ? 'rgba(70,100,140,0.28)' : 'rgba(130,172,224,0.26)'
    };
  }

  /* ---------- smooth transition ---------- */
  var swTimer;
  function beginSwitch() {
    root.classList.add('theme-switching');
    clearTimeout(swTimer);
    swTimer = setTimeout(function () { root.classList.remove('theme-switching'); }, 650);
  }

  /* ---------- Chart.js (defaults only - never touches a chart while it is being built) ---------- */
  function themeChartDefaults() {
    if (!window.Chart || !Chart.defaults) return;
    var p = pal();
    function set(fn) { try { fn(); } catch (e) { /* unsupported in this Chart.js version - ignore */ } }
    set(function () { Chart.defaults.color = p.text; });
    set(function () { Chart.defaults.borderColor = p.grid; });
    set(function () {
      var tip = Chart.defaults.plugins.tooltip;
      tip.backgroundColor = p.light ? 'rgba(13,27,46,0.94)' : 'rgba(7,13,25,0.94)';
      tip.titleColor = '#f2f7fd'; tip.bodyColor = '#cbd8e8';
    });
  }

  function refreshCharts() {
    if (!window.Chart) return;
    themeChartDefaults();
    setTimeout(function () {
      try {
        var inst = Chart.instances || {};
        Object.keys(inst).forEach(function (k) {
          try { if (inst[k] && inst[k].canvas && document.body.contains(inst[k].canvas)) inst[k].update('none'); } catch (e) { /* ignore */ }
        });
      } catch (e) { /* ignore */ }
    }, 0);
  }

  /* ---------- Plotly ---------- */
  // pale trace colours that vanish on a white background -> darker twins for Light Mode
  var LIGHT_SWAP = {
    '#f5d76e': '#b98a00', '#ffd54f': '#c99100', '#7ee787': '#2f9a4a', '#89ddff': '#1b8db8',
    '#80cbc4': '#2a968b', '#ffb86c': '#d9801a', '#c792ea': '#8a55c0', '#ef9a9a': '#cf5a5a',
    '#ff8fab': '#d4577a', '#4dd0e1': '#13899c'
  };
  function swapColor(c, light) {
    if (typeof c !== 'string') return c;
    var k = c.toLowerCase();
    if (light) return LIGHT_SWAP[k] || c;
    for (var from in LIGHT_SWAP) { if (LIGHT_SWAP[from] === k) return from; }
    return c;
  }
  function themePlot(gd) {
    if (!window.Plotly || !gd || !gd.layout) return;
    var p = pal();
    var upd = {
      paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
      'font.color': p.text,
      'hoverlabel.bgcolor': p.panel, 'hoverlabel.bordercolor': p.border, 'hoverlabel.font.color': p.bright
    };
    var keys = Object.keys(gd.layout).filter(function (k) { return /^(x|y)axis\d*$/.test(k); });
    if (keys.indexOf('xaxis') < 0) keys.push('xaxis');
    if (keys.indexOf('yaxis') < 0) keys.push('yaxis');
    keys.forEach(function (k) {
      upd[k + '.gridcolor'] = p.grid; upd[k + '.zerolinecolor'] = p.gridStrong; upd[k + '.linecolor'] = p.gridStrong;
    });
    try { Plotly.relayout(gd, upd); } catch (e) { /* ignore */ }
    try {
      (gd.data || []).forEach(function (tr, i) {
        var line = tr.line && tr.line.color, mk = tr.marker && tr.marker.color;
        var nl = swapColor(line, p.light), nm = swapColor(mk, p.light);
        if (nl !== line) Plotly.restyle(gd, { 'line.color': nl }, [i]);
        if (nm !== mk) Plotly.restyle(gd, { 'marker.color': nm }, [i]);
      });
    } catch (e) { /* ignore */ }
  }
  function refreshPlots() {
    if (!window.Plotly) return;
    document.querySelectorAll('.js-plotly-plot').forEach(themePlot);
  }
  function hookPlotly() {
    if (!window.Plotly || Plotly.__mmThemed) return;
    Plotly.__mmThemed = true;
    ['newPlot', 'react'].forEach(function (fn) {
      var orig = Plotly[fn];
      if (typeof orig !== 'function') return;
      Plotly[fn] = function () {
        var target = arguments[0];
        var res = orig.apply(this, arguments);
        try {
          Promise.resolve(res).then(function (gd) {
            try {
              var el = gd && gd.layout ? gd : (typeof target === 'string' ? document.getElementById(target) : target);
              themePlot(el);
            } catch (e) { /* ignore */ }
          }, function () { /* the original call's own rejection is handled by its caller */ });
        } catch (e) { /* ignore */ }
        return res;
      };
    });
  }

  /* ---------- wiring ---------- */
  function applyAll() { try { refreshCharts(); } catch (e) {} try { refreshPlots(); } catch (e) {} }

  try { hookPlotly(); } catch (e) { /* ignore */ }
  try { themeChartDefaults(); } catch (e) { /* ignore */ }

  // react to ANY change of data-theme (toggle button, other tab, auth page ...)
  new MutationObserver(function () { beginSwitch(); applyAll(); updateAuthButton(); })
    .observe(root, { attributes: true, attributeFilter: ['data-theme'] });

  // start the fade a hair earlier when the dashboard toggle is clicked
  document.addEventListener('click', function (e) {
    var t = e.target && e.target.closest && e.target.closest('#themeToggle, #authThemeToggle');
    if (t) beginSwitch();
  }, true);

  // keep several open tabs in sync
  window.addEventListener('storage', function (e) {
    if (e.key === KEY && e.newValue && e.newValue !== root.dataset.theme) root.dataset.theme = e.newValue;
  });

  /* ---------- login / register toggle ---------- */
  var authBtn = null;
  function updateAuthButton() {
    if (!authBtn) return;
    var light = isLight();
    authBtn.textContent = light ? '\uD83C\uDF19 Dark mode' : '\u2600\uFE0F Light mode';
    authBtn.setAttribute('aria-label', light ? 'Switch to dark mode' : 'Switch to light mode');
    authBtn.title = authBtn.getAttribute('aria-label');
  }
  document.addEventListener('DOMContentLoaded', function () {
    if (!root.dataset.theme) root.dataset.theme = 'dark';
    authBtn = document.getElementById('authThemeToggle');
    if (authBtn) {
      updateAuthButton();
      authBtn.addEventListener('click', function () {
        var next = isLight() ? 'dark' : 'light';
        root.dataset.theme = next;
        try { localStorage.setItem(KEY, next); } catch (e) { /* storage may be blocked */ }
      });
    }
    applyAll();
  });
})();
