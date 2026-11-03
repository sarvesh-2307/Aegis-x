/* ============================================================
   AEGIS-X  ·  script.js  v10
   ============================================================ */

let zoomed      = false;
let radarAngle  = 0;
let visionLog   = [];
let scoreHistory = [];   // sparkline history (max 20)
let recording   = false;
let alertActive = false;
let emergencyMode = false;

// ===================================================
// EMERGENCY SYSTEM
// ===================================================

function triggerEmergency() {
    emergencyMode = !emergencyMode;
    const btn = document.getElementById('btn-emergency');
    const header = document.querySelector('.header');
    
    if (emergencyMode) {
        // Activate emergency mode
        btn.classList.add('triggered');
        header.style.background = 'rgba(255, 0, 0, 0.25)';
        header.style.borderBottomColor = '#ff0000';
        
        // Create fullscreen overlay
        const overlay = document.createElement('div');
        overlay.id = 'emergency-overlay';
        overlay.className = 'emergency-overlay';
        document.body.appendChild(overlay);
        
        // Trigger alert
        alert('🚨 EMERGENCY MODE ACTIVATED 🚨');
        
        console.warn('EMERGENCY MODE ON');
    } else {
        // Deactivate emergency mode
        btn.classList.remove('triggered');
        header.style.background = 'rgba(20,0,0,0.85)';
        header.style.borderBottomColor = 'rgba(255,51,51,0.6)';
        
        const overlay = document.getElementById('emergency-overlay');
        if (overlay) overlay.remove();
        
        console.warn('EMERGENCY MODE OFF');
    }
}

// ===================================================
// FEATURE BUTTONS
// ===================================================

function toggleRecord() {
    recording = !recording;
    const btn = document.getElementById('btn-record');
    if (recording) {
        btn.classList.add('active');
        btn.style.boxShadow = '0 0 20px rgba(255, 100, 0, 0.8), inset 0 0 10px rgba(255, 100, 0, 0.2)';
        console.log('🎥 Recording started...');
        
        // Send to backend
        fetch('/record', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action: 'start'})
        }).catch(e => console.warn('Recording error:', e));
    } else {
        btn.classList.remove('active');
        btn.style.boxShadow = '0 0 8px rgba(255, 215, 0, 0.2)';
        console.log('⏹ Recording stopped.');
        
        // Send to backend
        fetch('/record', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action: 'stop'})
        }).catch(e => console.warn('Recording error:', e));
    }
}

function takeSnapshot() {
    const btn = document.getElementById('btn-snapshot');
    btn.classList.add('active');
    btn.style.animation = 'btn-emergency-trigger 0.4s ease';
    console.log('📸 Snapshot capturing...');
    
    // Send to backend
    fetch('/snapshot', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({})
    })
    .then(r => r.json())
    .then(d => {
        console.log('✅ Snapshot saved:', d.filename);
        showNotification('📸 SNAPSHOT CAPTURED', d.filename);
    })
    .catch(e => {
        console.warn('Snapshot error:', e);
        showNotification('❌ SNAPSHOT FAILED', 'Error saving snapshot');
    });
    
    setTimeout(() => {
        btn.classList.remove('active');
        btn.style.animation = 'none';
    }, 500);
}

function toggleAlert() {
    alertActive = !alertActive;
    const btn = document.getElementById('btn-alert');
    if (alertActive) {
        btn.classList.add('active');
        console.log('🔔 Alert system ACTIVATED');
        
        // Show alert hover on screen
        showAlertHover('ALERT SYSTEM ACTIVE ⚠️');
        
        // Send to backend
        fetch('/alert', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({type: 'ACTIVATION', threat_level: 'MEDIUM'})
        }).catch(e => console.warn('Alert error:', e));
    } else {
        btn.classList.remove('active');
        console.log('🔔 Alert system DEACTIVATED');
    }
}

// ===================================================
// ALERT & NOTIFICATION SYSTEM
// ===================================================

function showAlertHover(message) {
    const hover = document.createElement('div');
    hover.className = 'alert-hover';
    hover.innerHTML = message;
    document.body.appendChild(hover);
    
    // Animate in
    setTimeout(() => hover.classList.add('show'), 10);
    
    // Remove after 3 seconds
    setTimeout(() => {
        hover.classList.remove('show');
        setTimeout(() => hover.remove(), 300);
    }, 3000);
}

function showNotification(title, message) {
    const notif = document.createElement('div');
    notif.className = 'notification';
    notif.innerHTML = `<div class="notif-title">${title}</div><div class="notif-msg">${message}</div>`;
    document.body.appendChild(notif);
    
    // Animate in
    setTimeout(() => notif.classList.add('show'), 10);
    
    // Remove after 4 seconds
    setTimeout(() => {
        notif.classList.remove('show');
        setTimeout(() => notif.remove(), 300);
    }, 4000);
}

