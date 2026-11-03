history = []
memory_log = []

# -------- MEMORY --------
def update_memory(score):
    history.append(score)
    if len(history) > 30:
        history.pop(0)

def get_trend():
    if len(history) < 5:
        return 0
    return sum(history[-5:]) / 5


def update_memory_advanced(entry):
    memory_log.append(entry)
    if len(memory_log) > 50:
        memory_log.pop(0)

def get_behavior_pattern():
    if len(memory_log) < 10:
        return 0
    movement_count = sum(1 for e in memory_log if e["movement"])
    return movement_count / len(memory_log)


# -------- MAIN ENGINE --------
def fusion_engine(thermal, radar, vision):

    score = 0
    reasons = []
    tags = []

    t_conf = 0
    r_conf = 0
    v_conf = 0

    # ================= THERMAL =================
    if thermal["temp"] > thermal["ambient"] + 2:
        t_conf += 30
        reasons.append("Heat above ambient")
        tags.append("HEAT")

    if thermal["area"] > 25000:
        t_conf += 40
        reasons.append("Large body detected")

    elif thermal["area"] > 12000:
        t_conf += 20
        reasons.append("Medium body detected")

    if thermal["ratio"] < 0.75:
        t_conf += 25
        reasons.append("Crawling posture")
        tags.append("CRAWLING")

    if thermal["movement"]:
        t_conf += 15
        reasons.append("Thermal movement")
        tags.append("MOVEMENT")

    # ================= RADAR =================
    if radar["motion"]:
        r_conf += 40
        reasons.append("Radar motion")

    if radar["presence"]:
        r_conf += 20
        reasons.append("Presence detected")

    if radar["distance"] < 1.5:
        r_conf += 30
        reasons.append("Very close object")

    if radar["micro_motion"]:
        r_conf += 20
        reasons.append("Micro motion detected")

    # ================= VISION =================
    if vision["type"] == "human":
        v_conf += vision["confidence"]
        reasons.append("Human detected")
        tags.append("HUMAN")

    elif vision["type"] == "animal":
        v_conf += vision["confidence"] * 0.6
        reasons.append("Animal detected")
        tags.append("ANIMAL")

    else:
        v_conf += vision["confidence"] * 0.3
        reasons.append("Unknown object")
        tags.append("UNKNOWN")

    # ================= BASE FUSION =================
    score += (t_conf*0.4 + r_conf*0.3 + v_conf*0.3)

    # ================= DUO RULES =================
    if thermal["movement"] and radar["motion"]:
        score += 20
        reasons.append("Thermal + Radar correlation")

    if "HUMAN" in tags and thermal["temp"] > thermal["ambient"] + 2:
        score += 20
        reasons.append("Human heat confirmed")

    if radar["motion"] and vision["type"] == "human":
        score += 20
        reasons.append("Moving human")

    # ================= TRIPLE =================
    triple = False
    if thermal["movement"] and radar["motion"] and vision["type"] == "human":
        score += 35
        triple = True
        reasons.append("Triple confirmation")

    # ================= BEHAVIOR =================
    if "HUMAN" in tags and "CRAWLING" in tags:
        score += 30
        reasons.append("Suspicious crawling")

    if radar["distance"] < 2 and thermal["area"] > 20000:
        score += 20
        reasons.append("Large close object")

    if "UNKNOWN" in tags and radar["motion"]:
        score += 15
        reasons.append("Unknown moving object")

    # ================= ANIMAL FILTER =================
    if "ANIMAL" in tags and thermal["area"] < 15000:
        score -= 20
        reasons.append("Likely small animal")

    # ================= ENVIRONMENT =================
    if thermal["ambient"] > 32:
        score -= 10
        reasons.append("Hot environment adjustment")

    # ================= SENSOR FAILURE =================
    if thermal["area"] == 0:
        score -= 25
        reasons.append("Weak thermal")

    if not radar["presence"]:
        score -= 10

    # ================= MEMORY =================
    update_memory(score)
    update_memory_advanced(thermal)

    trend = get_trend()
    pattern = get_behavior_pattern()

    if trend > 70:
        score += 15
        reasons.append("Persistent activity")

    if pattern > 0.6:
        score += 10
        reasons.append("Repeated movement pattern")

    # ================= FINAL =================
    score = int(max(0, min(score, 100)))

    if score > 85:
        threat = "CRITICAL"
    elif score > 70:
        threat = "HIGH"
    elif score > 50:
        threat = "MEDIUM"
    elif score > 25:
        threat = "LOW"
    else:
        threat = "NONE"

    if triple:
        threat = "HIGH"

    return score, threat, list(set(reasons)), {
        "thermal": min(t_conf,100),
        "radar": min(r_conf,100),
        "vision": min(v_conf,100)
    }