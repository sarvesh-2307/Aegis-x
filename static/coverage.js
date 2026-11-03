/* ============================================================
   AEGIS-X  ·  coverage.js
   Sensor Coverage Planner with Blind Spot Detection
   ============================================================ */

'use strict';

// ── State ──────────────────────────────────────────────────
let map, mode = 'sensor';
let sensors    = [];           // { id, name, type, latlng, range, marker, circle }
let zonePoints = [];           // LatLng[] for user-drawn monitoring zone
let zoneLayer  = null;
let zoneLine   = null;
let blindLayers = [];          // L.Layer[]
let suggestLayers = [];        // L.Layer[]
let sensorIdCounter = 1;
let clickGuides = [];          // temp polylines while drawing zone

const TYPE_COLOR = {
    thermal: '#ff6633',
    radar:   '#44aaff',
    vision:  '#00ff88',
    multi:   '#cc44ff',
};

const GRID_SIZE = 0.0003;  // ~30m grid cell in degrees — adjust for area scale


// ── Init Map ───────────────────────────────────────────────
function initMap() {
    map = L.map('map', {
        center:          [26.8467, 80.9462],   // Lucknow, UP (change to your area)
        zoom:            16,
        zoomControl:     true,
        attributionControl: false,
    });

    // Dark satellite-style tile
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 22,
        attribution: '© OSM',
    }).addTo(map);

    // Optional: add dark overlay to push map darker
    L.tileLayer(
        'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png',
        { maxZoom: 22, opacity: 0.88, attribution: '' }
    ).addTo(map);

    map.on('click', onMapClick);
}


// ── Mode Switching ─────────────────────────────────────────
function setMode(m) {
    mode = m;
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('mode-' + m).classList.add('active');

    const badge = document.getElementById('map-mode-badge');
    if (m === 'sensor') {
        badge.textContent = '📍 CLICK MAP TO PLACE SENSOR';
        map.getContainer().style.cursor = 'crosshair';
    } else if (m === 'zone') {
        badge.textContent = '🔲 CLICK TO DRAW ZONE  |  Double-click to FINISH';
        map.getContainer().style.cursor = 'crosshair';
    } else {
        badge.textContent = '🖐 PAN MODE';
        map.getContainer().style.cursor = '';
    }
}


// ── Map Click Handler ──────────────────────────────────────
function onMapClick(e) {
    if (mode === 'sensor') placeSensor(e.latlng);
    else if (mode === 'zone') addZonePoint(e.latlng);
}

map = null;   // will be assigned in DOMContentLoaded


// ── Place Sensor ───────────────────────────────────────────
function placeSensor(latlng) {
    const type  = document.getElementById('cfg-type').value;
    const range = parseInt(document.getElementById('cfg-range').value);
    const name  = document.getElementById('cfg-name').value.trim() || ('SENSOR-' + String(sensorIdCounter).padStart(2,'0'));
    const color = TYPE_COLOR[type] || '#cc44ff';
    const id    = sensorIdCounter++;

    // Auto-increment name for next sensor
    document.getElementById('cfg-name').value = 'SENSOR-' + String(sensorIdCounter).padStart(2,'0');

    // Custom latlng icon
    const icon = L.divIcon({
        className: '',
        html: `<div class="sensor-marker" style="--col:${color};">
                   <div class="sm-ring"></div>
                   <div class="sm-dot"></div>
                   <div class="sm-label">${name}</div>
               </div>`,
        iconSize:   [40, 40],
        iconAnchor: [20, 20],
    });

    const marker = L.marker(latlng, { icon, draggable: true }).addTo(map);
    marker.bindPopup(buildSensorPopup(id, name, type, range, latlng));

    // Coverage circle
    const circle = L.circle(latlng, {
        radius:      range,
        color:       color,
        fillColor:   color,
        fillOpacity: 0.08,
        weight:      1.5,
        dashArray:   '6,4',
    }).addTo(map);

    const sensor = { id, name, type, latlng, range, marker, circle, color };
    sensors.push(sensor);

    // Drag updates circle
    marker.on('drag', e => {
        circle.setLatLng(e.latlng);
        sensor.latlng = e.latlng;
    });
    marker.on('dragend', () => {
        runCoverageStats();
        updateSensorList();
    });

    marker.on('dblclick', () => removeSensor(id));

    updateSensorList();
    updateHeaderStats();
    runCoverageStats();
}


