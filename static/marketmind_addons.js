(function () {
  const $ = (id) => document.getElementById(id);
  function initTheme() {
    const saved = localStorage.getItem('marketmind-theme') || 'dark';
    document.documentElement.dataset.theme = saved;
    const btn = $('themeToggle');
    if (btn) {
      const paint = () => { const light = document.documentElement.dataset.theme === 'light'; btn.textContent = light ? '🌙 Dark mode' : '☀️ Light mode'; btn.setAttribute('aria-label', light ? 'Switch to dark mode' : 'Switch to light mode'); btn.title = light ? 'Switch to dark mode' : 'Switch to light mode'; };
      paint(); btn.addEventListener('click', () => { const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'; document.documentElement.dataset.theme = next; localStorage.setItem('marketmind-theme', next); paint(); });
    }
  }
  function addChatMessage(text, who) {
    const box = $('mmChatMessages'); if (!box) return null;
    const wrap = document.createElement('div'); wrap.className = 'mm-chat-message ' + who;
    const label = document.createElement('div'); label.className = 'mm-chat-message-label'; label.textContent = who === 'user' ? 'You' : 'Market Mind';
    const body = document.createElement('div'); body.className = 'mm-chat-message-body'; body.textContent = text;
    wrap.append(label, body); box.appendChild(wrap); box.scrollTop = box.scrollHeight; return wrap;
  }
  const mmChatHistory = [];
  async function askChat(rawMessage) {
    const message = String(rawMessage || '').trim();
    if (!message || askChat.busy) return;
    askChat.busy = true;
    const input = $('mmChatInput'), send = $('mmChatSend');
    addChatMessage(message, 'user'); mmChatHistory.push({role:'user', content:message}); if (input) { input.value = ''; input.style.height = 'auto'; }
    const loading = addChatMessage('Let me think that through…', 'assistant');
    if (loading) loading.classList.add('mm-chat-loading'); if (send) send.disabled = true;
    let streamedReply = '';
    try {
      const res = await fetch('/api/ai-chat', {method:'POST', headers:{'Content-Type':'application/json','Accept':'application/json'}, body:JSON.stringify({message, history:mmChatHistory.slice(-8)})});
      if (res.headers.get('Content-Type')?.includes('application/x-ndjson')) {
        if (!res.ok) throw new Error('The chat service could not answer. Please try again.');
        const reader = res.body.getReader(), decoder = new TextDecoder();
        const replyBody = loading?.querySelector('.mm-chat-message-body');
        let buffer = '';
        const handleLine = line => {
          if (!line.trim()) return;
          const item = JSON.parse(line);
          if (item.error) throw new Error(item.error);
          if (item.content) {
            streamedReply += item.content;
            if (replyBody) replyBody.textContent = streamedReply;
            if (loading) loading.classList.remove('mm-chat-loading');
            const box = $('mmChatMessages'); if (box) box.scrollTop = box.scrollHeight;
          }
        };
        while (true) {
          const {value, done} = await reader.read();
          buffer += decoder.decode(value || new Uint8Array(), {stream: !done});
          const lines = buffer.split('\n'); buffer = lines.pop() || '';
          lines.forEach(handleLine);
          if (done) break;
        }
        handleLine(buffer);
        if (!streamedReply) throw new Error('Ollama returned an empty answer. Please try again.');
        if (loading) loading.classList.remove('mm-chat-loading');
        mmChatHistory.push({role:'assistant', content:streamedReply});
        return;
      }
      let data; try { data = await res.json(); } catch (_) { throw new Error('The chat service returned an unexpected response. Please refresh and try again.'); }
      if (!res.ok) throw new Error(data.error || 'I could not answer that just now. Please try again.');
      if (loading) loading.remove(); const reply = data.answer || 'I’m sorry — I couldn’t create an answer. Try asking in a different way.'; addChatMessage(reply, 'assistant'); mmChatHistory.push({role:'assistant', content:reply});
    } catch (err) {
      const errorMessage = err.message || 'I could not connect to the assistant. Check that Market Mind is running and try again.';
      if (streamedReply && loading) {
        const replyBody = loading.querySelector('.mm-chat-message-body');
        if (replyBody) replyBody.textContent = `${streamedReply}\n\nAnswer may be incomplete: ${errorMessage}`;
        loading.classList.remove('mm-chat-loading');
      } else {
        if (loading) loading.remove();
        addChatMessage(errorMessage, 'assistant');
      }
    }
    finally { askChat.busy = false; if (send) send.disabled = false; if (input) input.focus(); }
  }
  function initFloatingChat() {
    const panel = $('mmChatPanel'), launcher = $('mmChatLauncher');
    const setOpen = (open) => { if (!panel || !launcher) return; panel.classList.toggle('open', open); launcher.classList.toggle('is-open', open); launcher.setAttribute('aria-expanded', String(open)); panel.setAttribute('aria-hidden', String(!open)); if (open) $('mmChatInput')?.focus(); };
    launcher?.addEventListener('click', () => setOpen(!panel?.classList.contains('open')));
    $('mmChatMinimize')?.addEventListener('click', () => setOpen(false));
    $('mmChatClose')?.addEventListener('click', () => setOpen(false));
    $('mmChatClear')?.addEventListener('click', () => { const box=$('mmChatMessages'); if(box) { box.replaceChildren(); mmChatHistory.length = 0; addChatMessage('New chat started! 😊 What would you like to understand today?', 'assistant'); } });
    $('mmChatForm')?.addEventListener('submit', e => { e.preventDefault(); askChat($('mmChatInput')?.value); });
    $('mmChatInput')?.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('mmChatForm')?.requestSubmit(); } });
    $('mmChatInput')?.addEventListener('input', e => { e.target.style.height='auto'; e.target.style.height=Math.min(e.target.scrollHeight,120)+'px'; });
    document.querySelectorAll('[data-mm-prompt]').forEach(b => b.addEventListener('click', () => askChat(b.dataset.mmPrompt)));
  }
  function fillExplainStocks() { const sector = $('explainSector')?.value || 'IT'; const map = {'IT':['INFY.NS','TCS.NS','WIPRO.NS','HCLTECH.NS'],'Banking':['HDFCBANK.NS','SBIN.NS','ICICIBANK.NS','AXISBANK.NS'],'Pharma':['SUNPHARMA.NS','CIPLA.NS','DRREDDY.NS'],'FMCG':['HINDUNILVR.NS','ITC.NS','NESTLEIND.NS','BRITANNIA.NS']}; const sel = $('explainStock'); if (!sel) return; const prior = sel.value; sel.replaceChildren(); (map[sector] || []).forEach(sym => { const op = document.createElement('option'); op.value = sym; op.textContent = sym.replace('.NS',''); sel.appendChild(op); }); if ((map[sector] || []).includes(prior)) sel.value = prior; }
  async function explainStock() { const result = $('explainResult'); result.innerHTML = '<p>Calculating indicators from local historical prices…</p>'; const sector = $('explainSector').value; const symbol = $('explainStock').value; try { const res = await fetch(`/api/explainable-ai?sector=${encodeURIComponent(sector)}&symbol=${encodeURIComponent(symbol)}`); const d = await res.json(); if (!res.ok) throw new Error(d.error || 'Could not calculate explanation.'); result.replaceChildren(); const summary = document.createElement('p'); summary.className = 'explain-summary'; summary.textContent = d.summary; result.appendChild(summary); const kpis = document.createElement('div'); kpis.className = 'explain-kpis'; [["Latest close", d.latest_close],["Sector",d.sector],["Rows used",d.observations],["Latest date",d.last_date]].forEach(([label,value])=>{const card=document.createElement('div');card.className='explain-kpi';const l=document.createElement('span');l.textContent=label;const v=document.createElement('strong');v.textContent=value ?? '—';card.append(l,v);kpis.appendChild(card)}); result.appendChild(kpis); const table=document.createElement('table'); table.className='feature-table'; table.innerHTML='<thead><tr><th>Factor</th><th>Value</th><th>Interpretation</th></tr></thead>'; const tbody=document.createElement('tbody'); (d.factors||[]).forEach(f=>{const tr=document.createElement('tr');[f.name,`${f.value} ${f.unit}`,f.interpretation].forEach(t=>{const td=document.createElement('td');td.textContent=t;tr.appendChild(td)});tbody.appendChild(tr)}); table.appendChild(tbody);result.appendChild(table); } catch(e) { result.textContent = e.message; } }
  async function loadNews() {
    const out = $('newsResults'), summary = $('newsSummary'), button = $('newsLoad');
    out.textContent = 'Fetching headlines from Yahoo Finance and Google News…';
    summary.replaceChildren();
    if (button) { button.disabled = true; button.textContent = 'Loading news…'; }
    try {
      const res = await fetch(`/api/news-sentiment?symbol=${encodeURIComponent($('newsSymbol').value)}`, {headers:{'Accept':'application/json'}});
      let d;
      try { d = await res.json(); } catch (_) { throw new Error(res.redirected ? 'Your login session may have expired. Log in again and retry.' : `Unexpected response from news service (HTTP ${res.status}).`); }
      if (!res.ok) throw new Error(d.error || `News request failed (HTTP ${res.status}).`);
      summary.replaceChildren();
      const stats = d.total ? [['Overall', d.overall], ['Headlines', d.total], ['Positive', d.counts?.Positive || 0], ['Negative', d.counts?.Negative || 0], ['Neutral', d.counts?.Neutral || 0]] : [['Overall', 'Unavailable'], ['Headlines', 0]];
      stats.forEach(([k,v]) => { const el=document.createElement('div'); el.className='sentiment-stat'; const label=document.createElement('span'); label.textContent=k; const value=document.createElement('strong'); value.textContent=v; el.append(label,value); summary.appendChild(el); });
      out.replaceChildren();
      if (!d.headlines?.length) { const p=document.createElement('p'); p.textContent=d.message || 'No headlines were returned by the available news providers. Try again later.'; out.appendChild(p); return; }
      const note=document.createElement('p'); note.className='feature-note'; note.textContent=d.message || ''; out.appendChild(note);
      d.headlines.forEach(h => { const card=document.createElement('article'); card.className='news-card'; const title=document.createElement(h.url ? 'a' : 'h3'); title.textContent=h.title; if(h.url){title.href=h.url;title.target='_blank';title.rel='noopener noreferrer';} const meta=document.createElement('div');meta.className='news-meta';meta.textContent=`${h.publisher} · ${h.label} sentiment · score ${h.score}`;card.append(title,meta);out.appendChild(card); });
    } catch(e) { out.textContent=e.message || 'Could not load headlines. Check your connection and retry.'; }
    finally { if (button) { button.disabled = false; button.textContent = 'Analyze Latest News'; } }
  }

  document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initFloatingChat();
    $('explainSector')?.addEventListener('change',fillExplainStocks); $('explainRun')?.addEventListener('click',explainStock); fillExplainStocks();
    $('newsLoad')?.addEventListener('click',loadNews);
  });
})();
