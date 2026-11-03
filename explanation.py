from datetime import datetime

def generate_explanation(score, threat, reasons, confidence, thermal=None, radar=None, vision=None):
    """Generate detailed threat explanation with sensor-specific information."""
    
    # Get current timestamp
    current_time = datetime.now()
    time_str = current_time.strftime('%H:%M:%S')
    
    # ---------- SUMMARY ----------
    if threat == "CRITICAL":
        summary = "⚠️ CRITICAL THREAT — Multiple sensors active confirmation"
    elif threat == "HIGH":
        summary = "🔴 HIGH THREAT — Strong sensor agreement detected"
    elif threat == "MEDIUM":
        summary = "🟠 MEDIUM THREAT — Partial sensor confirmation"
    elif threat == "LOW":
        summary = "🟡 LOW THREAT — Minor activity detected"
    else:
        summary = "🟢 NO THREAT — Baseline activity"

    # ---------- SENSOR-SPECIFIC DETAILS ----------
    thermal_report = ""
    radar_report = ""
    vision_report = ""
    
    if thermal:
        temp_diff = thermal.get("temp", 0) - thermal.get("ambient", 0)
        if thermal.get("area", 0) > 0:
            if thermal.get("ratio", 1) < 0.75:
                posture = "CRAWLING (Suspicious)"
            else:
                posture = "STANDING"
            
            thermal_report = (
                f"🔥 THERMAL: Detected body at {thermal.get('temp', 0):.1f}°C "
                f"({temp_diff:+.1f}°C vs ambient) | "
                f"Size: {thermal.get('area', 0)}px² | "
                f"Posture: {posture} | "
                f"{'Movement observed' if thermal.get('movement') else 'Static'}"
            )
        else:
            thermal_report = "🔥 THERMAL: No detection"
    
    if radar:
        if radar.get("presence"):
            motion_str = "Motion" if radar.get("motion") else "No motion"
            micro_str = " + Micro motion" if radar.get("micro_motion") else ""
            radar_report = (
                f"📡 RADAR: Target present at {radar.get('distance', 0):.1f}m | "
                f"{motion_str}{micro_str} | Zone: {radar.get('zone', 'UNKNOWN')}"
            )
        else:
            radar_report = "📡 RADAR: No target detected"
    
    if vision:
        if vision.get("type") != "unknown":
            vision_report = (
                f"👁️ VISION: {vision.get('type', 'unknown').upper()} detected "
                f"({vision.get('confidence', 0)}% confidence)"
            )
        else:
            vision_report = "👁️ VISION: No detection"

    # ---------- CONFIDENCE BARS ----------
    def bar(val):
        val = int(val) if val else 0
        filled = int(val/10)
        return "█"*filled + "░"*(10-filled) + f" {val}%"

    conf_visual = {
        "thermal": bar(confidence.get("thermal", 0)),
        "radar": bar(confidence.get("radar", 0)),
        "vision": bar(confidence.get("vision", 0))
    }

    # ---------- LOG ----------
    log = []
    for r in reasons:
        log.append("• " + r)

    # ---------- DETECTION CHAIN ----------
    detection_chain = []
    if thermal_report and thermal and thermal.get("area", 0) > 0:
        detection_chain.append(thermal_report)
    if radar_report and radar and radar.get("presence"):
        detection_chain.append(radar_report)
    if vision_report and vision and vision.get("type") != "unknown":
        detection_chain.append(vision_report)

    # ---------- ANALYSIS ----------
    analysis = []

    if any("human" in r.lower() for r in reasons):
        analysis.append("✓ Subject confirmed HUMAN")

    if any("animal" in r.lower() for r in reasons):
        analysis.append("⚠ Possible ANIMAL activity")

    if any("unknown" in r.lower() for r in reasons):
        analysis.append("? Unknown object detected")

    if any("crawling" in r.lower() for r in reasons):
        analysis.append("🚨 Suspicious CRAWLING pattern")

    if any("movement" in r.lower() for r in reasons):
        analysis.append("⚡ Active MOTION detected")
    
    if any("triple" in r.lower() for r in reasons):
        analysis.append("🎯 TRIPLE SENSOR CONFIRMATION")

    # ---------- FINAL VERDICT ----------
    if threat in ["HIGH", "CRITICAL"]:
        verdict = "🔴 HIGH PROBABILITY THREAT — Immediate investigation required"
    elif threat == "MEDIUM":
        verdict = "🟠 POTENTIAL THREAT — Continue monitoring closely"
    elif threat == "LOW":
        verdict = "🟡 LOW THREAT — Routine monitoring sufficient"
    else:
        verdict = "🟢 NO THREAT — System operating normally"

    return {
        "timestamp": current_time.isoformat(),
        "time_str": time_str,
        "summary": summary,
        "confidence_visual": conf_visual,
        "log": log,
        "analysis": analysis,
        "verdict": verdict,
        "sensor_reports": {
            "thermal": thermal_report,
            "radar": radar_report,
            "vision": vision_report
        },
        "detection_chain": detection_chain,
        "threat_level": threat,
        "threat_score": score
    }