const DATA_BASE = './data';

const MONTH_NAMES = [
    '', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'
];

const TYPE_COLORS = {
    'ДТП мот/авто': '#e94560',
    'ДТП мот/мот': '#ff6b35',
    'ДТП одиночное': '#f0c929',
    'ДТП прочее': '#533483',
    'Поломка': '#4ecca3',
    'Угон': '#c0392b',
    'Розыск': '#2980b9',
    'Информация': '#0f3460'
};

const SEVERITY_CLASS = {
    'Без пострадавших': 'severity-ok',
    'Лёгкая': 'severity-light',
    'Средняя': 'severity-medium',
    'Тяжёлая': 'severity-heavy',
    'Смерть': 'severity-death',
    'Неизвестно': 'severity-unknown'
};

let map = null;
let markers = null;
let allYears = [];
let allTypes = [];

if (window.Telegram && window.Telegram.WebApp) {
    window.Telegram.WebApp.ready();
    window.Telegram.WebApp.expand();
}

document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
        tab.classList.add('active');
        const target = tab.dataset.tab;
        document.getElementById(`${target}-section`).classList.add('active');
        if (target === 'map' && !map) initMap();
    });
});

async function loadJSON(path) {
    const resp = await fetch(`${DATA_BASE}/${path}?_=${Date.now()}`);
    if (!resp.ok) return null;
    return resp.json();
}

async function loadFilters() {
    const [yearsData, typesData] = await Promise.all([
        loadJSON('years.json'),
        loadJSON('types.json')
    ]);

    allYears = yearsData ? yearsData.years : [];
    allTypes = typesData ? typesData.types : [];

    const yearSelect = document.getElementById('year-select');
    const mapYearSelect = document.getElementById('map-year-select');
    allYears.forEach(y => {
        yearSelect.add(new Option(y, y));
        mapYearSelect.add(new Option(y, y));
    });

    const typeSelect = document.getElementById('type-select');
    allTypes.forEach(t => {
        typeSelect.add(new Option(t, t));
    });
}

async function loadStats() {
    const year = document.getElementById('year-select').value;
    const month = document.getElementById('month-select').value;
    const type = document.getElementById('type-select').value;

    let data = null;

    if (type) {
        const safeName = type.replace(/\//g, '_').replace(/ /g, '_');
        data = await loadJSON(`type_${safeName}.json`);
    } else if (year && month) {
        data = await loadJSON(`stats_${year}_${month}.json`);
    } else if (year) {
        data = await loadJSON(`months_${year}.json`);
    } else {
        data = await loadJSON('stats.json');
    }

    if (!data) {
        document.getElementById('stats-cards').innerHTML = '<div class="loading">Нет данных</div>';
        document.getElementById('stats-chart').innerHTML = '';
        document.getElementById('stats-table').innerHTML = '';
        return;
    }

    document.getElementById('total-count').textContent = `Всего инцидентов: ${data.total}`;

    renderCards(data);
    renderChart(data, { year, month, type });
    renderTable(data, { year, month, type });
}

function renderCards(data) {
    const container = document.getElementById('stats-cards');
    const stats = data.stats;
    const total = stats.reduce((sum, r) => sum + r.cnt, 0);

    let topType = '-';
    let topCount = 0;
    stats.forEach(r => {
        const key = r.incident_type || r.year || r.month;
        if (r.cnt > topCount) {
            topCount = r.cnt;
            topType = key;
        }
    });

    container.innerHTML = `
        <div class="card red">
            <div class="card-value">${total}</div>
            <div class="card-label">Всего</div>
        </div>
        <div class="card orange">
            <div class="card-value">${stats.length}</div>
            <div class="card-label">Категорий</div>
        </div>
        <div class="card yellow">
            <div class="card-value">${topCount}</div>
            <div class="card-label">Макс. в категории</div>
        </div>
        <div class="card green">
            <div class="card-value">${total ? Math.round(total / Math.max(stats.length, 1)) : 0}</div>
            <div class="card-label">Среднее</div>
        </div>
    `;
}

function renderChart(data, filters) {
    const container = document.getElementById('stats-chart');
    const stats = data.stats;
    if (!stats.length) {
        container.innerHTML = '<div class="loading">Нет данных</div>';
        return;
    }

    const max = Math.max(...stats.map(r => r.cnt));

    let title = 'Распределение';
    if (filters.type) title = `По месяцам: ${filters.type}`;
    else if (filters.month) title = `По типам: ${MONTH_NAMES[filters.month]} ${filters.year}`;
    else if (filters.year) title = `По месяцам: ${filters.year}`;
    else title = 'По годам';

    let html = `<div class="chart-title">${title}</div>`;
    stats.forEach(r => {
        let label = r.incident_type || (r.month ? MONTH_NAMES[r.month] : r.year) || '?';
        if (r.year && r.month) label = `${MONTH_NAMES[r.month]} ${r.year}`;
        const pct = max ? (r.cnt / max * 100) : 0;
        const color = TYPE_COLORS[r.incident_type] || '#e94560';
        html += `
            <div class="bar-row">
                <div class="bar-label" title="${label}">${label}</div>
                <div class="bar-track">
                    <div class="bar-fill" style="width:${pct}%;background:${color}"></div>
                </div>
                <div class="bar-value">${r.cnt}</div>
            </div>
        `;
    });

    container.innerHTML = html;
}

function renderTable(data, filters) {
    const container = document.getElementById('stats-table');
    const stats = data.stats;
    if (!stats.length) {
        container.innerHTML = '';
        return;
    }

    const total = stats.reduce((sum, r) => sum + r.cnt, 0);
    let col1 = 'Категория';
    if (filters.type) col1 = 'Период';

    let html = `<div class="table-row header">
        <div class="table-cell">${col1}</div>
        <div class="table-cell">Кол-во</div>
    </div>`;

    stats.forEach(r => {
        let label = r.incident_type || '?';
        if (r.year && r.month) label = `${MONTH_NAMES[r.month]} ${r.year}`;
        else if (r.month) label = MONTH_NAMES[r.month];
        else if (r.year) label = String(r.year);

        const pct = total ? (r.cnt / total * 100).toFixed(1) : 0;
        html += `<div class="table-row">
            <div class="table-cell">${label}</div>
            <div class="table-cell">${r.cnt} (${pct}%)</div>
        </div>`;
    });

    container.innerHTML = html;
}

function initMap() {
    map = L.map('map').setView([55.75, 37.62], 10);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap'
    }).addTo(map);
    markers = L.layerGroup().addTo(map);
    loadMapData();
}