function buildSensorPopup(id, name, type, range, latlng) {
    return `<div style="font-family:'Share Tech Mono',monospace;font-size:11px;min-width:160px;">
        <div style="font-family:'Orbitron',sans-serif;color:#cc44ff;font-size:12px;margin-bottom:6px;">${name}</div>
        <div>TYPE: <b style="color:${TYPE_COLOR[type]}">${type.toUpperCase()}</b></div>
        <div>RANGE: <b style="color:#ffd700">${range}m</b></div>
        <div>LAT: ${latlng.lat.toFixed(5)}</div>
        <div>LNG: ${latlng.lng.toFixed(5)}</div>
        <button onclick="removeSensor(${id})" style="margin-top:8px;padding:4px 10px;background:rgba(200,0,0,.3);border:1px solid #ff3333;color:#ff4444;font-family:inherit;font-size:10px;border-radius:3px;cursor:pointer;letter-spacing:1px;">🗑 REMOVE</button>
    </div>`;
}


// ── Remove Sensor ──────────────────────────────────────────
function removeSensor(id) {
    const idx = sensors.findIndex(s => s.id === id);
    if (idx === -1) return;
    const s = sensors[idx];
    map.removeLayer(s.marker);
    map.removeLayer(s.circle);
    sensors.splice(idx, 1);
    updateSensorList();
    updateHeaderStats();
    runCoverageStats();
    clearBlindLayers();
}


// ── Sensor List UI ─────────────────────────────────────────
function updateSensorList() {
    const el = document.getElementById('sensor-list');
    if (sensors.length === 0) {
        el.innerHTML = '<div class="sensor-empty">No sensors deployed.<br>Use ADD SENSOR mode.</div>';
        return;
    }
    el.innerHTML = sensors.map(s => `
        <div class="sensor-card">
            <div class="sc-name">${s.name}</div>
            <div class="sc-detail">
                <span class="sc-type-badge ${s.type}">${s.type.toUpperCase()}</span>
                &nbsp; ${s.range}m range
            </div>
            <div class="sc-detail">${s.latlng.lat.toFixed(4)}, ${s.latlng.lng.toFixed(4)}</div>
            <button class="sc-delete" onclick="removeSensor(${s.id})">✕</button>
        </div>
    `).join('');
}


// ── Zone Drawing ───────────────────────────────────────────
function addZonePoint(latlng) {
    zonePoints.push(latlng);

    // Finish on double-click is handled via map dblclick
    if (clickGuides.length > 0) {
        map.removeLayer(clickGuides[clickGuides.length - 1]);
        clickGuides.pop();
    }

    if (zonePoints.length >= 2) {
        const ln = L.polyline(
            [zonePoints[zonePoints.length - 2], zonePoints[zonePoints.length - 1]],
            { color: '#cc44ff', weight: 1.5, dashArray: '4,4', opacity: 0.7 }
        ).addTo(map);
        clickGuides.push(ln);
    }

    if (zonePoints.length >= 3) finalizeZone();
    // Note: we finalize after 3+ clicks; user double-clicks to finish or we auto-close
}

// We'll also finalize zone on dblclick to handle arbitrary polygons
function setupZoneDoubleClick() {
    map.once('dblclick', e => {
        L.DomEvent.stopPropagation(e);
        if (zonePoints.length >= 3) finalizeZone();
    });
}

function finalizeZone() {
    // Clean up guide lines
    clickGuides.forEach(l => map.removeLayer(l));
    clickGuides = [];

    if (zoneLayer) map.removeLayer(zoneLayer);
    if (zoneLine)  map.removeLayer(zoneLine);

    zoneLayer = L.polygon(zonePoints, {
        color: '#cc44ff',
        fillColor: '#6600aa',
        fillOpacity: 0.06,
        weight: 2,
        dashArray: '8,4',
    }).addTo(map);

    zoneLine = null;
    setMode('sensor');   // auto-switch to sensor placement after zone drawn
    runCoverageStats();
}

