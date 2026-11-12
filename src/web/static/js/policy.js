'use strict';
(() => {
    const filters = document.getElementById('policyFilters');
    let inFlight = false;
    async function refresh(event) {
        if (event) event.preventDefault();
        if (inFlight) return;
        inFlight = true;
        const controller = new AbortController();
        const timeout = window.setTimeout(() => controller.abort(), 8000);
        const options = {signal: controller.signal, cache: 'no-store', credentials: 'same-origin'};
        const query = new URLSearchParams({limit: '50'});
        const device = new FormData(filters).get('device_id');
        if (device) query.set('device_id', device);
        try {
            for (const [path, id] of [['', 'policyOverview'], ['/decisions', 'policyDecisions'],
                ['/signals', 'policySignals'], ['/transitions', 'policyTransitions'], ['/intents', 'policyIntents']]) {
                const response = await fetch('/api/policy' + path + '?' + query, options);
                if (!response.ok) throw new Error('Unavailable');
                const value = await response.json();
                document.getElementById(id).textContent = JSON.stringify(value, null, 2);
                if (!path) {
                    const d = value.diagnostics;
                    if (!d || typeof d.queue_pending !== 'number') throw new Error('Malformed diagnostics');
                    document.getElementById('policyWorkerStatus').textContent = 'Policy Worker: ' + d.worker_status + '; версия: ' + (d.active_version || 'неизвестна');
                    document.getElementById('policyEvidenceStatus').textContent = 'Обработанные источники: ' + d.evidence_status + '; последнее evidence: ' + (d.last_processed_evidence_at || 'нет данных') + '; задержка: ' + (d.source_lag_seconds === null ? 'неизвестно' : Math.round(d.source_lag_seconds) + ' с');
                    document.getElementById('policyQueueStatus').textContent = 'Очередь: ' + d.queue_pending + '; ' + d.backlog_status + '; overflow: ' + (d.overflow === null ? 'неизвестно' : d.overflow);
                }
            }
            const metrics = document.getElementById('policyMetrics');
            if (metrics) {
                const response = await fetch('/api/policy/metrics', options);
                if (!response.ok) throw new Error('Metrics unavailable');
                metrics.textContent = JSON.stringify(await response.json(), null, 2);
            }
            document.getElementById('policyMessage').textContent = 'DRY_RUN: Policy Engine формирует рекомендации; команды не отправляет.';
        } catch (_) {
            document.getElementById('policyMessage').textContent = 'Политика временно недоступна.';
            for (const id of ['policyOverview','policyDecisions','policySignals','policyTransitions','policyIntents','policyMetrics']) {
                const node = document.getElementById(id); if (node) node.textContent = '';
            }
            document.getElementById('policyWorkerStatus').textContent = 'Policy Worker: unavailable / unknown';
            document.getElementById('policyEvidenceStatus').textContent = 'Актуальность evidence неизвестна';
            document.getElementById('policyQueueStatus').textContent = 'Очередь: неизвестно';
        } finally {
            window.clearTimeout(timeout);
            inFlight = false;
        }
    }
    filters.addEventListener('submit', refresh);
    const admin = document.getElementById('policyAdmin');
    if (admin) admin.addEventListener('submit', async event => {
        event.preventDefault();
        try {
            const data = new FormData(admin);
            const response = await fetch('/api/policy/versions', {method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content},
                body: JSON.stringify({version: data.get('version'), rules: JSON.parse(data.get('rules')), activate: data.has('activate')})});
            if (!response.ok) throw new Error('Rejected');
            await refresh();
        } catch (_) { document.getElementById('policyMessage').textContent = 'Изменение отклонено. Проверьте права, CSRF и параметры.'; }
    });
    refresh();
    window.setInterval(() => refresh(), 5000);
})();