async function loadMapData() {
    const year = document.getElementById('map-year-select').value;
    const filename = year ? `map_${year}.json` : 'map.json';
    const data = await loadJSON(filename);

    markers.clearLayers();

    const incidents = (data && data.incidents) || [];
    document.getElementById('map-count').textContent = `${incidents.length} точек`;

    incidents.forEach(inc => {
        if (!inc.latitude || !inc.longitude) return;

        const severityClass = SEVERITY_CLASS[inc.severity] || 'severity-unknown';
        const color = inc.severity === 'Смерть' ? '#333'
            : inc.severity === 'Тяжёлая' ? '#e94560'
            : inc.severity === 'Средняя' ? '#ff6b35'
            : inc.severity === 'Лёгкая' ? '#f0c929'
            : inc.severity === 'Без пострадавших' ? '#4ecca3'
            : '#999';

        const marker = L.circleMarker([inc.latitude, inc.longitude], {
            radius: 7,
            fillColor: color,
            color: '#fff',
            weight: 1,
            fillOpacity: 0.85
        });

        marker.bindPopup(`
            <b>${inc.incident_type || ''}</b>
            <span class="severity-badge ${severityClass}">${inc.severity || ''}</span><br>
            📍 ${inc.location || 'Без адреса'}<br>
            📅 ${inc.date ? inc.date.split('T')[0] : ''}
        `);

        markers.addLayer(marker);
    });

    if (incidents.length > 0) {
        const valid = incidents.filter(i => i.latitude && i.longitude);
        if (valid.length) {
            const bounds = L.latLngBounds(valid.map(i => [i.latitude, i.longitude]));
            map.fitBounds(bounds, { padding: [20, 20] });
        }
    }
}

document.getElementById('year-select').addEventListener('change', loadStats);
document.getElementById('month-select').addEventListener('change', loadStats);
document.getElementById('type-select').addEventListener('change', loadStats);
document.getElementById('map-year-select').addEventListener('change', loadMapData);

const monthSelect = document.getElementById('month-select');
for (let i = 1; i <= 12; i++) {
    monthSelect.add(new Option(MONTH_NAMES[i], i));
}

loadFilters().then(loadStats);
