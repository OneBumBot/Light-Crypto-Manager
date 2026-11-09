'use strict';
(() => {
    const form = document.getElementById('historyFilters');
    const rows = document.getElementById('historyRows');
    const status = document.getElementById('historyStatus');
    const prev = document.getElementById('historyPrev');
    const next = document.getElementById('historyNext');
    let offset = 0;
    let requestVersion = 0;
    async function load() {
        const version = ++requestVersion;
        const params = new URLSearchParams({limit: '100', offset: String(offset)});
        for (const [key, value] of new FormData(form)) {
            if (value) params.set(key, key === 'device_id' ? value : value + ':00Z');
        }
        prev.disabled = next.disabled = true;
        status.textContent = 'Загрузка…';
        try {
            const response = await fetch('/api/telemetry/history?' + params);
            if (version !== requestVersion) return;
            if (!response.ok) throw new Error('history unavailable');
            const result = await response.json();
            rows.replaceChildren();
            for (const item of result.items) {
                const row = document.createElement('tr');
                for (const value of [item.device_id, item.measured_at, item.temperature,
                    item.humidity, item.key_epoch + ' / ' + item.sequence_number]) {
                    const cell = document.createElement('td');
                    cell.textContent = String(value);
                    row.appendChild(cell);
                }
                rows.appendChild(row);
            }
            status.textContent = result.items.length ? 'Записей: ' + result.items.length : 'Нет данных';
            prev.disabled = offset === 0;
            next.disabled = result.items.length < 100 || offset >= 10000;
        } catch (_) {
            if (version === requestVersion) {
                rows.replaceChildren();
                status.textContent = 'История недоступна. Проверьте вход и повторите запрос.';
            }
        }
    }
    form.addEventListener('submit', event => { event.preventDefault(); offset = 0; load(); });
    prev.addEventListener('click', () => { offset = Math.max(0, offset - 100); load(); });
    next.addEventListener('click', () => { offset += 100; load(); });
    load();
})();
