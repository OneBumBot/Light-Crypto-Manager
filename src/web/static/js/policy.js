'use strict';
(() => {
    const filters = document.getElementById('policyFilters');
    async function refresh(event) {
        if (event) event.preventDefault();
        const query = new URLSearchParams({limit: '50'});
        const device = new FormData(filters).get('device_id');
        if (device) query.set('device_id', device);
        try {
            for (const [path, id] of [['', 'policyOverview'], ['/decisions', 'policyDecisions'],
                ['/signals', 'policySignals'], ['/transitions', 'policyTransitions'], ['/intents', 'policyIntents']]) {
                const response = await fetch('/api/policy' + path + '?' + query);
                if (!response.ok) throw new Error('Unavailable');
                document.getElementById(id).textContent = JSON.stringify(await response.json(), null, 2);
            }
            const metrics = document.getElementById('policyMetrics');
            if (metrics) {
                const response = await fetch('/api/policy/metrics');
                if (response.ok) metrics.textContent = JSON.stringify(await response.json(), null, 2);
            }
            document.getElementById('policyMessage').textContent = 'DRY_RUN: реальное управление отключено.';
        } catch (_) { document.getElementById('policyMessage').textContent = 'Политика временно недоступна.'; }
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
})();
