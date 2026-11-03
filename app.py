from flask import Flask, render_template, Response, jsonify, request, send_file
import threading
import time
import json
import os
from datetime import datetime

from sensors.thermal import thermal_loop, generate_thermal, latest_thermal
from sensors.radar import radar_loop, latest_radar
from sensors.vision import vision_loop, generate_vision, latest_vision

from fusion_engine import fusion_engine
from explanation import generate_explanation
from data_logger import log_recording, log_snapshot, get_recordings, get_snapshots, get_intrusion_log, SNAPSHOTS_DIR, RECORDINGS_DIR, log_event, should_log

app = Flask(__name__)

# ===== RPi OPTIMIZATION FLAGS =====
# Reduce frame rate and processing on Raspberry Pi for smooth performance
import platform
is_rpi = 'arm' in platform.machine().lower() or 'aarch64' in platform.machine().lower()
FRAME_SKIP = 2 if is_rpi else 1  # Skip frames on RPi to reduce load
frame_count = 0

# ===== THREAD START =====
def start_threads():
    threading.Thread(target=thermal_loop, daemon=True).start()
    time.sleep(1)

    threading.Thread(target=radar_loop, daemon=True).start()
    time.sleep(1)

    threading.Thread(target=vision_loop, daemon=True).start()

start_threads()


