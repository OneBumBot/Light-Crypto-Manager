const socket = io();

// глобальные переменные
let temperatureChart, humidityChart;
const chartData = {
    labels: [],
    temperature: [],
    humidity: [],
};
const MAX_DATA_POINTS = 50;

document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded');

    if (typeof Chart === 'undefined') {
        console.error('Chart.js NOT loaded');
        return;
    } else {
        console.log('Chart.js loaded OK');
    }

    initCharts();
    loadHistoricalData();

    socket.on('connect', () => {
        console.log('Socket.IO connected');
    });

    socket.on('sensor_update', data => {
        console.log('sensor_update:', data);
        updateDashboard(data);
        updateCharts(data);
    });
});

function initCharts() {
    const tempCtx = document.getElementById('temperatureChart')?.getContext('2d');
    const humCtx  = document.getElementById('humidityChart')?.getContext('2d');

    if (!tempCtx || !humCtx) {
        console.error('One of canvases not found');
        return;
    }

    temperatureChart = new Chart(tempCtx, {
        type: 'line',
        data: {
            labels: chartData.labels,
            datasets: [{
                label: 'Температура (°C)',
                data: chartData.temperature,
                borderColor: 'rgb(220, 53, 69)',
                backgroundColor: 'rgba(220, 53, 69, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {responsive: true, maintainAspectRatio: false}
    });

    humidityChart = new Chart(humCtx, {
        type: 'line',
        data: {
            labels: chartData.labels,
            datasets: [{
                label: 'Влажность (%)',
                data: chartData.humidity,
                borderColor: 'rgb(13, 110, 253)',
                backgroundColor: 'rgba(13, 110, 253, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {responsive: true, maintainAspectRatio: false}
    });

    console.log('Charts initialized');
}

async function loadHistoricalData() {
    try {
        const resp = await fetch('/api/latest-data');
        const data = await resp.json();
        console.log('latest-data:', data);

        if (!data.temperature || data.temperature.length === 0) {
            console.warn('No historical data');
            return;
        }

        chartData.labels      = data.timestamps.map(formatTime);
        chartData.temperature = data.temperature;
        chartData.humidity    = data.humidity;

        temperatureChart.update();
        humidityChart.update();

        // Обновим цифры сверху
        updateDashboard({
            temperature: data.temperature.at(-1),
            humidity:    data.humidity.at(-1),
            timestamp:   data.timestamps.at(-1)
        });
    } catch (e) {
        console.error('loadHistoricalData error:', e);
    }
}

function updateDashboard(data) {
    const tEl = document.getElementById('tempValue');
    const hEl = document.getElementById('humidityValue');
    const timeEl = document.getElementById('lastUpdate');

    if (tEl && data.temperature != null) tEl.textContent = data.temperature.toFixed(1);
    if (hEl && data.humidity != null)   hEl.textContent = data.humidity.toFixed(1);

    if (timeEl && data.timestamp) {
        const d = new Date(data.timestamp);
        timeEl.textContent = d.toLocaleString('ru-RU');
    }
}

function updateCharts(data) {
    const label = formatTime(data.timestamp);

    chartData.labels.push(label);
    chartData.temperature.push(data.temperature);
    chartData.humidity.push(data.humidity);

    if (chartData.labels.length > MAX_DATA_POINTS) {
        chartData.labels.shift();
        chartData.temperature.shift();
        chartData.humidity.shift();
    }

    temperatureChart.update('none');
    humidityChart.update('none');
}

function formatTime(ts) {
    const d = new Date(ts);
    return d.toLocaleTimeString('ru-RU', {hour: '2-digit', minute: '2-digit', second: '2-digit'});
}