function clearZone() {
    if (zoneLayer) { map.removeLayer(zoneLayer); zoneLayer = null; }
    if (zoneLine)  { map.removeLayer(zoneLine);  zoneLine = null; }
    clickGuides.forEach(l => map.removeLayer(l));
    clickGuides = [];
    zonePoints = [];
    clearBlindLayers();
    resetStats();
}

function clearAll() {
    sensors.forEach(s => { map.removeLayer(s.marker); map.removeLayer(s.circle); });
    sensors = [];
    clearZone();
    clearBlindLayers();
    clearSuggestions();
    updateSensorList();
    updateHeaderStats();
    document.getElementById('blind-list').innerHTML       = '<div class="blind-empty">Run analysis first.</div>';
    document.getElementById('suggestion-list').innerHTML  = '<div class="suggest-empty">Run auto-suggest to see recommendations.</div>';
    sensorIdCounter = 1;
    document.getElementById('cfg-name').value = 'SENSOR-01';
}

function clearBlindLayers() {
    blindLayers.forEach(l => map.removeLayer(l));
    blindLayers = [];
}
function clearSuggestions() {
    suggestLayers.forEach(l => map.removeLayer(l));
    suggestLayers = [];
}


// ══════════════════════════════════════════════════════════════
// COVERAGE ANALYSIS — Grid-based
// ══════════════════════════════════════════════════════════════

function latLngToMeters(a, b) {
    return map.distance(a, b);
}

function isCovered(latlng) {
    return sensors.some(s => latLngToMeters(latlng, s.latlng) <= s.range);
}

function isInsideZone(latlng) {
    if (!zoneLayer) return true;   // no zone = whole map
    // Leaflet point-in-polygon using ray casting
    const pt = map.latLngToLayerPoint(latlng);
    const poly = zoneLayer.getLatLngs()[0].map(ll => map.latLngToLayerPoint(ll));
    return pointInPolygon([pt.x, pt.y], poly.map(p => [p.x, p.y]));
}

function pointInPolygon(point, polygon) {
    const [x, y] = point;
    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const [xi, yi] = polygon[i];
        const [xj, yj] = polygon[j];
        if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) {
            inside = !inside;
        }
    }
    return inside;
}

function getBounds() {
    if (zoneLayer) return zoneLayer.getBounds();
    return map.getBounds();
}