// ===================================================
// ZOOM / PANEL SYSTEM
// ===================================================

function zoomPanel(boxEl) {
    if (zoomed) return;          // already zoomed somewhere
    let grid = document.getElementById('grid');
    grid.classList.add('zoom-active');
    boxEl.classList.add('active');
    zoomed = true;
}

function exitZoom(e) {
    if (e) e.stopPropagation();
    let grid = document.getElementById('grid');
    grid.classList.remove('zoom-active');
    document.querySelectorAll('.box').forEach(b => {
        b.classList.remove('active', 'data-open');
    });
    // Reset toggle buttons
    document.querySelectorAll('.btn-toggle').forEach(btn => {
        btn.innerText = 'OPEN DATA ▶';
    });
    zoomed = false;
}

function toggleData(e, panelId, btnId) {
    e.stopPropagation();
    let box = document.getElementById('box-' + panelId.split('-')[0]);  // e.g. 'thermal-data' -> box-thermal
    let btn = document.getElementById(btnId);

    if (!box) return;

    if (box.classList.contains('data-open')) {
        box.classList.remove('data-open');
        btn.innerText = 'OPEN DATA ▶';
    } else {
        box.classList.add('data-open');
        btn.innerText = '◀ CLOSE DATA';
    }
}

// ===================================================
// ACCORDION
// ===================================================

function toggleAcc(btn) {
    event.stopPropagation();   // don't trigger zoomPanel onclick
    btn.classList.toggle('open');
}

// ===================================================
// ADD CLICK HANDLERS TO BOXES (so click body zooms)
// ===================================================

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.box').forEach(box => {
        box.addEventListener('click', function() {
            zoomPanel(this);
        });
        // Keep data panels always visible
        box.classList.add('data-always-open');
    });
});

// ===================================================
// LIVE DATA UPDATER
// ===================================================

