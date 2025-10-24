(function(){
  // defaults
  const INITIAL_TAIL_LINES = 200;
  let websocket = null;
  let isPaused = false;
  let reconnectAttempts = 0;
  const MAX_RECONNECT = 6;

  // client state
  let selectedLevels = new Set();
  let pollTimer = null;
  let currentKeyword = '';
  let headerSearch = '';
  let currentLines = INITIAL_TAIL_LINES;
  let currentIntervalMs = 5000;
  let sortColumn = null;
  let sortDirection = -1; // default newest first for ts

  // util
  function qsDecode(s){ try{ return decodeURIComponent(s.replace(/\+/g,' ')); }catch(e){ return s; } }
  function escapeHtml(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function debounce(fn, wait){ let t = null; return function(){ const ctx = this; const args = arguments; clearTimeout(t); t = setTimeout(()=> fn.apply(ctx, args), wait); }; }
  function highlightText(text, kw){ if(!kw) return escapeHtml(text); try{ const esc = (kw+'').replace(/[.*+?^${}()|[\\]\\]/g,'\\$&'); const re = new RegExp('('+esc+')','gi'); return escapeHtml(text).replace(re, '<mark class="log-highlight">$1</mark>'); }catch(e){ return escapeHtml(text); } }

  // DOM helpers
  function el(id){ return document.getElementById(id); }

  // return selected file basename from select (or null)
  function getSelectedFile(){
    try{
      const sel = document.getElementById('logFileSelect');
      if(sel && sel.value) return sel.value;
    }catch(e){}
    return null;
  }

  function _buildWsUrl(){
    const loc = window.location;
    const protocol = (loc.protocol === 'https:') ? 'wss:' : 'ws:';
    const base = protocol + '//' + loc.host + '/ws/logging-tail';
    const t = (el('wsToken')||{}).value;
    const file = getSelectedFile();
    const params = new URLSearchParams();
    if (t) params.set('token', t);
    if (file) params.set('file', file);
    const q = params.toString();
    return base + (q ? ('?'+q) : '');
  }

  function clearLogTable(){
    try{
      const tbody = el('logTableBody'); if (tbody) tbody.innerHTML = '';
      const totalEl = el('totalLogs'); if (totalEl) totalEl.textContent = '0';
      const lastUpdateEl = el('lastUpdate'); if (lastUpdateEl) lastUpdateEl.textContent = '';
      el('pauseBtn').disabled = false; el('resumeBtn').disabled = true;
    }catch(e){ console.error('clearLogTable', e); }
  }

  function _stopPoll(){ if (pollTimer){ clearInterval(pollTimer); pollTimer = null; } }
  function _restartPollIfNeeded(){ _stopPoll(); if (!websocket && (el('autoPoll') && el('autoPoll').checked)){ pollTimer = setInterval(_sendReloadRequest, currentIntervalMs); } }

  function connectWebSocket(userInitiated=false){
    if (websocket) return;
    clearLogTable();
    const url = _buildWsUrl();
    try{
      websocket = new WebSocket(url);
      websocket.onopen = ()=>{
        reconnectAttempts = 0;
        const s = el('wsStatus'); if (s) s.className = 'w-3 h-3 bg-green-500 rounded-full';
        const st = el('wsStatusText'); if (st) st.textContent = 'WS 연결됨';
        el('connectBtn').disabled = true; el('disconnectBtn').disabled = false;
        _stopPoll();
      };
      websocket.onmessage = (ev)=>{ if(!isPaused){ try{ const data = JSON.parse(ev.data); if (data && data.type === 'line') addLogEntry(data); }catch(e){ console.error('ws parse',e); } } };
      websocket.onclose = ()=>{ websocket = null; const s = el('wsStatus'); if (s) s.className='w-3 h-3 bg-red-500 rounded-full'; const st = el('wsStatusText'); if (st) st.textContent='WS 연결 해제됨'; el('connectBtn').disabled=false; el('disconnectBtn').disabled=true; _restartPollIfNeeded(); if(el('autoReconnect') && el('autoReconnect').checked) _scheduleReconnect(); };
      websocket.onerror = ()=>{ const s = el('wsStatus'); if (s) s.className='w-3 h-3 bg-yellow-500 rounded-full'; const st = el('wsStatusText'); if (st) st.textContent='WS 연결 오류'; };
    }catch(err){ console.error('WebSocket 연결 실패:', err); if(el('autoReconnect') && el('autoReconnect').checked) _scheduleReconnect(); }
  }

  function _scheduleReconnect(){ if (reconnectAttempts >= MAX_RECONNECT) return; reconnectAttempts += 1; const delay = Math.min(30000, 500 * Math.pow(2, reconnectAttempts)); const st = el('wsStatusText'); if(st) st.textContent = `재연결 시도 중 (${reconnectAttempts}/${MAX_RECONNECT}) ...`; setTimeout(()=>{ connectWebSocket(false); }, delay); }
  function disconnectWebSocket(){ if (websocket){ websocket.close(); websocket = null; } }

  function parseTsMs(tsStr){ if(!tsStr) return NaN; try{ const s = tsStr.replace('T',' '); const d = new Date(s); if(!isNaN(d)) return d.getTime(); return NaN; }catch(e){ return NaN; } }

  // format Date ms -> input[type=datetime-local] string 'YYYY-MM-DDTHH:MM'
  function formatDateTimeLocal(ms){ try{ const d = new Date(ms); const pad = (n)=> n.toString().padStart(2,'0'); const YYYY = d.getFullYear(); const MM = pad(d.getMonth()+1); const DD = pad(d.getDate()); const hh = pad(d.getHours()); const mm = pad(d.getMinutes()); const ss = pad(d.getSeconds()); return `${YYYY}-${MM}-${DD}T${hh}:${mm}:${ss}`; }catch(e){ return ''; } }

  function sortTable(col, forceDir){
    const tbody = el('logTableBody'); if(!tbody) return;
    const rows = Array.from(tbody.children);
    if(!col) return;
    if (typeof forceDir !== 'undefined'){
      sortDirection = forceDir;
      sortColumn = col;
    } else {
      if (sortColumn === col){ sortDirection = -sortDirection; } else { sortColumn = col; sortDirection = (col === 'ts' ? -1 : 1); }
    }
    rows.sort((a,b)=>{
      if(col==='ts'){ const ta = parseTsMs(a.dataset.rawTs||''); const tb = parseTsMs(b.dataset.rawTs||''); return (ta - tb) * sortDirection; }
      if(col==='level'){ const pri={'ERROR':4,'WARNING':3,'INFO':2,'DEBUG':1}; const la = pri[(a.dataset.rawLevel||'').toUpperCase()]||0; const lb = pri[(b.dataset.rawLevel||'').toUpperCase()]||0; return (la - lb) * sortDirection; }
      const ma = (a.dataset.rawMsg||'').toLowerCase(); const mb = (b.dataset.rawMsg||'').toLowerCase(); if(ma<mb) return -1*sortDirection; if(ma>mb) return 1*sortDirection; return 0;
    });
    rows.forEach(r=>tbody.appendChild(r));
    // toggle UI elements when sort is active
    try{ if(typeof updateHiddenOnSort === 'function') updateHiddenOnSort(); }catch(e){}
  }

  // Hide/show certain UI controls when a sort is active
  function updateHiddenOnSort(){
    try{
      const shouldHide = !!sortColumn;
      // specific IDs
      const ids = [];
      ids.forEach(id=>{ const elNode = document.getElementById(id); if(elNode) elNode.hidden = shouldHide; });
      // class-based selectors: hide any elements marked for hiding on sort
      const nodes = document.querySelectorAll('.hide-on-sort');
      nodes.forEach(n=>{ n.hidden = shouldHide; });
      // Note: do NOT globally hide .sort-asc/.sort-desc here — visibility for sort arrows
      // is managed per-column by updateSortToggle(). 
    }catch(e){ console.error('updateHiddenOnSort error', e); }
  }

  // Manage visibility of asc/desc buttons per column: when ascending is active hide asc and show desc, and vice versa.
  function updateSortToggle(col, dir){
    try{
      if(!col) return;
      const ascBtns = document.querySelectorAll('.sort-asc[data-col="'+col+'"]');
      const descBtns = document.querySelectorAll('.sort-desc[data-col="'+col+'"]');
      if(dir === 1){ // asc requested -> hide asc, show desc
        ascBtns.forEach(b=>{ b.hidden = true; });
        descBtns.forEach(b=>{ b.hidden = false; });
      } else if(dir === -1){ // desc requested -> show asc, hide desc
        ascBtns.forEach(b=>{ b.hidden = false; });
        descBtns.forEach(b=>{ b.hidden = true; });
      }
    }catch(e){ console.error('updateSortToggle error', e); }
  }

  function applyFilter(){
    const kw = (currentKeyword||'').toLowerCase();
    const hs = (headerSearch||'').toLowerCase();
    const tbody = el('logTableBody'); if(!tbody) return;
    const levelFilterActive = selectedLevels.size > 0;
    const startVal = (el('startTs') && el('startTs').value) ? new Date(el('startTs').value).getTime() : null;
    const endVal = (el('endTs') && el('endTs').value) ? new Date(el('endTs').value).getTime() : null;
    Array.from(tbody.children).forEach(function(row){
      const raw = row.dataset.rawMsg || '';
      const level = (row.dataset.rawLevel||'').toUpperCase();
      const tsRaw = row.dataset.rawTs || '';
      const tsMs = parseTsMs(tsRaw);
      const combined = (row.dataset.rawTs || '') + ' ' + level + ' ' + raw;
      const kwMatched = !kw || combined.toLowerCase().indexOf(kw) !== -1;
      const levelMatched = !levelFilterActive || selectedLevels.has(level);
      const tsMatched = (startVal===null || isNaN(startVal) ? true : (tsMs >= startVal)) && (endVal===null || isNaN(endVal) ? true : (tsMs <= endVal));
      const msgCell = row.querySelector('td:nth-child(3)'); if(msgCell) msgCell.innerHTML = highlightText(raw, currentKeyword);
      // headerSearch (msgSearch) 적용: 메시지 컬럼에 대해 별도 검사
      const headerMatched = !hs || (raw||'').toLowerCase().indexOf(hs) !== -1;
      row.style.display = (kwMatched && levelMatched && tsMatched && headerMatched) ? '' : 'none';
    });
    if(sortColumn) sortTable(sortColumn);
  }

  function addLogEntry(logData){
    const tbody = el('logTableBody'); if(!tbody) return;
    const row = document.createElement('tr'); row.className = 'hover:bg-gray-50';
    const level = (logData.level||'').toUpperCase();
    const levelClass = level === 'ERROR' ? 'bg-red-100 text-red-800' : (level === 'WARNING' ? 'bg-yellow-100 text-yellow-800' : 'bg-blue-100 text-blue-800');
    const ts = logData.ts || new Date().toLocaleString('ko-KR');
    const msgRaw = (logData.msg || logData.message || '');

    row.dataset.rawMsg = msgRaw;
    row.dataset.rawTs = ts;
    row.dataset.rawLevel = level;

    const highlighted = highlightText(msgRaw, currentKeyword);
    row.innerHTML = `\n      <td class="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-900">${escapeHtml(ts)}</td>\n      <td class="px-6 py-4 whitespace-nowrap"><span class="inline-flex px-2 py-1 text-xs font-semibold rounded-full ${levelClass}">${escapeHtml(level)}</span></td>\n      <td class="px-6 py-4 text-sm font-mono text-gray-900"><div class='log-msg'>${highlighted}</div></td>\n    `;

    const msgDiv = row.querySelector('.log-msg');
    if(msgDiv){
      msgDiv.addEventListener('click', function(){ this.classList.toggle('expanded'); });
    }

    tbody.insertBefore(row, tbody.firstChild);
    el('lastUpdate').textContent = new Date().toLocaleString('ko-KR');
    const totalEl = el('totalLogs'); totalEl.textContent = parseInt(totalEl.textContent||'0') + 1;

    // apply current filter immediately
    const kw = (currentKeyword||'').toLowerCase();
    const combined = (ts + ' ' + level + ' ' + msgRaw).toLowerCase();
    const kwMatched = !kw || combined.indexOf(kw) !== -1;
    const levelMatched = selectedLevels.size === 0 || selectedLevels.has((level||'').toUpperCase());
    if (!(kwMatched && levelMatched)) row.style.display = 'none';
  }

  function _buildFilterPayload(){
    const payload = { lines: currentLines };
    if (currentKeyword) payload.keyword = currentKeyword;
    if (selectedLevels && selectedLevels.size) payload.levels = Array.from(selectedLevels);
    if (el('startTs') && el('startTs').value){ try{ payload.start = String(new Date(el('startTs').value).getTime()); }catch(e){} }
    if (el('endTs') && el('endTs').value){ try{ payload.end = String(new Date(el('endTs').value).getTime()); }catch(e){} }
    const file = getSelectedFile();
    if (file) payload.file = file;
    return payload;
  }

  function _sendReloadRequest(){
    const payload = _buildFilterPayload();
    if (websocket){
      try{ websocket.send(JSON.stringify(Object.assign({cmd:'reload_tail'}, payload))); return; }catch(e){ console.error('WS send failed', e); }
    }
    const params = new URLSearchParams(); params.set('lines', String(payload.lines || currentLines));
    if (payload.keyword) params.set('keyword', payload.keyword);
    if (payload.levels && payload.levels.length) params.set('level', payload.levels.join(','));
    if (payload.start) params.set('start', payload.start);
    if (payload.end) params.set('end', payload.end);
    if (payload.file) params.set('file', payload.file);
    fetch('/ws/logging-tail?' + params.toString(), {credentials: 'same-origin'})
      .then(function(resp){ if(!resp.ok) throw new Error('HTTP ' + resp.status); return resp.json(); })
      .then(function(data){ clearLogTable(); if (!Array.isArray(data)) return; data.forEach(function(entry){ addLogEntry(entry); }); })
      .catch(function(err){ console.error('fetchTailHttp error', err); });
  }

  function init(){
    document.addEventListener('DOMContentLoaded', function(){
      try{
        const connectBtn = el('connectBtn'); const disconnectBtn = el('disconnectBtn');
        const pauseBtn = el('pauseBtn'); const resumeBtn = el('resumeBtn');
        const loadBtn = el('loadBtn'); const tokenInput = el('wsToken');
        const tailLinesSelect = el('tailLinesSelect'); const pollInterval = el('pollInterval');
        const keywordFilter = el('keywordFilter'); const applyFilterBtn = el('applyFilterBtn'); const clearFilterBtn = el('clearFilterBtn');
        const msgSearch = el('msgSearch');
        const autoPoll = el('autoPoll'); const autoReconnect = el('autoReconnect');
        const levelChips = document.querySelectorAll('.level-chip'); const sortBtns = document.querySelectorAll('.sort-btn');
        const fileSelect = el('logFileSelect');

        // restore localStorage (guard DOM elements)
        try{ if(tokenInput) tokenInput.value = localStorage.getItem('de_mcu_ws_token') || ''; }catch(e){}
        try{ if(tailLinesSelect){ tailLinesSelect.value = localStorage.getItem('de_mcu_tail_lines') || tailLinesSelect.value; currentLines = parseInt(tailLinesSelect.value,10)||INITIAL_TAIL_LINES; } }catch(e){}
        try{ if(pollInterval){ pollInterval.value = localStorage.getItem('de_mcu_poll_interval') || pollInterval.value; currentIntervalMs = parseInt(pollInterval.value,10)||currentIntervalMs; } }catch(e){}
        try{ if(keywordFilter){ keywordFilter.value = localStorage.getItem('de_mcu_keyword') || ''; currentKeyword = keywordFilter.value; } }catch(e){}
        try{ headerSearch = localStorage.getItem('de_mcu_msg_search') || ''; if(msgSearch) { msgSearch.value = headerSearch; } }catch(e){}
        try{ if(autoPoll) autoPoll.checked = (localStorage.getItem('de_mcu_auto_poll') === '1'); }catch(e){}
        try{ const savedLevels = JSON.parse(localStorage.getItem('de_mcu_selected_levels')||'null'); if(Array.isArray(savedLevels)){ selectedLevels = new Set(savedLevels.map(s=> (s||'').toUpperCase())); levelChips.forEach(function(ch){ if(selectedLevels.has((ch.dataset.level||'').toUpperCase())) ch.classList.add('ring','ring-2','ring-offset-1'); }); } }catch(e){}

        // events
        connectBtn && connectBtn.addEventListener('click', ()=>connectWebSocket(true));
        disconnectBtn && disconnectBtn.addEventListener('click', disconnectWebSocket);
        pauseBtn && pauseBtn.addEventListener('click', ()=>{ isPaused = true; pauseBtn.disabled = true; resumeBtn.disabled = false; });
        resumeBtn && resumeBtn.addEventListener('click', ()=>{ isPaused = false; pauseBtn.disabled = false; resumeBtn.disabled = true; });
        loadBtn && loadBtn.addEventListener('click', ()=>{ clearLogTable(); _sendReloadRequest(); });
        tokenInput && tokenInput.addEventListener('change', ()=>{ try{ localStorage.setItem('de_mcu_ws_token', tokenInput.value); }catch(e){} });

        tailLinesSelect && tailLinesSelect.addEventListener('change', function(){ currentLines = parseInt(this.value,10)||INITIAL_TAIL_LINES; try{ localStorage.setItem('de_mcu_tail_lines', this.value); }catch(e){} });
        pollInterval && pollInterval.addEventListener('change', function(){ currentIntervalMs = parseInt(this.value,10)||1000; try{ localStorage.setItem('de_mcu_poll_interval', this.value); }catch(e){}; _restartPollIfNeeded(); });

        const doSearch = debounce(function(kw){ currentKeyword = (kw||'').trim(); try{ localStorage.setItem('de_mcu_keyword', currentKeyword); }catch(e){}; _sendReloadRequest(); }, 350);
        keywordFilter && keywordFilter.addEventListener('input', function(e){ doSearch(e.target.value); });
        // header message search (debounced)
        const doHeaderSearch = debounce(function(v){ headerSearch = (v||'').trim(); try{ localStorage.setItem('de_mcu_msg_search', headerSearch); }catch(e){}; applyFilter(); }, 250);
        msgSearch && msgSearch.addEventListener('input', function(e){ doHeaderSearch(e.target.value); });

        applyFilterBtn && applyFilterBtn.addEventListener('click', function(){ currentKeyword = keywordFilter.value.trim(); try{ localStorage.setItem('de_mcu_keyword', currentKeyword); }catch(e){}; applyFilter(); _sendReloadRequest(); });
        clearFilterBtn && clearFilterBtn.addEventListener('click', function(){ keywordFilter.value = ''; currentKeyword = ''; try{ localStorage.removeItem('de_mcu_keyword'); }catch(e){}; applyFilter(); _sendReloadRequest(); });
        autoPoll && autoPoll.addEventListener('change', function(){ try{ localStorage.setItem('de_mcu_auto_poll', this.checked ? '1' : '0'); }catch(e){}; _restartPollIfNeeded(); });

        levelChips && levelChips.forEach(function(ch){ ch.addEventListener('click', function(){ const lvl = (ch.dataset.level||'').toUpperCase(); if(!lvl) return; if(selectedLevels.has(lvl)){ selectedLevels.delete(lvl); ch.classList.remove('ring','ring-2','ring-offset-1'); } else { selectedLevels.add(lvl); ch.classList.add('ring','ring-2','ring-offset-1'); } try{ localStorage.setItem('de_mcu_selected_levels', JSON.stringify(Array.from(selectedLevels))); }catch(e){}; applyFilter(); _sendReloadRequest(); }); });

        // wire sort arrow buttons: asc (▲) forces ascending, desc (▼) forces descending
        const sortAscBtns = document.querySelectorAll('.sort-asc');
        const sortDescBtns = document.querySelectorAll('.sort-desc');
        // initial: hide all descending buttons
        sortDescBtns && sortDescBtns.forEach(function(b){ b.hidden = true; });
        sortAscBtns && sortAscBtns.forEach(function(b){ b.addEventListener('click', function(){ sortTable(b.dataset.col, 1); try{ updateSortToggle(b.dataset.col, 1); }catch(e){} }); });
        sortDescBtns && sortDescBtns.forEach(function(b){ b.addEventListener('click', function(){ sortTable(b.dataset.col, -1); try{ updateSortToggle(b.dataset.col, -1); }catch(e){} }); });
        // ensure initial visibility according to current sort state
        try{ updateHiddenOnSort(); }catch(e){}

        // level select all / clear handlers
        const selectAllLevelsBtn = el('selectAllLevels');
        const clearAllLevelsBtn = el('clearAllLevels');
        selectAllLevelsBtn && selectAllLevelsBtn.addEventListener('click', function(){ if(!levelChips) return; selectedLevels = new Set(); levelChips.forEach(function(ch){ const lvl = (ch.dataset.level||'').toUpperCase(); if(lvl){ selectedLevels.add(lvl); ch.classList.add('ring','ring-2','ring-offset-1'); } }); try{ localStorage.setItem('de_mcu_selected_levels', JSON.stringify(Array.from(selectedLevels))); }catch(e){}; applyFilter(); _sendReloadRequest(); });
        clearAllLevelsBtn && clearAllLevelsBtn.addEventListener('click', function(){ if(!levelChips) return; selectedLevels = new Set(); levelChips.forEach(function(ch){ ch.classList.remove('ring','ring-2','ring-offset-1'); }); try{ localStorage.setItem('de_mcu_selected_levels', JSON.stringify([])); }catch(e){}; applyFilter(); _sendReloadRequest(); });

        // preset time range buttons
        const preset1h = el('preset1h'); const preset24h = el('preset24h'); const preset7d = el('preset7d');
        function setPreset(hours){ const now = Date.now(); const start = now - (hours * 3600 * 1000); if(el('startTs')) el('startTs').value = formatDateTimeLocal(start); if(el('endTs')) el('endTs').value = formatDateTimeLocal(Date.now()); applyFilter(); _sendReloadRequest(); updateTsToggle(true); }
        preset1h && preset1h.addEventListener('click', function(){ setPreset(1); });
        preset24h && preset24h.addEventListener('click', function(){ setPreset(24); });
        preset7d && preset7d.addEventListener('click', function(){ setPreset(24*7); });

        const applyTsFilter = el('applyTsFilter'); const clearTsFilter = el('clearTsFilter');
        // Toggle behavior like sort arrows: initially hide clear (like sort-desc), clicking apply shows clear and hides apply, clicking clear reverses
        function updateTsToggle(applied){ try{ if(applyTsFilter) applyTsFilter.hidden = !!applied; if(clearTsFilter) clearTsFilter.hidden = !applied; }catch(e){} }
        // initial state: applied = false -> hide clear
        updateTsToggle(false);
        applyTsFilter && applyTsFilter.addEventListener('click', function(){ try{ applyFilter(); _sendReloadRequest(); updateTsToggle(true); }catch(e){ console.error('applyTsFilter click', e); } });
        clearTsFilter && clearTsFilter.addEventListener('click', function(){ try{ if(el('startTs')) el('startTs').value = ''; if(el('endTs')) el('endTs').value = ''; applyFilter(); _sendReloadRequest(); updateTsToggle(false); }catch(e){ console.error('clearTsFilter click', e); } });

        // init auto-poll
        if (!websocket && autoPoll && autoPoll.checked){ pollTimer = setInterval(_sendReloadRequest, currentIntervalMs); }

        // auto connect if token present (guard tokenInput)
        if (tokenInput && (tokenInput.value||'').trim().length > 0){ if(autoReconnect) autoReconnect.checked = true; connectWebSocket(false); }

        // --- Modal & level/message filter behavior ---
        const levelModalOverlay = el('levelFilterModalOverlay');
        const levelApplyBtn = el('levelFilterApply');
        const levelCancelBtn = el('levelFilterCancel');
        const levelCheckboxes = document.querySelectorAll('.level-checkbox');
        const levelSelectedBadge = el('levelSelectedCount');
        // 하이라이트 컬러는 general modal 내에 존재함. 메시지 전용 입력 및 버튼은 제거됨.

        // modal open/close helpers with focus restore
        let _lastFocusedElement = null;
        function openModalOverlay(overlay){
          if (!overlay) return;
          _lastFocusedElement = document.activeElement;
          overlay.style.display = 'flex';
          overlay.setAttribute('aria-hidden','false');
          // focus first focusable element inside modal
          try{
            const focusable = overlay.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
            if (focusable) focusable.focus();
          }catch(e){}
        }
        function closeModalOverlay(overlay){
          if (!overlay) return;
          overlay.style.display = 'none';
          overlay.setAttribute('aria-hidden','true');
          try{ if (_lastFocusedElement && typeof _lastFocusedElement.focus === 'function') _lastFocusedElement.focus(); }catch(e){}
          _lastFocusedElement = null;
        }

        // close modal when clicking on overlay backdrop
        if(typeof levelModalOverlay !== 'undefined' && levelModalOverlay){
          levelModalOverlay.addEventListener('click', function(e){ if (e.target === levelModalOverlay) closeModalOverlay(levelModalOverlay); });
        }
        // general modal backdrop click handled below (generalModal)

        // ESC key closes any open modal
        document.addEventListener('keydown', function(e){ if (e.key === 'Escape' || e.key === 'Esc'){
          try{ if (levelModalOverlay && levelModalOverlay.style.display === 'flex') { closeModalOverlay(levelModalOverlay); } else if (generalModal && generalModal.style.display === 'flex') { closeModalOverlay(generalModal); } }catch(ex){}
        }});

        // open level modal
        const openLevelBtn = el('openLevelFilter');
        openLevelBtn && openLevelBtn.addEventListener('click', function(){
          if(!levelModalOverlay) return; levelCheckboxes.forEach(function(cb){ cb.checked = selectedLevels.has(cb.value); }); openModalOverlay(levelModalOverlay);
        });

        levelCancelBtn && levelCancelBtn.addEventListener('click', function(){ closeModalOverlay(levelModalOverlay); });

        levelApplyBtn && levelApplyBtn.addEventListener('click', function(){ try{
          // gather checked
          selectedLevels = new Set(); levelCheckboxes.forEach(function(cb){ if(cb.checked) selectedLevels.add(cb.value); });
          try{ localStorage.setItem('de_mcu_selected_levels', JSON.stringify(Array.from(selectedLevels))); }catch(e){}
          // update UI chips (if present)
          document.querySelectorAll('.level-chip').forEach(function(ch){ const lvl = (ch.dataset.level||'').toUpperCase(); if(selectedLevels.has(lvl)) ch.classList.add('ring','ring-2','ring-offset-1'); else ch.classList.remove('ring','ring-2','ring-offset-1'); });
          updateLevelBadge(); applyFilter(); _sendReloadRequest();
        }catch(e){ console.error('apply level filter', e); } finally{ closeModalOverlay(levelModalOverlay); }});

        // 메시지 필터 전용 버튼 및 동적 생성 로직은 삭제됨 (통합 필터는 openGeneralFilter를 사용)

        function updateLevelBadge(){ try{ if(!levelSelectedBadge) return; levelSelectedBadge.textContent = String(selectedLevels.size || 0); }catch(e){} }

        // update counts for each level (visible counts in header chips)
        function updateLevelCounts(){ try{ const counts = {'ERROR':0,'WARNING':0,'INFO':0,'DEBUG':0}; const tbody = el('logTableBody'); if(!tbody) return; Array.from(tbody.children).forEach(function(r){ const lvl = (r.dataset.rawLevel||'').toUpperCase(); if(lvl && counts.hasOwnProperty(lvl)) counts[lvl] += 1; }); ['ERROR','WARNING','INFO','DEBUG'].forEach(function(l){ const elc = el('count-'+l); if(elc) elc.textContent = String(counts[l]||0); }); }catch(e){ console.error('updateLevelCounts', e); } }

        // update counts initially
        updateLevelBadge(); updateLevelCounts();

        // --- General filter modal wiring (open/apply/cancel) ---
        const generalModal = el('generalFilterModalOverlay');
        const generalApply = el('generalFilterApply');
        const generalCancel = el('generalFilterCancel');
        const openGeneralBtn = el('openGeneralFilter');
        // openMsgFilter 버튼은 템플릿에서 제거됨

        // open general filter modal and populate current values
        openGeneralBtn && openGeneralBtn.addEventListener('click', function(){
          if(!generalModal) return;
          try{ if(tailLinesSelect) tailLinesSelect.value = localStorage.getItem('de_mcu_tail_lines') || tailLinesSelect.value; }catch(e){}
          try{ if(pollInterval) pollInterval.value = localStorage.getItem('de_mcu_poll_interval') || pollInterval.value; }catch(e){}
          try{ if(keywordFilter) keywordFilter.value = localStorage.getItem('de_mcu_keyword') || currentKeyword || ''; }catch(e){}
          try{ if(autoPoll) autoPoll.checked = (localStorage.getItem('de_mcu_auto_poll') === '1'); }catch(e){}
          openModalOverlay(generalModal);
        });

        // general modal cancel/apply
        generalCancel && generalCancel.addEventListener('click', function(){ closeModalOverlay(generalModal); });
        generalApply && generalApply.addEventListener('click', function(){
          try{
            if(tailLinesSelect) { currentLines = parseInt(tailLinesSelect.value,10) || INITIAL_TAIL_LINES; try{ localStorage.setItem('de_mcu_tail_lines', tailLinesSelect.value); }catch(e){} }
            if(pollInterval) { currentIntervalMs = parseInt(pollInterval.value,10) || currentIntervalMs; try{ localStorage.setItem('de_mcu_poll_interval', pollInterval.value); }catch(e){} }
            // 키워드 필터는 keywordFilter만 사용
            try{ currentKeyword = (keywordFilter && keywordFilter.value) ? keywordFilter.value.trim() : ''; try{ localStorage.setItem('de_mcu_keyword', currentKeyword); }catch(e){} }catch(e){ console.error('saving keyword filter', e); }
            // apply highlight color if present
            try{ const hp = el('highlightColor'); if(hp && hp.value) { document.documentElement.style.setProperty('--log-highlight-bg', hp.value); } }catch(e){}
            if(autoPoll) { try{ localStorage.setItem('de_mcu_auto_poll', autoPoll.checked ? '1' : '0'); }catch(e){}; _restartPollIfNeeded(); }
            applyFilter(); _sendReloadRequest();
          }catch(err){ console.error('general filter apply', err); }
          finally{ closeModalOverlay(generalModal); }
        });

        // 메시지 필터 전용 헤더 버튼은 제거되어 관련 핸들러 없음

        // When file selection changes: reload tail and reconnect WS
        if(fileSelect){
          fileSelect.addEventListener('change', ()=>{
            clearLogTable();
            _sendReloadRequest();
            // reconnect WS with new file param
            if(websocket){ try{ websocket.close(); }catch(e){} websocket=null; }
            if(autoReconnect && autoReconnect.checked){ _scheduleReconnect(); } else { connectWebSocket(); }
          });
        }

        // auto-load & connect on page load
        window.addEventListener('load', ()=>{ clearLogTable(); _sendReloadRequest(); connectWebSocket(); });

      }catch(e){ console.error('init error', e); }
    });
  }

  // expose minimal functions for debugging
  window.DE_MCU = { connectWebSocket, disconnectWebSocket, clearLogTable };
  init();
})();