// ── MAIN ANALYSIS FUNCTION ────────────────────────────────
function analyzeBlindSpots() {
    clearBlindLayers();
    document.getElementById('blind-list').innerHTML = '';

    if (sensors.length === 0) {
        alert('Place at least one sensor first!');
        return;
    }

    const bounds     = getBounds();
    const latStep    = GRID_SIZE;
    const lngStep    = GRID_SIZE;

    let totalCells   = 0;
    let coveredCells = 0;
    let overlapCells = 0;
    let blindCells   = 0;

    // Cluster blind cells into groups
    const blindClusterMap = {};

    for (let lat = bounds.getSouth(); lat < bounds.getNorth(); lat += latStep) {
        for (let lng = bounds.getWest(); lng < bounds.getEast(); lng += lngStep) {
            const latlng = L.latLng(lat, lng);
            if (!isInsideZone(latlng)) continue;
            totalCells++;

            const coverCount = sensors.filter(s => latLngToMeters(latlng, s.latlng) <= s.range).length;

            if (coverCount === 0) {
                blindCells++;
                // Cluster key — group nearby blind cells (rough clustering)
                const ck = Math.round(lat / (latStep * 5)) + ':' + Math.round(lng / (lngStep * 5));
                if (!blindClusterMap[ck]) {
                    blindClusterMap[ck] = { cells: [], lat: 0, lng: 0, count: 0 };
                }
                blindClusterMap[ck].cells.push(latlng);
                blindClusterMap[ck].lat += lat;
                blindClusterMap[ck].lng += lng;
                blindClusterMap[ck].count++;

                // Draw blind cell
                const r = L.rectangle(
                    [[lat, lng], [lat + latStep, lng + lngStep]],
                    {
                        color:       '#ff2222',
                        fillColor:   '#ff0000',
                        fillOpacity: 0.35,
                        weight:      0,
                        className:   'blind-cell',
                    }
                ).addTo(map);
                blindLayers.push(r);

            } else if (coverCount >= 2) {
                overlapCells++;
            } else {
                coveredCells++;
            }
        }
    }

    // Stats
    const pCov  = totalCells ? Math.round(((coveredCells + overlapCells) / totalCells) * 100) : 0;
    const pBlnd = totalCells ? Math.round((blindCells / totalCells) * 100) : 0;
    const pOvlp = totalCells ? Math.round((overlapCells / totalCells) * 100) : 0;

    setBar('covered', pCov);
    setBar('blind',   pBlnd);
    setBar('overlap', pOvlp);
    updateHeaderStats(pCov, blindCells);

    // Build blind cluster list
    const clusters = Object.values(blindClusterMap).sort((a, b) => b.count - a.count);
    const listEl = document.getElementById('blind-list');
    if (clusters.length === 0) {
        listEl.innerHTML = '<div class="blind-empty" style="color:#00ff88;">✔ Full coverage! No blind spots.</div>';
    } else {
        listEl.innerHTML = clusters.slice(0, 20).map((cl, i) => {
            const clat = (cl.lat / cl.count).toFixed(5);
            const clng = (cl.lng / cl.count).toFixed(5);
            const severity = cl.count > 40 ? 'high' : cl.count > 15 ? 'medium' : 'low';
            const sLabel  = cl.count > 40 ? 'HIGH' : cl.count > 15 ? 'MEDIUM' : 'LOW';
            return `<div class="blind-card" onclick="flyToBlind(${clat},${clng})">
                <div class="bc-label">BLIND ZONE #${i + 1}</div>
                <div class="bc-coord">${clat}, ${clng}</div>
                <div class="bc-coord">Area ≈ ${(cl.count * 30 * 30).toLocaleString()} m²</div>
                <span class="bc-severity ${severity}">${sLabel}</span>
            </div>`;
        }).join('');
    }

    document.getElementById('stat-blind').textContent = clusters.length;
}

function flyToBlind(lat, lng) {
    map.flyTo([lat, lng], 17, { duration: 1.2 });
}