function update() {
    fetch('/data')
        .then(r => r.json())
        .then(d => {
            if (!d || !d.fusion) return;

            const fusion = d.fusion;
            const exp    = d.explanation || {};
            const thermal = d.thermal  || {};
            const radar   = d.radar    || {};
            const vision  = d.vision   || {};

            // ---------- RADAR VISUAL ----------
            const dot   = document.getElementById('target-dot');
            const stage = document.querySelector('.radar-stage');
            if (dot && stage) {
                if (radar.presence) {
                    dot.style.display = 'block';
                    const sz = stage.offsetWidth;
                    const cx = sz / 2, cy = sz / 2;
                    const maxR = sz / 2 - 12;
                    const r = Math.min((radar.distance || 0) / 10, 0.95) * maxR;
                    radarAngle += 0.04;
                    dot.style.left = (cx + r * Math.cos(radarAngle)) + 'px';
                    dot.style.top  = (cy + r * Math.sin(radarAngle)) + 'px';
                    // Color by threat
                    const c = {CRITICAL:'#ff0000', HIGH:'#ff6600', MEDIUM:'#ffcc00'}[fusion.level] || '#00ff66';
                    dot.style.background   = c;
                    dot.style.boxShadow    = `0 0 14px ${c}, 0 0 28px ${c}`;
                } else {
                    dot.style.display = 'none';
                }
            }

            // ---------- THERMAL DATA ----------
            setText('th-temp',    thermal.temp    !== undefined ? thermal.temp.toFixed(1) + '°C' : '---');
            setText('th-ambient', thermal.ambient !== undefined ? thermal.ambient.toFixed(1) + '°C' : '---');
            setText('th-area',    thermal.area    !== undefined ? thermal.area.toLocaleString() : '---');

            // Distance category
            const area = thermal.area || 0;
            let distLabel = 'FAR';
            if      (area > 25000) distLabel = 'CLOSE (<2m)';
            else if (area > 12000) distLabel = 'MED (~3-5m)';
            setText('th-dist',    distLabel);

            // Posture
            const ratio = thermal.ratio;
            setText('th-posture', ratio !== undefined ? (ratio < 0.8 ? '🔴 CRAWLING' : '🟢 STANDING') : '---');

            // Env analysis
            const envEl = document.getElementById('th-env');
            if (envEl) {
                if (thermal.temp > (thermal.ambient || 0) + 2) {
                    envEl.innerHTML = '<span style="color:#ff4444">⚠ Heat signature exceeds ambient baseline.</span>';
                } else {
                    envEl.innerHTML = '<span style="color:#00cc44">✔ Ambient temperature normal.</span>';
                }
            }

            // Object analysis
            const objEl = document.getElementById('th-obj');
            if (objEl) {
                objEl.innerText = thermal.movement
                    ? '🔴 Movement trajectory detected.'
                    : '✔ Static thermal signature.';
            }

            // ---------- RADAR DATA ----------
            setText('r-dist', radar.distance !== undefined ? radar.distance.toFixed(1) : '---');
            setBadge('r-motion',   radar.motion,       'DETECTED', 'CLEAR');
            setBadge('r-micro',    radar.micro_motion, 'YES',      'NO');
            setBadge('r-presence', radar.presence,     'YES',      'NO');

            // ---------- VISION DATA ----------
            const vCount = document.getElementById('v-count');
            const vItems = document.getElementById('v-items');
            if (vCount && vItems) {
                if (vision.type && vision.type !== 'unknown') {
                    vCount.innerText = '1';
                    vItems.innerHTML = `<li>${vision.type.toUpperCase()} — ${vision.confidence}% confidence</li>`;
                    // Detection log
                    const now = new Date();
                    const ts  = `${now.getHours()}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
                    const entry = `[${ts}] ${vision.type.toUpperCase()} DETECTED (${vision.confidence}%)`;
                    if (!visionLog.includes(entry)) {
                        visionLog.unshift(entry);
                        if (visionLog.length > 20) visionLog.pop();
                        const logUl = document.getElementById('v-log');
                        if (logUl) logUl.innerHTML = visionLog.map(l => `<li>${l}</li>`).join('');
                    }
                } else {
                    vCount.innerText = '0';
                    vItems.innerHTML = '<li>No targets detected.</li>';
                }
            }

            // ---------- THREAT PANEL ----------
            const score = fusion.score || 0;
            let barColor = '#00cc00';
            if      (score > 80) barColor = '#ff0000';
            else if (score > 60) barColor = '#ff4400';
            else if (score > 40) barColor = '#ffaa00';
            else if (score > 20) barColor = '#ffdd00';

            // Level badge
            const levelBadge = document.getElementById('t-level');
            if (levelBadge) {
                levelBadge.innerText = fusion.level || 'NONE';
                levelBadge.style.color      = barColor;
                levelBadge.style.textShadow = `0 0 30px ${barColor}, 0 0 60px ${barColor}55`;
            }

            // Threat score bar
            const bar = document.getElementById('t-bar');
            if (bar) {
                bar.style.width      = score + '%';
                bar.style.background = barColor;
                bar.style.boxShadow  = `0 0 12px ${barColor}`;
            }

            setText('t-score', score + ' / 100');

            // ---------- SENSOR CONFIDENCE BARS ----------
            const conf = fusion.confidence || {};
            setSensorBar('thermal', conf.thermal || 0);
            setSensorBar('radar',   conf.radar   || 0);
            setSensorBar('vision',  conf.vision  || 0);

            // ---------- SPARKLINE UPDATE ----------
            scoreHistory.push(score);
            if (scoreHistory.length > 20) scoreHistory.shift();
            drawSparkline(scoreHistory, barColor);

            // Cards with enhanced sensor-specific information
            setText('t-summary', exp.summary || '---');
            
            // Display timestamp
            const timestampEl = document.getElementById('t-timestamp');
            if (timestampEl && exp.time_str) {
                timestampEl.innerHTML = `<span style="color:#00ff88;">🕐 ${exp.time_str}</span>`;
            }

            const confEl = document.getElementById('t-confidence');
            if (confEl && exp.confidence_visual) {
                const cv = exp.confidence_visual;
                confEl.innerHTML =
                    `THERMAL: ${cv.thermal || '---'}<br>` +
                    `RADAR:   ${cv.radar   || '---'}<br>` +
                    `VISION:  ${cv.vision  || '---'}`;
            }

            // Detailed sensor reports
            const sensorReportsEl = document.getElementById('t-sensor-reports');
            if (sensorReportsEl && exp.sensor_reports) {
                let reportsHtml = '<div style="font-size:11px; line-height:1.6;">';
                if (exp.sensor_reports.thermal) reportsHtml += `<div>${exp.sensor_reports.thermal}</div>`;
                if (exp.sensor_reports.radar) reportsHtml += `<div>${exp.sensor_reports.radar}</div>`;
                if (exp.sensor_reports.vision) reportsHtml += `<div>${exp.sensor_reports.vision}</div>`;
                reportsHtml += '</div>';
                sensorReportsEl.innerHTML = reportsHtml;
            }

            const logEl = document.getElementById('t-log');
            if (logEl && exp.log) {
                logEl.innerHTML = exp.log.length
                    ? exp.log.map(l => `• ${l}`).join('<br>')
                    : 'No anomalies logged.';
            }

            const behavEl = document.getElementById('t-behavior');
            if (behavEl && exp.analysis) {
                behavEl.innerHTML = exp.analysis.length
                    ? exp.analysis.join('<br>')
                    : 'Normal baseline activity.';
            }
            
            // Display verdict
            const verdictEl = document.getElementById('t-verdict');
            if (verdictEl && exp.verdict) {
                verdictEl.innerHTML = exp.verdict;
                let verdictColor = '#00ff88';
                if (exp.threat_level === 'CRITICAL') verdictColor = '#ff0000';
                else if (exp.threat_level === 'HIGH') verdictColor = '#ff6600';
                else if (exp.threat_level === 'MEDIUM') verdictColor = '#ffaa00';
                verdictEl.style.color = verdictColor;
            }
        })
        .catch(err => console.warn('Data fetch error:', err));
}

// ===================================================
// HELPERS
// ===================================================

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.innerText = val;
}

function setBadge(id, condition, trueLabel, falseLabel) {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerText   = condition ? trueLabel : falseLabel;
    el.className   = 'badge-status ' + (condition ? 'detected' : 'clear');
}

function pad(n) { return String(n).padStart(2,'0'); }

// ----- SENSOR CONFIDENCE BAR -----
function setSensorBar(sensor, pct) {
    pct = Math.min(100, Math.max(0, pct));
    const fill = document.getElementById('bar-' + sensor);
    const label = document.getElementById('pct-' + sensor);
    if (fill) {
        fill.style.width = pct + '%';
        // glow intensity scales with value
        const glow = sensor === 'thermal' ? '#ff5500'
                   : sensor === 'radar'   ? '#0099ff'
                   :                        '#00cc66';
        fill.style.boxShadow = pct > 5 ? `0 0 ${8 + pct/10}px ${glow}` : 'none';
    }
    if (label) label.innerText = pct + '%';
}

// ----- SPARKLINE CANVAS CHART -----
function drawSparkline(history, lineColor) {
    const canvas = document.getElementById('spark-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    if (history.length < 2) return;

    const maxPts = 20;
    const pts = history.slice(-maxPts);
    const stepX = W / (maxPts - 1);

    // Grid lines at 25 / 50 / 75
    ctx.strokeStyle = 'rgba(255,215,0,0.08)';
    ctx.lineWidth = 1;
    [0.25, 0.5, 0.75].forEach(f => {
        const y = H - f * H;
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    });

    // Area fill under the line
    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, lineColor + '55');
    grad.addColorStop(1, 'transparent');
    ctx.beginPath();
    pts.forEach((v, i) => {
        const x = i * stepX;
        const y = H - (v / 100) * H;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.lineTo((pts.length - 1) * stepX, H);
    ctx.lineTo(0, H);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Glowing line
    ctx.beginPath();
    pts.forEach((v, i) => {
        const x = i * stepX;
        const y = H - (v / 100) * H;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 2.5;
    ctx.shadowColor = lineColor;
    ctx.shadowBlur = 10;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Dot on latest point
    const lx = (pts.length - 1) * stepX;
    const ly = H - (pts[pts.length - 1] / 100) * H;
    ctx.beginPath();
    ctx.arc(lx, ly, 5, 0, Math.PI * 2);
    ctx.fillStyle = lineColor;
    ctx.shadowColor = lineColor;
    ctx.shadowBlur = 14;
    ctx.fill();
    ctx.shadowBlur = 0;
}

// Apply color classes to bar fills on first load
document.addEventListener('DOMContentLoaded', () => {
    const t = document.getElementById('bar-thermal');
    const r = document.getElementById('bar-radar');
    const v = document.getElementById('bar-vision');
    if (t) t.classList.add('thermal');
    if (r) r.classList.add('radar');
    if (v) v.classList.add('vision');
});

// ===================================================
// INIT
// ===================================================

setInterval(update, 500);
update();   // fetch immediately on load

// ===================================================
// DATASET DOWNLOAD
// ===================================================

function downloadDataset() {
    console.log('📥 Downloading dataset...');
    
    fetch('/api/download-dataset')
        .then(response => response.blob())
        .then(blob => {
            // Create download link
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `AEGIS_dataset_${new Date().toISOString().slice(0,10)}.json`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
            
            showNotification('✅ DATASET DOWNLOADED', 'Successfully exported intrusion log');
        })
        .catch(err => {
            console.error('Download error:', err);
            showNotification('❌ DOWNLOAD FAILED', 'Error exporting dataset');
        });
}

function viewLogs() {
    console.log('📋 Opening intruder log viewer...');
    window.open('/logs', 'AEGIS_IntruderLog', 'width=1400,height=800');
}