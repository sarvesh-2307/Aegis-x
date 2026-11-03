# AEGIS-X — data_logger.py
# Persistent SQLite event database
# Stores every intrusion/detection event with full sensor snapshot
# DB path: logs/aegis_events.db  (auto-created on first run)

import sqlite3
import time
import json
import os
import csv
import io
from datetime import datetime

# ── Path ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR  = os.path.join(BASE_DIR, 'logs')
RECORDINGS_DIR = os.path.join(LOG_DIR, 'recordings')
SNAPSHOTS_DIR = os.path.join(LOG_DIR, 'snapshots')
DB_PATH  = os.path.join(LOG_DIR,  'aegis_events.db')

# Ensure directories exist
os.makedirs(RECORDINGS_DIR, exist_ok=True)
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)

# ── Throttle config ───────────────────────────────────
INTERVAL_CRITICAL = 1.5    # seconds between logs when CRITICAL
INTERVAL_HIGH     = 3.0
INTERVAL_MEDIUM   = 8.0
INTERVAL_LOW      = 15.0
INTERVAL_NONE     = 60.0   # periodic heartbeat

# ── Internal state ────────────────────────────────────
_last_log_time     = 0.0
_last_threat_level = "__INIT__"


# ======================================================
# DB SCHEMA INIT
# ======================================================
def _init_db():
    os.makedirs(LOG_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp             TEXT    NOT NULL,
            unix_time             REAL    NOT NULL,
            event_type            TEXT    NOT NULL,

            threat_level          TEXT,
            threat_score          INTEGER,

            vision_type           TEXT,
            vision_confidence     INTEGER,

            radar_distance        REAL,
            radar_speed_kmh       REAL,
            radar_zone            TEXT,
            radar_presence        INTEGER,
            radar_motion          INTEGER,
            radar_micro           INTEGER,
            radar_approaching     INTEGER,
            radar_speed_label     TEXT,

            thermal_temp          REAL,
            thermal_ambient       REAL,
            thermal_cluster_count INTEGER,
            thermal_movement      INTEGER,
            thermal_threshold_low  REAL,
            thermal_threshold_high REAL,
            thermal_clusters      TEXT,   -- JSON array

            reasons               TEXT    -- JSON array
        )
    ''')
    # Recordings table
    con.execute('''
        CREATE TABLE IF NOT EXISTS recordings (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            filename      TEXT    NOT NULL UNIQUE,
            timestamp     TEXT    NOT NULL,
            unix_time     REAL    NOT NULL,
            duration_sec  REAL,
            file_size     INTEGER,
            threat_level  TEXT
        )
    ''')
    # Snapshots table  
    con.execute('''
        CREATE TABLE IF NOT EXISTS snapshots (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            filename     TEXT    NOT NULL UNIQUE,
            timestamp    TEXT    NOT NULL,
            unix_time    REAL    NOT NULL,
            file_size    INTEGER,
            sensor_type  TEXT,
            threat_level TEXT
        )
    ''')
    # Index for fast queries
    con.execute('CREATE INDEX IF NOT EXISTS idx_unix ON events(unix_time)')
    con.execute('CREATE INDEX IF NOT EXISTS idx_level ON events(threat_level)')
    con.execute('CREATE INDEX IF NOT EXISTS idx_rec_unix ON recordings(unix_time)')
    con.execute('CREATE INDEX IF NOT EXISTS idx_snap_unix ON snapshots(unix_time)')
    con.commit()
    con.close()
    print(f"✅ [Logger] Database ready at {DB_PATH}")
    print(f"✅ [Logger] Recordings stored at {RECORDINGS_DIR}")
    print(f"✅ [Logger] Snapshots stored at {SNAPSHOTS_DIR}")

_init_db()


# ======================================================
# SHOULD WE LOG THIS TICK?
# ======================================================
def should_log(threat_level: str, radar: dict, vision: dict) -> str | None:
    """
    Returns event_type string if we should write a row, else None.
    Event types: LEVEL_CHANGE | ALL_CLEAR | THREAT | PRESENCE | PERIODIC
    """
    global _last_log_time, _last_threat_level

    now = time.time()

    # Level change → always log immediately
    if threat_level != _last_threat_level:
        _last_threat_level = threat_level
        _last_log_time = now
        return 'ALL_CLEAR' if threat_level == 'NONE' else 'LEVEL_CHANGE'

    # Choose interval based on current level
    intervals = {
        'CRITICAL': INTERVAL_CRITICAL,
        'HIGH':     INTERVAL_HIGH,
        'MEDIUM':   INTERVAL_MEDIUM,
        'LOW':      INTERVAL_LOW,
        'NONE':     INTERVAL_NONE,
    }
    interval = intervals.get(threat_level, INTERVAL_NONE)

    if now - _last_log_time < interval:
        return None   # too soon

    # Determine event type
    _last_log_time = now
    if threat_level in ('HIGH', 'CRITICAL'):
        return 'THREAT'
    if radar.get('presence') or (vision.get('type', 'unknown') != 'unknown'):
        return 'PRESENCE'
    if threat_level != 'NONE':
        return 'PERIODIC'
    return None   # silent — no need to log


# ======================================================
# WRITE EVENT
# ======================================================
def log_event(event_type: str, score: int, threat: str,
              thermal: dict, radar: dict, vision: dict, reasons: list):
    """Insert one event row into the SQLite database."""
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        clusters_j = json.dumps(thermal.get('clusters', []),  ensure_ascii=False)
        reasons_j  = json.dumps(reasons,                      ensure_ascii=False)

        con = sqlite3.connect(DB_PATH, timeout=10)
        con.execute('''
            INSERT INTO events (
                timestamp, unix_time, event_type,
                threat_level, threat_score,
                vision_type, vision_confidence,
                radar_distance, radar_speed_kmh, radar_zone,
                radar_presence, radar_motion, radar_micro,
                radar_approaching, radar_speed_label,
                thermal_temp, thermal_ambient,
                thermal_cluster_count, thermal_movement,
                thermal_threshold_low, thermal_threshold_high,
                thermal_clusters, reasons
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            ts, time.time(), event_type,
            threat, int(score),
            vision.get('type', 'unknown'), int(vision.get('confidence', 0)),
            float(radar.get('distance', 0)),
            float(radar.get('speed_kmh', 0)),
            radar.get('zone', 'CLEAR'),
            int(bool(radar.get('presence',    False))),
            int(bool(radar.get('motion',      False))),
            int(bool(radar.get('micro_motion',False))),
            int(bool(radar.get('approaching', False))),
            radar.get('speed_label', 'STATIC'),
            float(thermal.get('temp',    0)),
            float(thermal.get('ambient', 0)),
            int(thermal.get('cluster_count', 0)),
            int(bool(thermal.get('movement', False))),
            float(thermal.get('threshold_low',  0)),
            float(thermal.get('threshold_high', 42)),
            clusters_j, reasons_j
        ))
        con.commit()
        con.close()
    except Exception as e:
        print(f"[Logger] Write error: {e}")