// ── AUTO-SUGGEST ───────────────────────────────────────────
function autoSuggestSensors() {
    clearSuggestions();

    if (sensors.length === 0 && !zoneLayer) {
        alert('Place sensors or draw a zone first, then run Analyze, then Auto-Suggest.');
        return;
    }

    // If no blind analysis done yet, do it first
    if (blindLayers.length === 0) analyzeBlindSpots();

    // Collect blind cell centroids
    const bounds  = getBounds();
    const latStep = GRID_SIZE;
    const lngStep = GRID_SIZE;

    const blindCells = [];
    for (let lat = bounds.getSouth(); lat < bounds.getNorth(); lat += latStep) {
        for (let lng = bounds.getWest(); lng < bounds.getEast(); lng += lngStep) {
            const latlng = L.latLng(lat, lng);
            if (!isInsideZone(latlng)) continue;
            if (!isCovered(latlng)) blindCells.push(latlng);
        }
    }

    if (blindCells.length === 0) {
        document.getElementById('suggestion-list').innerHTML =
            '<div class="suggest-empty" style="color:#00ff88;">✔ No blind spots — no suggestions needed!</div>';
        return;
    }

    // k-means style clustering: find centroids of blind cell clusters
    const suggestions = computeSuggestions(blindCells, Math.min(5, Math.ceil(blindCells.length / 20)));

    const listEl = document.getElementById('suggestion-list');
    listEl.innerHTML = '';

    suggestions.forEach((pt, i) => {
        const sugId = 'SUG-' + String(i + 1).padStart(2, '0');

        // Draw suggestion marker on map
        const icon = L.divIcon({
            className: '',
            html: `<div class="suggest-marker">
                       <div class="sgm-ring"></div>
                       <div class="sgm-label">${sugId}</div>
                   </div>`,
            iconSize:   [40, 40],
            iconAnchor: [20, 20],
        });
        const m = L.marker([pt.lat, pt.lng], { icon }).addTo(map);
        const rng = parseInt(document.getElementById('cfg-range').value);
        const c = L.circle([pt.lat, pt.lng], {
            radius: rng,
            color: '#44aaff',
            fillColor: '#44aaff',
            fillOpacity: 0.08,
            weight: 1,
            dashArray: '5,4',
        }).addTo(map);
        suggestLayers.push(m, c);

        // Card in right panel
        const card = document.createElement('div');
        card.className = 'suggest-card';
        card.innerHTML = `<div class="sug-label">${sugId} — SUGGESTED POSITION</div>
            <div class="sug-detail">LAT: ${pt.lat.toFixed(5)}  LNG: ${pt.lng.toFixed(5)}</div>
            <div class="sug-detail">Covers ≈ ${pt.blindCount} blind cells</div>
            <button class="sug-add-btn" onclick="addSuggested(${pt.lat},${pt.lng},'${sugId}')">➕ DEPLOY HERE</button>`;
        card.onclick = () => map.flyTo([pt.lat, pt.lng], 17, { duration: 1 });
        listEl.appendChild(card);
    });
}

function computeSuggestions(blindCells, k) {
    // Simple greedy: pick cell covering the most uncovered cells
    const rng = parseInt(document.getElementById('cfg-range').value);
    let remaining = [...blindCells];
    const suggestions = [];

    for (let i = 0; i < k; i++) {
        if (remaining.length === 0) break;
        let best = null, bestCount = 0;

        // Sample candidates (every Nth blind cell for speed)
        const step = Math.max(1, Math.round(remaining.length / 60));
        for (let j = 0; j < remaining.length; j += step) {
            const cand = remaining[j];
            const covered = remaining.filter(c => map.distance(cand, c) <= rng).length;
            if (covered > bestCount) { bestCount = covered; best = cand; }
        }

        if (!best) break;
        suggestions.push({ lat: best.lat, lng: best.lng, blindCount: bestCount });

        // Remove cells covered by this suggestion
        remaining = remaining.filter(c => map.distance(best, c) > rng);
    }
    return suggestions;
}

function addSuggested(lat, lng, name) {
    const prevMode = mode;
    setMode('sensor');
    document.getElementById('cfg-name').value = name + '-DEPLOYED';
    placeSensor(L.latLng(lat, lng));
    setMode(prevMode);
    analyzeBlindSpots();
}


// ── STATS HELPERS ──────────────────────────────────────────
function setBar(which, pct) {
    document.getElementById('bar-' + which).style.width = pct + '%';
    document.getElementById('val-' + which).textContent = pct + '%';
}

function resetStats() {
    ['covered', 'blind', 'overlap'].forEach(w => setBar(w, 0));
    updateHeaderStats(0, 0);
}

function runCoverageStats() {
    if (sensors.length === 0) { resetStats(); return; }
    // Quick approximate coverage %
    const bounds  = getBounds();
    const latStep = GRID_SIZE * 2;   // coarser grid for live stats
    const lngStep = GRID_SIZE * 2;
    let total = 0, cov = 0, over = 0, blind = 0;

    for (let lat = bounds.getSouth(); lat < bounds.getNorth(); lat += latStep) {
        for (let lng = bounds.getWest(); lng < bounds.getEast(); lng += lngStep) {
            const latlng = L.latLng(lat, lng);
            if (!isInsideZone(latlng)) continue;
            total++;
            const cnt = sensors.filter(s => latLngToMeters(latlng, s.latlng) <= s.range).length;
            if (cnt === 0) blind++;
            else if (cnt >= 2) over++;
            else cov++;
        }
    }
    const pCov  = total ? Math.round(((cov + over) / total) * 100) : 0;
    const pBlnd = total ? Math.round((blind  / total) * 100) : 0;
    const pOvlp = total ? Math.round((over   / total) * 100) : 0;
    setBar('covered', pCov);
    setBar('blind',   pBlnd);
    setBar('overlap', pOvlp);
    updateHeaderStats(pCov, null);
}

