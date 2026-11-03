# 🔥 AEGIS-X — thermal.py (Flask Module)
# Exports: thermal_loop(), generate_thermal(), latest_thermal
# RPi OPTIMIZED: Reduced refresh rate, frame skipping

import board
import busio
import adafruit_mlx90640
import numpy as np
import cv2
import time
import platform

# ======================================================
# PERFORMANCE CONFIG (RPi OPTIMIZED)
# ======================================================
is_rpi = 'arm' in platform.machine().lower() or 'aarch64' in platform.machine().lower()
SENSOR_REFRESH = adafruit_mlx90640.RefreshRate.REFRESH_2_HZ if is_rpi else adafruit_mlx90640.RefreshRate.REFRESH_4_HZ
JPEG_QUALITY_THERMAL = 70 if is_rpi else 80
print(f"🔥 [Thermal] Mode: {'RPi' if is_rpi else 'Desktop'} | Refresh: {'2Hz' if is_rpi else '4Hz'}")

# ======================================================
# SHARED STATE  — read by app.py + fusion_engine
# ======================================================
latest_thermal = {
    "temp":     0.0,
    "ambient":  0.0,
    "area":     0,
    "ratio":    1.0,
    "movement": False,
    "distance": 5.0,
}

# Internal frame buffer for MJPEG stream
_frame_jpg = None

# ======================================================
# MAIN THREAD LOOP  (runs as daemon thread in app.py)
# ======================================================
def thermal_loop():
    global latest_thermal, _frame_jpg

    # -------- I2C INIT --------
    i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
    mlx = adafruit_mlx90640.MLX90640(i2c)
    mlx.refresh_rate = SENSOR_REFRESH
    print(f"✅ [Thermal] MLX90640 initialized with refresh rate: {mlx.refresh_rate}")

    raw_frame = [0] * 768
    baseline = None
    prev_center = None
    alpha = 0.02  # adaptive calibration speed

    while True:
        # -------- READ SENSOR --------
        try:
            mlx.getFrame(raw_frame)
        except Exception as e:
            print(f"[Thermal] Frame read error: {e}")
            time.sleep(0.1)
            continue

        data = np.reshape(raw_frame, (24, 32))

        # -------- AMBIENT (mean of whole frame) --------
        ambient = float(np.mean(data))

        # -------- DYNAMIC BASELINE --------
        if baseline is None:
            baseline = data.copy()
            continue

        baseline = (1 - alpha) * baseline + alpha * data

        diff = data - baseline
        diff[diff < 0] = 0
        diff = np.clip(diff, 0, 5)
        norm = diff / 5.0

        # -------- UPSCALE --------
        img = cv2.resize(norm, (640, 480), interpolation=cv2.INTER_LINEAR)
        img = np.uint8(img * 255)

        # -------- SMOOTH --------
        img = cv2.GaussianBlur(img, (3, 3), 0)

        # -------- COLORMAP --------
        heatmap = cv2.applyColorMap(img, cv2.COLORMAP_INFERNO)

        # -------- THRESHOLD + CONTOURS --------
        _, thresh = cv2.threshold(img, 20, 255, cv2.THRESH_BINARY)
        kernel = np.ones((3, 3), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Reset defaults every frame
        area      = 0
        ratio     = 1.0
        temp      = ambient
        distance  = 5.0
        movement  = False

        if contours:
            filtered = [c for c in contours if cv2.contourArea(c) > 300]

            if filtered:
                all_points = np.vstack(filtered)
                x, y, w, h = cv2.boundingRect(all_points)

                cx = x + w // 2
                cy = y + h // 2
                area = w * h

                # -------- DISTANCE ESTIMATION --------
                frame_area = heatmap.shape[0] * heatmap.shape[1]
                rel = area / frame_area

                if   rel > 0.20: distance = 1.0
                elif rel > 0.10: distance = 2.0
                elif rel > 0.05: distance = 3.0
                elif rel > 0.02: distance = 4.0
                else:            distance = 5.0

                # -------- REAL TEMPERATURE --------
                scale_y = 24 / heatmap.shape[0]
                scale_x = 32 / heatmap.shape[1]
                roi = data[
                    int(y * scale_y):int((y + h) * scale_y),
                    int(x * scale_x):int((x + w) * scale_x)
                ]
                if roi.size > 0:
                    temp = float(np.max(roi))

                # -------- POSTURE RATIO --------
                ratio = h / (w + 1)

                # -------- MOVEMENT --------
                if prev_center:
                    dx = cx - prev_center[0]
                    dy = cy - prev_center[1]
                    movement = abs(dx) > 8 or abs(dy) > 8
                prev_center = (cx, cy)

                # -------- HUMAN FILTER --------
                human_flag = "HUMAN" if 0.5 < ratio < 3 else "UNKNOWN"
                posture    = "STANDING" if h > w else "CRAWLING"
                direction  = "STABLE"
                if prev_center and movement:
                    dx = cx - prev_center[0]
                    dy = cy - prev_center[1]
                    direction = ("RIGHT" if dx > 0 else "LEFT") if abs(dx) > abs(dy) else ("DOWN" if dy > 0 else "UP")

                # -------- DRAW OVERLAY ON HEATMAP --------
                cv2.rectangle(heatmap, (x, y), (x+w, y+h), (0, 255, 255), 2)
                cv2.circle(heatmap, (cx, cy), 5, (0, 255, 0), -1)

                cv2.putText(heatmap, f"TARGET ({human_flag})", (10, 28),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(heatmap, f"TEMP: {temp:.1f}C  DIST: {distance:.1f}m", (10, 56),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 200, 255), 2)
                cv2.putText(heatmap, f"POSTURE: {posture}  DIR: {direction}", (10, 82),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

        # -------- UPDATE SHARED STATE --------
        latest_thermal["temp"]     = round(temp, 1)
        latest_thermal["ambient"]  = round(ambient, 1)
        latest_thermal["area"]     = int(area)
        latest_thermal["ratio"]    = round(ratio, 3)
        latest_thermal["movement"] = bool(movement)
        latest_thermal["distance"] = distance

        # -------- ENCODE JPEG FOR STREAM --------
        # HUD border overlay
        cv2.rectangle(heatmap, (0, 0), (heatmap.shape[1]-1, heatmap.shape[0]-1), (255, 51, 51), 2)
        cv2.putText(heatmap, "AEGIS-X  THERMAL", (10, heatmap.shape[0]-12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 215, 0), 1)

        # RPi OPTIMIZED: Lower JPEG quality
        _, buf = cv2.imencode('.jpg', heatmap, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY_THERMAL])
        _frame_jpg = buf.tobytes()


# ======================================================
# MJPEG STREAM GENERATOR  (called by Flask /thermal_feed)
# ======================================================
def generate_thermal():
    global _frame_jpg
    while True:
        if _frame_jpg is None:
            time.sleep(0.05)
            continue
        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' +
            _frame_jpg +
            b'\r\n'
        )
        time.sleep(0.04)   # ~25 fps cap