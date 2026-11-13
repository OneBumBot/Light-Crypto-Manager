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
      const data = await response.json(); clear();
      const capture = data.capture || {}, worker = data.worker || {};
      const dropped = (capture.queue_overflow || 0) + (capture.reader_drops || 0) + (capture.stats?.dropped_by_kernel || 0);
      let condition = 'Получает пакеты / SHADOW_ONLY';
      if (!capture.fresh || !worker.fresh) condition = 'Сервис недоступен или heartbeat устарел';
      else if (worker.status === 'MODEL_UNAVAILABLE') condition = 'Модель недоступна';
      else if (dropped || capture.status === 'CAPTURE_INCOMPLETE') condition = 'CAPTURE_INCOMPLETE — потерян контекст';
      else if (capture.traffic_state !== 'RECENT') condition = 'Сервис работает, свежего traffic нет';
      else if (data.pending > 64 || !worker.evidence_fresh) condition = 'Сервис работает, inference отстаёт';
      status.textContent = `${condition}. Capture: ${capture.status}; worker: ${worker.status}. RESEARCH / SHADOW_ONLY`;
      const values = {
        'Capture point': capture.capture_point || data.source?.capture_point || 'lab-devices eth0 / Ethernet IPv4 TCP',
        Packets: data.packets, Sessions: data.sessions, Inferences: data.inferences,
        'Unknown / unavailable context': data.unknown, 'Processing backlog': data.pending,
        'Kernel drops': capture.stats?.dropped_by_kernel ?? 'not_measured_until_capture_end',
        'Queue overflow': capture.queue_overflow, 'Reader drops': capture.reader_drops,
        'Last packet': capture.last_packet, 'Last inference': worker.last_inference,
        'Source fresh': capture.traffic_state, 'Inference fresh': worker.evidence_fresh,
        Parity: data.feature_parity?.status, Binding: data.device_binding,
        'Worker peak RSS KiB': worker.peak_rss_kib
      };
      for (const [label, value] of Object.entries(values)) {
        const dt = document.createElement('dt'), dd = document.createElement('dd'); dt.textContent = label; dd.textContent = String(value ?? 'unknown'); summary.append(dt, dd);
      }
      if (!data.available) return; // Stale scores remain cleared; technical status is separate.
      for (const item of data.results || []) {
        const tr = document.createElement('tr');
        const latency = typeof item.inference_finish === 'number' && typeof item.capture_timestamp === 'number' ? (1000 * (item.inference_finish - item.capture_timestamp)).toFixed(2) : 'unavailable';
        for (const value of [item.session_id, item.model_id, item.model_version, item.score, item.threshold, item.inference_status, latency, item.device_binding]) { const td = document.createElement('td'); td.textContent = String(value ?? 'unavailable'); tr.append(td); }
        rows.append(tr);
      }
    } catch (_) { clear(); status.textContent = 'Источник недоступен. Текущие scores очищены.'; }
  }
  document.getElementById('shadow-prev').addEventListener('click', () => {offset = Math.max(0, offset - 25); refresh();});
  document.getElementById('shadow-next').addEventListener('click', () => {offset = Math.min(50000, offset + 25); refresh();});
  refresh(); setInterval(refresh, 3000);
})();