function updateHeaderStats(coveragePct, blindCount) {
    if (coveragePct !== undefined && coveragePct !== null)
        document.getElementById('stat-coverage').textContent = coveragePct + '%';
    if (blindCount !== null && blindCount !== undefined)
        document.getElementById('stat-blind').textContent = blindCount;
    document.getElementById('stat-sensors').textContent = sensors.length;
}


// ── EXPORT ─────────────────────────────────────────────────
function exportReport() {
    const report = {
        timestamp: new Date().toISOString(),
        sensors: sensors.map(s => ({
            id: s.id, name: s.name, type: s.type,
            lat: s.latlng.lat, lng: s.latlng.lng, range: s.range,
        })),
        zone: zonePoints.map(p => ({ lat: p.lat, lng: p.lng })),
        coverage_pct: document.getElementById('stat-coverage').textContent,
        blind_spot_count: document.getElementById('stat-blind').textContent,
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = 'aegis_coverage_report.json';
    a.click();
    URL.revokeObjectURL(url);
}


// ── CUSTOM MARKER STYLES (injected) ───────────────────────
function injectMarkerCSS() {
    const style = document.createElement('style');
    style.textContent = `
        .sensor-marker {
            position: relative;
            width: 40px; height: 40px;
            display: flex; align-items: center; justify-content: center;
        }
        .sm-ring {
            position: absolute;
            width: 32px; height: 32px;
            border-radius: 50%;
            border: 2px solid var(--col, #cc44ff);
            box-shadow: 0 0 12px var(--col, #cc44ff);
            animation: sensor-pulse 1.5s ease-in-out infinite;
        }
        .sm-dot {
            width: 10px; height: 10px;
            border-radius: 50%;
            background: var(--col, #cc44ff);
            box-shadow: 0 0 8px var(--col, #cc44ff);
            z-index: 1;
        }
        .sm-label {
            position: absolute;
            bottom: -18px;
            font-family: 'Orbitron', sans-serif;
            font-size: 8px;
            color: var(--col, #cc44ff);
            white-space: nowrap;
            letter-spacing: 1px;
            text-shadow: 0 0 6px var(--col, #cc44ff);
        }
        @keyframes sensor-pulse {
            0%,100% { opacity:1; transform: scale(1); }
            50%      { opacity:.4; transform: scale(1.2); }
        }
        .suggest-marker {
            position: relative;
            width: 40px; height: 40px;
            display: flex; align-items: center; justify-content: center;
        }
        .sgm-ring {
            position: absolute;
            width: 32px; height: 32px;
            border-radius: 50%;
            border: 2px dashed #44aaff;
            box-shadow: 0 0 14px #44aaff;
            animation: sug-spin 3s linear infinite;
        }
        .sgm-label {
            font-family: 'Orbitron', sans-serif;
            font-size: 8px;
            color: #44aaff;
            letter-spacing: 1px;
            z-index: 1;
        }
        @keyframes sug-spin { to { transform: rotate(360deg); } }
    `;
    document.head.appendChild(style);
}


// ── INIT ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    injectMarkerCSS();

    map = L.map('map', {
        center:   [26.8467, 80.9462],
        zoom:     17,
        zoomControl:     true,
        attributionControl: false,
        doubleClickZoom: false,
    });

    // Primary dark tiles
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 22,
        attribution: '© CartoDB',
    }).addTo(map);

    map.on('click', onMapClick);

    // Double-click to finish zone drawing
    map.on('dblclick', e => {
        if (mode === 'zone' && zonePoints.length >= 3) {
            zonePoints.push(e.latlng);
            finalizeZone();
        }
    });

    setMode('sensor');
});