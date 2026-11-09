'use strict';
(() => {
    async function refresh(event) {
        if (event) event.preventDefault();
        const params = new URLSearchParams({limit: '50'});
        const device = new FormData(document.getElementById('mlFilters')).get('device_id');
        if (device) params.set('device_id', device);
        try {
            const [eventsResponse, statusResponse] = await Promise.all([
                fetch('/api/ml/events?' + params), fetch('/api/ml/status')]);
            if (!eventsResponse.ok || !statusResponse.ok) throw new Error('unavailable');
            const events = await eventsResponse.json(), status = await statusResponse.json();
            document.getElementById('mlStatus').textContent = JSON.stringify({models: status.models,
                feed: status.feed, events: status.event_status_counts,
                mean_prepare_ms: status.mean_prepare_ms, mean_inference_ms: status.mean_inference_ms,
                delivery_ack_lag_seconds: status.mean_delivery_ack_lag_seconds}, null, 2);
            document.getElementById('protocolStatus').textContent = status.protocol_rejections === null
                ? 'Агрегаты криптографических отказов доступны администратору.' : 'Отвергнуто протоколом: ' + status.protocol_rejections;
            document.getElementById('rulesStatus').textContent = status.rule_anomalies === null
                ? 'Журнал простых правил недоступен вашей роли.' : 'Событий простых правил: ' + status.rule_anomalies;
            const rows = document.getElementById('mlRows'); rows.replaceChildren();
            for (const item of events.items) {
                const row = document.createElement('tr');
                for (const value of [item.device_id, item.detector, item.evaluated_at,
                    item.score, item.threshold, item.model_id + ' / ' + item.model_version,
                    item.status, item.is_anomaly === null ? 'Не оценено' : (item.is_anomaly ? 'Сигнал' : 'Нет сигнала')]) {
                    const cell = document.createElement('td'); cell.textContent = value === null ? '—' : String(value); row.appendChild(cell);
                }
                rows.appendChild(row);
            }
            document.getElementById('mlMessage').textContent = events.items.length ? '' : 'Нет результатов ML.';
        } catch (_) { document.getElementById('mlMessage').textContent = 'ML-результаты недоступны. Проверьте вход и повторите запрос.'; }
    }
    document.getElementById('mlFilters').addEventListener('submit', refresh);
    refresh();
})();