# ======================================================
# READ — for log viewer
# ======================================================
def get_events(limit=50, offset=0, level_filter=None, search=None):
    """Return (list_of_dicts, total_count)."""
    try:
        con = sqlite3.connect(DB_PATH, timeout=5)
        con.row_factory = sqlite3.Row

        where, params = [], []
        if level_filter and level_filter != 'ALL':
            where.append('threat_level = ?')
            params.append(level_filter)
        if search:
            where.append('(event_type LIKE ? OR vision_type LIKE ? OR radar_zone LIKE ?)')
            params += [f'%{search}%', f'%{search}%', f'%{search}%']

        where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

        total = con.execute(
            f'SELECT COUNT(*) FROM events {where_sql}', params
        ).fetchone()[0]

        rows = con.execute(
            f'SELECT * FROM events {where_sql} ORDER BY unix_time DESC LIMIT ? OFFSET ?',
            params + [limit, offset]
        ).fetchall()
        con.close()
        return [dict(r) for r in rows], total
    except Exception as e:
        print(f"[Logger] Read error: {e}")
        return [], 0


def get_summary():
    """Stats for the dashboard cards."""
    try:
        con = sqlite3.connect(DB_PATH, timeout=5)
        total      = con.execute('SELECT COUNT(*) FROM events').fetchone()[0]
        threats    = con.execute(
            "SELECT COUNT(*) FROM events WHERE threat_level IN ('HIGH','CRITICAL')"
        ).fetchone()[0]
        last_row   = con.execute(
            'SELECT timestamp, threat_level, threat_score FROM events ORDER BY unix_time DESC LIMIT 1'
        ).fetchone()
        highest    = con.execute(
            "SELECT threat_level FROM events WHERE threat_level != 'NONE' "
            "ORDER BY threat_score DESC LIMIT 1"
        ).fetchone()
        today_str  = datetime.now().strftime('%Y-%m-%d')
        today_cnt  = con.execute(
            "SELECT COUNT(*) FROM events WHERE timestamp LIKE ?", (today_str + '%',)
        ).fetchone()[0]
        con.close()
        return {
            'total':          total,
            'high_threats':   threats,
            'today':          today_cnt,
            'last_event':     dict(last_row) if last_row else None,
            'highest_threat': highest[0] if highest else 'NONE',
        }
    except Exception as e:
        print(f"[Logger] Summary error: {e}")
        return {'total': 0, 'high_threats': 0, 'today': 0, 'last_event': None, 'highest_threat': 'NONE'}


