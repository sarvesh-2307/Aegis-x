import serial
import time

latest_radar = {
    "presence": False,
    "motion": False,
    "micro_motion": False,
    "distance": 0
}

ser = None

# ===== AUTO CONNECT =====
def connect_radar():
    global ser

    ports = ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyAMA0"]

    for p in ports:
        try:
            ser = serial.Serial(p, 256000, timeout=1)
            print(f"✅ Radar connected on {p}")
            return
        except:
            continue

    print("❌ Radar NOT connected")


# ===== LOOP =====
def radar_loop():
    global latest_radar, ser

    connect_radar()

    while True:
        try:
            if ser is None:
                time.sleep(1)
                connect_radar()
                continue

            data = ser.read(23)

            if len(data) < 23:
                continue

            presence = data[8]
            motion = data[9]
            micro = data[10]
            dist = data[12]

            latest_radar["presence"] = bool(presence)
            latest_radar["motion"] = bool(motion)
            latest_radar["micro_motion"] = bool(micro)
            latest_radar["distance"] = dist / 10.0

        except Exception as e:
            print("Radar error:", e)
            ser = None
            time.sleep(1)