# 👁️ AEGIS-X — vision.py (Haar Cascade — Face + Upper Body Detection)
# Exports: vision_loop(), generate_vision(), latest_vision
# RPi OPTIMIZED: Lower resolution, frame skipping, reduced processing

import cv2
import numpy as np
import time
import platform

# ======================================================
# PERFORMANCE CONFIG (RPi OPTIMIZED)
# ======================================================
is_rpi = 'arm' in platform.machine().lower() or 'aarch64' in platform.machine().lower()
FRAME_SKIP = 3 if is_rpi else 1          # Skip frames on RPi
RESOLUTION = (480, 360) if is_rpi else (640, 480)  # Lower res on RPi
JPEG_QUALITY = 60 if is_rpi else 82      # Lower JPEG quality on RPi
DETECTION_FREQ = 4 if is_rpi else 2      # Detect every Nth frame

print(f"👁️ [Vision] Mode: {'RPi' if is_rpi else 'Desktop'} | Resolution: {RESOLUTION} | Frame Skip: {FRAME_SKIP}")

# ======================================================
# SHARED STATE
# ======================================================
latest_vision = {
    "type":       "unknown",
    "confidence": 0
}

_frame_jpg    = None
_cap          = None
_face_cascade = None
_body_cascade = None


# ======================================================
# PLACEHOLDER FRAME
# ======================================================
def _make_placeholder(msg="NO SIGNAL"):
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (10, 0, 20)
    cv2.rectangle(img, (2, 2), (637, 477), (0, 51, 255), 2)
    cv2.putText(img, "AEGIS-X",        (220, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 51, 255), 2)
    cv2.putText(img, msg,              (60,  260), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
    cv2.putText(img, "VISION OFFLINE", (180, 320), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 100), 1)
    _, buf = cv2.imencode('.jpg', img)
    return buf.tobytes()


# ======================================================
# INIT HAAR CASCADE DETECTORS  (100% built-in to OpenCV)
# ======================================================
def _init_cascades():
    global _face_cascade, _body_cascade
    base = cv2.data.haarcascades   # built-in OpenCV path

    _face_cascade = cv2.CascadeClassifier(base + 'haarcascade_frontalface_default.xml')
    _body_cascade = cv2.CascadeClassifier(base + 'haarcascade_upperbody.xml')

    if _face_cascade.empty():
        print("❌ [Vision] Face cascade load failed!")
        return False
    print("✅ [Vision] Haar Cascade (Face + Upper Body) loaded — no model files needed.")


# ======================================================
# OPEN CAMERA (RPi OPTIMIZED)
# ======================================================
def _open_camera():
    global _cap
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  RESOLUTION[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, RESOLUTION[1])
    cap.set(cv2.CAP_PROP_FPS,          20 if is_rpi else 30)

    if cap.isOpened():
        _cap = cap
        actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        print(f"✅ [Vision] USB webcam opened: {int(actual_w)}x{int(actual_h)} @ {actual_fps}fps")
        return True

    cap.release()
    print("❌ [Vision] Camera open failed.")
    return False


# ======================================================
# MAIN THREAD LOOP
# ======================================================
def vision_loop():
    global latest_vision, _frame_jpg

    _init_cascades()
    camera_ok = _open_camera()

    if not camera_ok:
        _frame_jpg = _make_placeholder("CAMERA NOT FOUND")
        while True:
            time.sleep(5)

    print("✅ [Vision] Loop starting — Haar Cascade detection active.")

    last_rects     = []
    last_type      = "unknown"
    last_conf      = 0
    frame_count    = 0
    skip_count     = 0

    while True:
        try:
            ret, frame = _cap.read()
            if not ret or frame is None:
                time.sleep(0.05)
                continue

            # RPi OPTIMIZATION: Skip frames
            skip_count += 1
            if skip_count < FRAME_SKIP:
                time.sleep(0.01)
                continue
            skip_count = 0

            (fh, fw) = frame.shape[:2]
            draw = frame.copy()

            # -------- DETECTION every Nth frame --------
            frame_count += 1
            if frame_count % DETECTION_FREQ == 0:
                gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray  = cv2.equalizeHist(gray)  # improve contrast

                # ----- Face Detection -----
                faces = _face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.15 if is_rpi else 1.1,  # Faster on RPi
                    minNeighbors=5 if is_rpi else 4,      # Stricter on RPi
                    minSize=(50, 50) if is_rpi else (40, 40)
                )

                # ----- Upper Body Detection -----
                bodies = _body_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.15 if is_rpi else 1.1,
                    minNeighbors=4 if is_rpi else 3,
                    minSize=(70, 70) if is_rpi else (60, 60)
                ) if not _body_cascade.empty() else []

                rects_out = []
                detected  = False

                # Faces → HUMAN (high confidence)
                for (x, y, w, h) in faces:
                    rects_out.append((x, y, w, h, 0.90, "FACE"))
                    detected = True

                # Upper bodies (only if no face already covering same area)
                for (x, y, w, h) in bodies:
                    rects_out.append((x, y, w, h, 0.75, "BODY"))
                    detected = True

                if detected:
                    last_type  = "human"
                    last_conf  = 90 if len(faces) > 0 else 75
                else:
                    last_type  = "unknown"
                    last_conf  = 0

                last_rects = rects_out

                # Update shared state
                latest_vision["type"]       = last_type
                latest_vision["confidence"] = last_conf
            
            # -------- DRAW DETECTIONS --------
            for (x, y, w, h, conf, tag) in last_rects:
                color = (0, 255, 0) if tag == "FACE" else (0, 200, 255)
                cv2.rectangle(draw, (x, y), (x+w, y+h), color, 2)
                cv2.putText(draw, f"({tag}) {int(conf*100)}%",
                            (x, max(y - 8, 16)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            # HUD overlay
            st  = latest_vision["type"]
            clr = (0, 255, 0) if st == "human" else (80, 80, 80)
            cv2.putText(draw, "AEGIS-X  AI VISION", (10, 26),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 215, 0), 2)
            cv2.putText(draw, st.upper(), (fw - 120, 26),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, clr, 2)
            cv2.rectangle(draw, (0, 0), (fw-1, fh-1), (255, 51, 51), 2)

            # RPi OPTIMIZED: Lower JPEG quality
            _, buf     = cv2.imencode('.jpg', draw, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
            _frame_jpg = buf.tobytes()

        except Exception as e:
            print(f"[Vision] Error: {e}")
            time.sleep(0.1)

        # RPi OPTIMIZED: Faster loop
        time.sleep(0.040 if is_rpi else 0.033)


# ======================================================
# MJPEG STREAM GENERATOR
# ======================================================
def generate_vision():
    global _frame_jpg
    placeholder = _make_placeholder("STARTING UP...")

    while True:
        frame = _frame_jpg if _frame_jpg is not None else placeholder
        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' +
            frame +
            b'\r\n'
        )
        time.sleep(0.033)