# ======================================================
# EXPORT — CSV bytes for download
# ======================================================
def export_csv():
    """Return CSV bytes of all events."""
    try:
        con = sqlite3.connect(DB_PATH, timeout=5)
        con.row_factory = sqlite3.Row
        rows = con.execute('SELECT * FROM events ORDER BY unix_time DESC').fetchall()
        con.close()

        buf = io.StringIO()
        if rows:
            w = csv.DictWriter(buf, fieldnames=rows[0].keys())
            w.writeheader()
            for r in rows:
                w.writerow(dict(r))
        return buf.getvalue().encode('utf-8')
    except Exception as e:
        print(f"[Logger] CSV export error: {e}")
        return b''


# ======================================================
# RECORDING MANAGEMENT
# ======================================================
def log_recording(filename: str, duration_sec: float, threat_level: str = "NONE"):
    """Log a screen recording with timestamp and metadata."""
    try:
        file_path = os.path.join(RECORDINGS_DIR, filename)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        con = sqlite3.connect(DB_PATH, timeout=10)
        con.execute('''
            INSERT INTO recordings (filename, timestamp, unix_time, duration_sec, file_size, threat_level)
            VALUES (?,?,?,?,?,?)
        ''', (filename, ts, time.time(), duration_sec, file_size, threat_level))
        con.commit()
        con.close()
        print(f"✅ [Logger] Recording logged: {filename}")
    except Exception as e:
        print(f"[Logger] Recording log error: {e}")


def get_recordings(limit=50, offset=0):
    """Get list of recordings with metadata."""
    try:
        con = sqlite3.connect(DB_PATH, timeout=5)
        con.row_factory = sqlite3.Row
        
        total = con.execute('SELECT COUNT(*) FROM recordings').fetchone()[0]
        rows = con.execute(
            'SELECT * FROM recordings ORDER BY unix_time DESC LIMIT ? OFFSET ?',
            [limit, offset]
        ).fetchall()
        con.close()
        return [dict(r) for r in rows], total
    except Exception as e:
        print(f"[Logger] Read recordings error: {e}")
        return [], 0


# ======================================================
# SNAPSHOT MANAGEMENT
# ======================================================
def log_snapshot(filename: str, sensor_type: str = "MULTI", threat_level: str = "NONE"):
    """Log a snapshot with timestamp and metadata."""
    try:
        file_path = os.path.join(SNAPSHOTS_DIR, filename)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        con = sqlite3.connect(DB_PATH, timeout=10)
        con.execute('''
            INSERT INTO snapshots (filename, timestamp, unix_time, file_size, sensor_type, threat_level)
            VALUES (?,?,?,?,?,?)
        ''', (filename, ts, time.time(), file_size, sensor_type, threat_level))
        con.commit()
        con.close()
        print(f"✅ [Logger] Snapshot logged: {filename}")
    except Exception as e:
        print(f"[Logger] Snapshot log error: {e}")


def get_snapshots(limit=50, offset=0, sensor_filter=None):
    """Get list of snapshots with metadata."""
    try:
        con = sqlite3.connect(DB_PATH, timeout=5)
        con.row_factory = sqlite3.Row
        
        where = []
        params = []
        if sensor_filter and sensor_filter != 'ALL':
            where.append('sensor_type = ?')
            params.append(sensor_filter)
        
        where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''
        total = con.execute(f'SELECT COUNT(*) FROM snapshots {where_sql}', params).fetchone()[0]
        rows = con.execute(
            f'SELECT * FROM snapshots {where_sql} ORDER BY unix_time DESC LIMIT ? OFFSET ?',
            params + [limit, offset]
        ).fetchall()
        con.close()
        return [dict(r) for r in rows], total
    except Exception as e:
        print(f"[Logger] Read snapshots error: {e}")
        return [], 0


# ======================================================
# INTRUSION LOG - FULL DATASET EXPORT
# ======================================================
def get_intrusion_log(start_time=None, end_time=None, threat_level_filter=None):
    """Get complete intrusion log with all related recordings and snapshots."""
    try:
        con = sqlite3.connect(DB_PATH, timeout=5)
        con.row_factory = sqlite3.Row
        
        # Base query for events
        where = []
        params = []
        
        if threat_level_filter and threat_level_filter != 'ALL':
            where.append("threat_level IN ('HIGH','CRITICAL')")
        if start_time:
            where.append("unix_time >= ?")
            params.append(start_time)
        if end_time:
            where.append("unix_time <= ?")
            params.append(end_time)
        
        where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''
        
        events = con.execute(
            f'SELECT * FROM events {where_sql} ORDER BY unix_time DESC',
            params
        ).fetchall()
        
        recordings = con.execute(
            'SELECT * FROM recordings ORDER BY unix_time DESC LIMIT 100'
        ).fetchall()
        
        snapshots = con.execute(
            'SELECT * FROM snapshots ORDER BY unix_time DESC LIMIT 100'
        ).fetchall()
        
        con.close()
        
        return {
            'events': [dict(r) for r in events],
            'recordings': [dict(r) for r in recordings],
            'snapshots': [dict(r) for r in snapshots],
            'export_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        print(f"[Logger] Get intrusion log error: {e}")
        return {'events': [], 'recordings': [], 'snapshots': [], 'export_time': ''}