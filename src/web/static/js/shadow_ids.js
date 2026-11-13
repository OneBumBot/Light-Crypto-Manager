'use strict';
(() => {
  let offset = 0;
  const rows = document.getElementById('shadow-rows');
  const summary = document.getElementById('shadow-summary');
  const status = document.getElementById('shadow-status');
  function clear() { rows.replaceChildren(); summary.replaceChildren(); }
  async function refresh() {
    try {
      const response = await fetch(`/api/research/shadow-ids?limit=25&offset=${offset}`, {credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok) throw new Error('unavailable');
      const data = await response.json();
      clear();
      if (!data.available) { status.textContent = 'Источник устарел / недоступен. Текущие scores очищены.'; return; }
      const capture = data.capture || {}, worker = data.worker || {};
      status.textContent = `Capture: ${capture.status}; worker: ${worker.status}; backlog: ${data.pending}. RESEARCH / SHADOW_ONLY`;
      for (const [label, value] of Object.entries({Packets: data.packets, Inferences: data.inferences, 'Kernel drops': capture.stats?.dropped_by_kernel ?? 'not_measured_until_capture_end', 'Queue overflow': capture.queue_overflow, 'Reader drops': capture.reader_drops, 'Last packet': capture.last_packet, 'Parity': data.feature_parity?.status, 'Binding': data.device_binding})) {
        const dt = document.createElement('dt'), dd = document.createElement('dd'); dt.textContent = label; dd.textContent = String(value ?? 'unknown'); summary.append(dt, dd);
      }
      for (const item of data.results || []) {
        const tr = document.createElement('tr');
        for (const value of [item.session_id, item.model_id, item.score, item.threshold, item.inference_status, item.device_binding]) { const td = document.createElement('td'); td.textContent = String(value ?? 'unavailable'); tr.append(td); }
        rows.append(tr);
      }
    } catch (_) { clear(); status.textContent = 'Источник недоступен. Текущие scores очищены.'; }
  }
  document.getElementById('shadow-prev').addEventListener('click', () => {offset = Math.max(0, offset - 25); refresh();});
  document.getElementById('shadow-next').addEventListener('click', () => {offset = Math.min(50000, offset + 25); refresh();});
  refresh(); setInterval(refresh, 3000);
})();