# ===== ROUTES =====
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/thermal_feed")
def thermal_feed():
    return Response(generate_thermal(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route("/vision_feed")
def vision_feed():
    return Response(generate_vision(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# ===== DATA =====
@app.route("/data")
def data():
    try:
        score, threat, reasons, confidence = fusion_engine(
            latest_thermal,
            latest_radar,
            latest_vision
        )

        explanation = generate_explanation(
            score, threat, reasons, confidence,
            thermal=latest_thermal,
            radar=latest_radar,
            vision=latest_vision
        )
        
        # ===== LOG EVENT TO DATABASE =====
        event_type = should_log(threat, latest_radar, latest_vision)
        if event_type:
            log_event(
                event_type=event_type,
                score=score,
                threat=threat,
                thermal=latest_thermal,
                radar=latest_radar,
                vision=latest_vision,
                reasons=reasons
            )
            print(f"📝 [Logger] Event logged: {event_type} | Threat: {threat} | Score: {score}/100")

        return jsonify({
            "thermal": latest_thermal,
            "radar": latest_radar,
            "vision": latest_vision,

            "fusion": {
                "score": score,
                "level": threat,
                "reasons": reasons,
                "confidence": confidence
            },

            "explanation": explanation
        })

    except Exception as e:
        return jsonify({
            "error": str(e),
            "fusion": {"score": 0, "level": "NONE"}
        })


# ===== ALERT SYSTEM =====
@app.route("/alert", methods=["POST"])
def alert():
    """Handle alert trigger with recording/documentation"""
    try:
        data = request.get_json() or {}
        alert_type = data.get('type', 'GENERAL')
        threat_level = data.get('threat_level', 'MEDIUM')
        
        print(f"🔔 ALERT TRIGGERED: {alert_type} (Level: {threat_level})")
        
        return jsonify({
            "status": "ok", 
            "alert": alert_type,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== EMERGENCY =====
@app.route("/emergency", methods=["POST"])
def emergency():
    """Handle emergency button trigger"""
    try:
        data = request.get_json() or {}
        status = data.get('status', 'unknown')
        
        if status == 'activated':
            print("🚨 EMERGENCY MODE ACTIVATED 🚨")
            # Log emergency event
            threat_score, threat_level, _, _ = fusion_engine(
                latest_thermal, latest_radar, latest_vision
            )
        else:
            print("✓ Emergency mode deactivated")
        
        return jsonify({"status": "ok", "emergency": status})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== RECORDING SYSTEM =====
@app.route("/record", methods=["POST"])
def record_action():
    """Start/stop screen recording"""
    try:
        action = request.get_json().get('action', 'start')
        
        if action == 'start':
            print("🎥 Recording started...")
            # In a real system, this would start ffmpeg or similar
            return jsonify({"status": "recording_started", "timestamp": datetime.now().isoformat()})
        elif action == 'stop':
            print("⏹ Recording stopped")
            # Save recording with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"recording_{timestamp}.mp4"
            score, threat, _, _ = fusion_engine(latest_thermal, latest_radar, latest_vision)
            log_recording(filename, duration_sec=60.0, threat_level=threat)
            return jsonify({"status": "recording_stopped", "filename": filename})
        
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== SNAPSHOT SYSTEM =====
@app.route("/snapshot", methods=["POST"])
def take_snapshot():
    """Capture snapshot from all sensors and save to dataset"""
    try:
        import cv2
        import numpy as np
        
        # Create multi-sensor snapshot
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Get current threat level
        score, threat, _, _ = fusion_engine(latest_thermal, latest_radar, latest_vision)
        
        # Create snapshot metadata
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'threat_level': threat,
            'threat_score': score,
            'thermal': latest_thermal,
            'radar': latest_radar,
            'vision': latest_vision
        }
        
        # Save metadata as JSON
        meta_filename = f"snapshot_{timestamp}_metadata.json"
        meta_path = os.path.join(SNAPSHOTS_DIR, meta_filename)
        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Log snapshot
        snap_filename = f"snapshot_{timestamp}.json"
        log_snapshot(snap_filename, sensor_type="MULTI", threat_level=threat)
        
        print(f"📸 Snapshot captured: {timestamp} | Threat: {threat}")
        
        return jsonify({
            "status": "snapshot_captured",
            "filename": snap_filename,
            "timestamp": datetime.now().isoformat(),
            "threat_level": threat
        })
    except Exception as e:
        print(f"Snapshot error: {e}")
        return jsonify({"error": str(e)}), 500


# ===== RECORDINGS LIST =====
@app.route("/api/recordings")
def api_recordings():
    """Get list of recordings"""
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        recordings, total = get_recordings(limit, offset)
        
        return jsonify({
            "recordings": recordings,
            "total": total,
            "path": RECORDINGS_DIR
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== SNAPSHOTS LIST =====
@app.route("/api/snapshots")
def api_snapshots():
    """Get list of snapshots"""
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        sensor_filter = request.args.get('sensor', 'ALL')
        
        snapshots, total = get_snapshots(limit, offset, sensor_filter)
        
        return jsonify({
            "snapshots": snapshots,
            "total": total,
            "path": SNAPSHOTS_DIR
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== INTRUSION LOG DATASET =====
@app.route("/api/intrusion-log")
def intrusion_log():
    """Get complete intrusion log with all events, recordings, snapshots"""
    try:
        start_time = request.args.get('start_time', type=float)
        end_time = request.args.get('end_time', type=float)
        threat_filter = request.args.get('threat_level', 'ALL')
        
        log_data = get_intrusion_log(start_time, end_time, threat_filter)
        
        return jsonify(log_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== DOWNLOAD DATASET =====
@app.route("/api/download-dataset")
def download_dataset():
    """Download complete intrusion dataset as JSON with all metadata"""
    try:
        log_data = get_intrusion_log()
        
        # Create comprehensive JSON export
        export_data = {
            'export_timestamp': datetime.now().isoformat(),
            'system': 'AEGIS-X',
            'data': log_data
        }
        
        # Create file for download
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"AEGIS_dataset_{timestamp}.json"
        filepath = os.path.join(LOG_DIR, filename)
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
            mimetype='application/json'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== DOWNLOAD SNAPSHOT =====
@app.route("/download/snapshot/<filename>")
def download_snapshot(filename):
    """Download a specific snapshot"""
    try:
        filepath = os.path.join(SNAPSHOTS_DIR, filename)
        if os.path.exists(filepath):
            return send_file(
                filepath,
                as_attachment=True,
                download_name=filename
            )
        return jsonify({"error": "Snapshot not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== DOWNLOAD RECORDING =====
@app.route("/download/recording/<filename>")
def download_recording(filename):
    """Download a specific recording"""
    try:
        filepath = os.path.join(RECORDINGS_DIR, filename)
        if os.path.exists(filepath):
            return send_file(
                filepath,
                as_attachment=True,
                download_name=filename
            )
        return jsonify({"error": "Recording not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== INTRUDER LOG VIEWER =====
@app.route("/logs")
def logs_viewer():
    """View complete intruder log with all recordings and snapshots"""
    return render_template("logs.html")


# ===== DETAILED EVENTS API =====
@app.route("/api/events-detailed")
def events_detailed():
    """Get events with detailed sensor information + snapshots + recordings in timeline"""
    try:
        from data_logger import get_events, get_snapshots, get_recordings
        
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        level_filter = request.args.get('level', 'ALL')
        date_filter = request.args.get('date', '')  # Format: YYYY-MM-DD
        
        # Get all data types
        events, total_events = get_events(limit=1000, offset=0)  # Get more events for merging
        snapshots, _ = get_snapshots(limit=1000, offset=0)
        recordings, _ = get_recordings(limit=1000, offset=0)
        
        # Format events with readable timestamps and explanations
        timeline = []
        
        # Add events
        for event in events:
            reasons_list = json.loads(event.get('reasons', '[]')) if event.get('reasons') else []
            
            # Create readable explanation
            explanation = []
            
            # Thermal part
            if event.get('thermal_temp'):
                temp_diff = event.get('thermal_temp', 0) - event.get('thermal_ambient', 0)
                explanation.append(
                    f"🔥 THERMAL: {event.get('thermal_temp')}°C ({temp_diff:+.1f}°C vs ambient) | "
                    f"Size: {event.get('thermal_cluster_count', 0)} clusters | "
                    f"Movement: {'Yes' if event.get('thermal_movement') else 'No'}"
                )
            
            # Radar part
            if event.get('radar_presence'):
                explanation.append(
                    f"📡 RADAR: {event.get('radar_distance', 0):.1f}m | "
                    f"Motion: {'Yes' if event.get('radar_motion') else 'No'} | "
                    f"Micro: {'Yes' if event.get('radar_micro') else 'No'}"
                )
            
            # Vision part
            if event.get('vision_type') != 'unknown':
                explanation.append(
                    f"👁️ VISION: {event.get('vision_type', 'unknown').upper()} "
                    f"({event.get('vision_confidence', 0)}% confidence)"
                )
            
            # Apply threat level filter
            if level_filter != 'ALL' and event.get('threat_level') != level_filter:
                continue
            
            # Apply date filter
            if date_filter:
                event_date = event.get('timestamp', '').split(' ')[0]  # Extract date part (YYYY-MM-DD)
                if event_date != date_filter:
                    continue
            
            timeline.append({
                'id': event.get('id'),
                'type': 'event',
                'timestamp': event.get('timestamp'),
                'unix_time': event.get('unix_time'),
                'event_type': event.get('event_type'),
                'threat_level': event.get('threat_level'),
                'threat_score': event.get('threat_score'),
                'display': f"🎯 {event.get('event_type')}",
                'sensor_readings': {
                    'thermal_temp': event.get('thermal_temp'),
                    'thermal_ambient': event.get('thermal_ambient'),
                    'radar_distance': event.get('radar_distance'),
                    'radar_motion': event.get('radar_motion'),
                    'vision_type': event.get('vision_type'),
                    'vision_confidence': event.get('vision_confidence'),
                },
                'explanation': explanation,
                'reasons': reasons_list
            })
        
        # Add snapshots
        for snapshot in snapshots:
            # Apply date filter
            if date_filter:
                snap_date = snapshot.get('timestamp', '').split(' ')[0]
                if snap_date != date_filter:
                    continue
                    
            timeline.append({
                'id': f"snap_{snapshot.get('id')}",
                'type': 'snapshot',
                'timestamp': snapshot.get('timestamp'),
                'unix_time': snapshot.get('unix_time'),
                'filename': snapshot.get('filename'),
                'display': f"📸 SNAPSHOT - {snapshot.get('sensor_type', 'MULTI')}",
                'threat_level': snapshot.get('threat_level', 'NONE'),
                'threat_score': 0,
                'file_size': snapshot.get('file_size', 0),
                'sensor_type': snapshot.get('sensor_type'),
                'explanation': [f"📸 Snapshot captured by {snapshot.get('sensor_type', 'MULTI')} sensor"],
                'reasons': []
            })
        
        # Add recordings
        for recording in recordings:
            # Apply date filter
            if date_filter:
                rec_date = recording.get('timestamp', '').split(' ')[0]
                if rec_date != date_filter:
                    continue
            timeline.append({
                'id': f"rec_{recording.get('id')}",
                'type': 'recording',
                'timestamp': recording.get('timestamp'),
                'unix_time': recording.get('unix_time'),
                'filename': recording.get('filename'),
                'display': f"🎥 RECORDING ({recording.get('duration_sec', 0):.1f}s)",
                'threat_level': recording.get('threat_level', 'NONE'),
                'threat_score': 0,
                'duration_sec': recording.get('duration_sec', 0),
                'file_size': recording.get('file_size', 0),
                'explanation': [f"🎥 Recording saved: {recording.get('duration_sec', 0):.1f} seconds"],
                'reasons': []
            })
        
        # Sort by unix_time descending (newest first)
        timeline.sort(key=lambda x: x.get('unix_time', 0), reverse=True)
        
        # Apply limit and offset
        total = len(timeline)
        paginated_timeline = timeline[offset:offset + limit]
        
        return jsonify({
            "events": paginated_timeline,
            "total": total,
            "limit": limit,
            "offset": offset
        })
    except Exception as e:
        print(f"Error in events_detailed: {e}")
        return jsonify({"error": str(e)}), 500


# ===== COMPREHENSIVE DATASET EXPORT =====
@app.route("/api/dataset-summary")
def dataset_summary():
    """Get summary of all datasets"""
    try:
        from data_logger import get_events, get_recordings, get_snapshots
        
        # Get counts
        events, total_events = get_events(limit=1, offset=0)
        recordings, total_recordings = get_recordings(limit=1, offset=0)
        snapshots, total_snapshots = get_snapshots(limit=1, offset=0)
        
        # Get threat levels distribution
        events_all, _ = get_events(limit=10000, offset=0)
        threat_distribution = {}
        for event in events_all:
            level = event.get('threat_level', 'NONE')
            threat_distribution[level] = threat_distribution.get(level, 0) + 1
        
        return jsonify({
            "summary": {
                "total_events": total_events,
                "total_recordings": total_recordings,
                "total_snapshots": total_snapshots,
                "threat_distribution": threat_distribution,
                "export_timestamp": datetime.now().isoformat(),
                "paths": {
                    "snapshots": SNAPSHOTS_DIR,
                    "recordings": RECORDINGS_DIR,
                    "database": os.path.join(LOG_DIR, 'aegis_events.db')
                }
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== RUN =====
if __name__ == "__main__":
    print(f"{'🍓 RPi Mode enabled' if is_rpi else '💻 Desktop Mode'}")
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)