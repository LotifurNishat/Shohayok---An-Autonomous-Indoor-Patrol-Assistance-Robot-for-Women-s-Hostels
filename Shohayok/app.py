import signal
import sys
import threading
import time
import datetime
import os
import cv2
import numpy as np
from collections import deque
from flask import Flask, jsonify, redirect, render_template, request, session, url_for, Response
from picamera2 import Picamera2
from gpiozero import LineSensor, DistanceSensor, Buzzer
from mfrc522 import SimpleMFRC522
import motors

app = Flask(__name__)
app.secret_key = "nirapod_super_secret_key_2026"
os.makedirs("static/captures", exist_ok=True)

# --- GLOBAL CAMERA & AI CONFIGURATION ---
PROTOTXT_PATH = "MobileNetSSD_deploy.prototxt"
MODEL_PATH = "MobileNetSSD_deploy.caffemodel"
PERSON_CLASS_ID = 15
CONFIDENCE_THRESHOLD = 0.55

print("[INFO] Loading MobileNet-SSD Deep Learning Network...")
net = cv2.dnn.readNetFromCaffe(PROTOTXT_PATH, MODEL_PATH)

print("[INFO] Initializing Pi 5 Camera Stack (Picamera2)...")
try:
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(main={"size": (640, 480)})
    picam2.configure(config)
except Exception as e:
    print(f"[WARNING] Camera initialization failed: {e}. Running in headless mode.")
    picam2 = None

# ==========================================
# 1. HARDWARE CONFIGURATION
# ==========================================
ir1 = LineSensor(5, pull_up=False)
ir2 = LineSensor(6, pull_up=False)
ir3 = LineSensor(23, pull_up=False)
ir4 = LineSensor(24, pull_up=False)
ir5 = LineSensor(4, pull_up=False)

sonar = DistanceSensor(echo=22, trigger=27, max_distance=2.0)
rfid_reader = SimpleMFRC522()
security_buzzer = Buzzer(17)

# ==========================================
# RFID BACKGROUND READER
# ==========================================
rfid_lock = threading.Lock()
latest_rfid_tag = None

def rfid_worker():
    global latest_rfid_tag
    print("[INFO] RFID background reader started.")
    last_printed_tag = None

    while True:
        try:
            raw_tag_id, _ = rfid_reader.read_no_block()
            if raw_tag_id is not None:
                tag_id = int(raw_tag_id)
                with rfid_lock:
                    latest_rfid_tag = tag_id
                # Don't spam the terminal with the same UID
                if tag_id != last_printed_tag:
                    print(f"[RFID] Detected UID: {tag_id}")
                    last_printed_tag = tag_id
        except Exception as e:
            print(f"[RFID ERROR] {e}")
        # Poll approximately 100 times/sec
        time.sleep(0.01)

def get_latest_rfid():
    global latest_rfid_tag
    with rfid_lock:
        tag_id = latest_rfid_tag
        latest_rfid_tag = None
    return tag_id

# Ensure these match your physical tag UIDs perfectly
ZONES = {
    282334791308: "Zone A (Rooms 101-105)",
    51337757957:  "Zone B (Common Room)",
}

RUN_SPEED = 0.40
TURN_SPEED = 0.45
SPIN_SPEED = 0.50
KICK_POWER = 0.65
KICK_DURATION = 0.01
CORNER_SWEEP_TIMEOUT = 0.15
OBSTACLE_THRESHOLD_CM = 15.0

# ==========================================
# 2. UNIFIED STATE & CONFIGURATION
# ==========================================
USERS = {
    "resident1": {"password": "123", "role": "resident", "name": "Sadia (Room 102)"},
    "resident2": {"password": "123", "role": "resident", "name": "Tasnim (Room 105)"},
    "security1": {"password": "123", "role": "security", "name": "Guard Rafiq"},
    "admin1":    {"password": "123", "role": "admin",    "name": "Hostel Super Admin"},
}

system_config = {
    "monitoring_start": "01:00",
    "monitoring_end": "05:00",
    "inventory": ["Sanitary Pad", "Sterile Bandage", "Antiseptic Wipes", "Paracetamol"],
}

system_state = {
    "current_zone": "Zone A (Rooms 101-105)",
    "target_zone": None,
    "robot_status": "PATROLLING",
    "active_request": None,
    "timer_remaining": 0,
    "security_alert": False,
    "alert_timestamp": None,
    "alert_image_url": None,
    "alert_zone": None, # Added to track location during alert
    "alarm_active": False,
    "camera_active": True,
    "privacy_mode": False,
    "audit_logs": []
}

state_lock = threading.RLock()

# Thread-safe global frame buffer
global_frame_jpeg = None
camera_lock = threading.Lock()

def log_event(message):
    with state_lock:
        timestamp = datetime.datetime.now().strftime("%I:%M:%S %p")
        log_entry = f"[{timestamp}] {message}"
        system_state["audit_logs"].insert(0, log_entry)
        if len(system_state["audit_logs"]) > 40:
            system_state["audit_logs"].pop()
        print(log_entry)

# --- BACKGROUND TIMERS ---
def countdown_timer():
    while True:
        time.sleep(1)
        with state_lock:
            if "WAITING" in system_state["robot_status"]:
                if system_state["timer_remaining"] > 0:
                    system_state["timer_remaining"] -= 1
                else:
                    log_event(f"Timeout expired at {system_state['current_zone']}. Resuming patrol.")
                    system_state["robot_status"] = "PATROLLING"
                    system_state["active_request"] = None
                    system_state["target_zone"] = None

threading.Thread(target=countdown_timer, daemon=True).start()

def is_within_monitoring_hours():
    now = datetime.datetime.now().time()
    fmt = "%H:%M"
    start_t = datetime.datetime.strptime(system_config["monitoring_start"], fmt).time()
    end_t = datetime.datetime.strptime(system_config["monitoring_end"], fmt).time()
    if start_t <= end_t:
        return start_t <= now <= end_t
    return now >= start_t or now <= end_t

# ==========================================
# 3. DEDICATED BACKGROUND AI CAMERA THREAD
# ==========================================
def camera_worker():
    global global_frame_jpeg
    print("[INFO] Dedicated Camera AI Thread Started.")

    if picam2 is None:
        return

    try:
        picam2.start()
        time.sleep(1.5)  # Warm up sensor exposure
    except Exception as e:
        print(f"[ERROR] Camera failed to start in worker thread: {e}")
        return

    frame_count = 0
    detection_history = deque(maxlen=5)
    last_alert_time = 0

    while True:
        try:
            frame = picam2.capture_array()
            if frame is None:
                time.sleep(0.05)
                continue

            if frame.ndim == 3 and frame.shape[2] == 4:
                frame = frame[:, :, :3]
            frame = np.ascontiguousarray(frame)
            (h, w) = frame.shape[:2]

            # Run Deep Learning AI every 5 frames (~6 FPS) to save CPU load
            if frame_count % 5 == 0:
                blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5)
                net.setInput(blob)
                detections = net.forward()

                person_found = False
                active_box = None

                for i in range(detections.shape[2]):
                    confidence = detections[0, 0, i, 2]
                    class_id = int(detections[0, 0, i, 1])

                    if class_id == PERSON_CLASS_ID and confidence > CONFIDENCE_THRESHOLD:
                        person_found = True
                        box = detections[0, 0, i, 3:7] * [w, h, w, h]
                        active_box = box.astype("int")
                        break

                # Maintain sliding window to prevent 1-frame glitches
                detection_history.append(person_found)

                # Save Intruder Snapshot Logic (If human confirmed in 3 of the last 5 frames)
                if sum(detection_history) >= 3 and is_within_monitoring_hours() and not system_state["security_alert"]:
                    # Cooldown of 15 seconds to prevent spamming
                    if time.time() - last_alert_time > 15:
                        with state_lock:
                            filename = f"capture_{int(time.time())}.jpg"
                            annotated = frame.copy()
                            (startX, startY, endX, endY) = active_box
                            cv2.rectangle(annotated, (startX, startY), (endX, endY), (0, 0, 255), 2)
                            cv2.putText(annotated, f"PERSON CONFIRMED", (startX, max(20, startY - 10)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                            cv2.imwrite(f"static/captures/{filename}", annotated)

                            system_state["security_alert"] = True
                            system_state["alert_timestamp"] = datetime.datetime.now().strftime("%I:%M:%S %p")
                            system_state["alert_image_url"] = f"/static/captures/{filename}"
                            system_state["alert_zone"] = system_state["current_zone"] # Tag the zone

                        log_event(f"AI Security Event: Human presence snapshot saved at {system_state['current_zone']}.")
                        last_alert_time = time.time()
                        detection_history.clear()

            frame_count += 1

            # Draw tracked boxes onto the background buffer for the live stream
            if active_box is not None:
                (startX, startY, endX, endY) = active_box
                cv2.rectangle(frame, (startX, startY), (endX, endY), (0, 255, 0), 2)

            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                with camera_lock:
                    global_frame_jpeg = buffer.tobytes()

        except Exception as e:
            time.sleep(0.1)

# ==========================================
# 4. CHASSIS HARDWARE CONTROL THREAD
# ==========================================
def read_sensors():
    return [int(ir1.value == 0), int(ir2.value == 0), int(ir3.value == 0), int(ir4.value == 0), int(ir5.value == 0)]

def execute_90_degree_turn(direction):
    motors.stop()
    time.sleep(0.05)
    if direction == "RIGHT":
        motors.spin_right(SPIN_SPEED)
        time.sleep(0.25)
        timeout = time.time() + 0.8
        while True:
            s = read_sensors()
            if s[1] == 1 or s[2] == 1 or s[3] == 1 or time.time() > timeout: break
            time.sleep(0.01)
    elif direction == "LEFT":
        motors.spin_left(SPIN_SPEED)
        time.sleep(0.25)
        timeout = time.time() + 0.8
        while True:
            s = read_sensors()
            if s[1] == 1 or s[2] == 1 or s[3] == 1 or time.time() > timeout: break
            time.sleep(0.01)
    motors.stop()
    time.sleep(0.05)

def set_motion_state(new_state, current_state):
    if new_state == current_state: return current_state
    if new_state == "FORWARD":
        motors.forward(KICK_POWER); time.sleep(KICK_DURATION); motors.forward(RUN_SPEED)
    elif new_state == "TURN_LEFT":
        motors.turn_left(KICK_POWER); time.sleep(KICK_DURATION); motors.turn_left(TURN_SPEED)
    elif new_state == "TURN_RIGHT":
        motors.turn_right(KICK_POWER); time.sleep(KICK_DURATION); motors.turn_right(TURN_SPEED)
    elif new_state == "STOP":
        motors.stop()
    return new_state

def robot_loop():
    log_event("NIRAPOD Navigation Subsystem initialized.")
    time.sleep(3)

    last_state = "STOP"
    target_state = "STOP"
    last_turn_dir = None
    lost_line_time = 0

    # RFID debounce
    last_rfid_tag = None
    last_rfid_process_time = 0
    RFID_DEBOUNCE = 0.5

    while True:
        now = time.time()

        with state_lock:
            status = system_state["robot_status"]
            alarm = system_state["alarm_active"]
            alert = system_state["security_alert"]
            target = system_state["target_zone"]

        if "WAITING" in status or alarm or alert:
            if last_state != "STOP":
                last_state = set_motion_state("STOP", last_state)
            if alarm:
                security_buzzer.on()
            else:
                security_buzzer.off()
            time.sleep(0.1)
            continue

        security_buzzer.off()
        tag_id = get_latest_rfid()

        if tag_id:
            if tag_id != last_rfid_tag or (now - last_rfid_process_time) > RFID_DEBOUNCE:
                zone_name = ZONES.get(tag_id, f"Checkpoint ({tag_id})")
                print(f"[RFID] UID={tag_id} | Zone={zone_name} | Target={target} | Status={status}")

                checkpoint_pause = False
                arrived_at_target = False

                with state_lock:
                    previous_zone = system_state["current_zone"]
                    system_state["current_zone"] = zone_name

                    if target == zone_name:
                        print(f"[RFID] TARGET REACHED: {zone_name}")
                        if status == "EN_ROUTE_EMERGENCY":
                            system_state["robot_status"] = "WAITING_PICKUP"
                        elif status == "EN_ROUTE_SENDER":
                            system_state["robot_status"] = "WAITING_SENDER"
                        elif status == "EN_ROUTE_RECEIVER":
                            system_state["robot_status"] = "WAITING_RECEIVER"
                        system_state["timer_remaining"] = 300
                        arrived_at_target = True

                    elif zone_name != previous_zone:
                        checkpoint_pause = True

                last_rfid_tag = tag_id
                last_rfid_process_time = time.time()

                if arrived_at_target:
                    log_event(f"Arrived at designated target: {zone_name}")
                    last_state = set_motion_state("STOP", last_state)
                    continue

                if checkpoint_pause:
                    print(f"[RFID] New checkpoint detected: {zone_name}")
                    motors.stop()
                    time.sleep(0.20)
                    lost_line_time = 0
                    last_turn_dir = None
                    last_state = "STOP"

        s = read_sensors()
        distance_cm = sonar.distance * 100

        if distance_cm < OBSTACLE_THRESHOLD_CM:
            target_state = "STOP"
            last_turn_dir = None
            lost_line_time = 0
            last_state = set_motion_state(target_state, last_state)
        else:
            if sum(s) >= 4:
                target_state = "STOP"
            elif s[0] == 1:
                execute_90_degree_turn("LEFT")
                target_state = "FORWARD"
                last_state = "STOP"
            elif s[4] == 1:
                execute_90_degree_turn("RIGHT")
                target_state = "FORWARD"
                last_state = "STOP"
            elif s[2] == 1:
                target_state = "FORWARD"
                last_turn_dir = None
                lost_line_time = 0
            elif s[1] == 1:
                target_state = "TURN_LEFT"
                last_turn_dir = "LEFT"
                lost_line_time = 0
            elif s[3] == 1:
                target_state = "TURN_RIGHT"
                last_turn_dir = "RIGHT"
                lost_line_time = 0
            elif sum(s) == 0:
                if lost_line_time == 0:
                    lost_line_time = now

                if last_turn_dir is not None and (now - lost_line_time) < CORNER_SWEEP_TIMEOUT:
                    if last_turn_dir == "LEFT":
                        motors.spin_left(SPIN_SPEED)
                    else:
                        motors.spin_right(SPIN_SPEED)
                else:
                    target_state = "FORWARD"

            if s[0] == 0 and s[4] == 0:
                last_state = set_motion_state(target_state, last_state)

        time.sleep(0.005)


# ==========================================
# 5. WEB ROUTES & USER APIS
# ==========================================
def generate_video_stream(user_role):
    offline_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(offline_frame, "PRIVACY LOCK / OFFLINE", (110, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
    _, offline_bytes_buffer = cv2.imencode('.jpg', offline_frame)
    offline_bytes = offline_bytes_buffer.tobytes()

    while True:
        with state_lock:
            is_active = system_state["camera_active"]
            privacy = system_state["privacy_mode"]

        block_stream = (not is_active) or (user_role == "security" and privacy)

        if block_stream or picam2 is None:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + offline_bytes + b'\r\n')
            time.sleep(1.0)
        else:
            with camera_lock:
                current_jpeg = global_frame_jpeg
            if current_jpeg is not None:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + current_jpeg + b'\r\n')
            else:
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + offline_bytes + b'\r\n')
            time.sleep(0.05)

@app.route('/video_feed')
def video_feed():
    role = session.get("role")
    if role not in ["admin", "security"]:
        return redirect(url_for("login"))
    return Response(generate_video_stream(role), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))
    role = session.get("role")
    if role == "resident": return redirect(url_for("resident_dashboard"))
    elif role == "security": return redirect(url_for("security_dashboard"))
    elif role == "admin": return redirect(url_for("admin_dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username, password = request.form.get("username"), request.form.get("password")
        if username in USERS and USERS[username]["password"] == password:
            session.update({"user": username, "role": USERS[username]["role"], "name": USERS[username]["name"]})
            log_event(f"User login: {session['name']} ({session['role']})")
            return redirect(url_for("index"))
        return render_template("login.html", error="Invalid Credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    name = session.get("name", "User")
    session.clear()
    log_event(f"User logout: {name}")
    return redirect(url_for("login"))

@app.route("/resident")
def resident_dashboard():
    if session.get("role") != "resident": return redirect(url_for("login"))
    return render_template("resident.html", user=session, zones=list(ZONES.values()), inventory=system_config["inventory"])

@app.route("/security")
def security_dashboard():
    if session.get("role") != "security": return redirect(url_for("login"))
    return render_template("security.html", user=session)

@app.route("/admin")
def admin_dashboard():
    if session.get("role") != "admin": return redirect(url_for("login"))
    return render_template("admin.html", user=session, config=system_config, monitoring_active=is_within_monitoring_hours())

@app.route("/api/status", methods=["GET"])
def get_status():
    with state_lock:
        return jsonify({
            **system_state,
            "monitoring_active": is_within_monitoring_hours(),
            "inventory": system_config["inventory"]
        })

@app.route("/api/resident/call-emergency", methods=["POST"])
def call_emergency():
    target = request.json.get("target_zone")
    item = request.json.get("item")
    with state_lock:
        if system_state["active_request"]: return jsonify({"success": False, "message": "Robot occupied."}), 400
        if system_state["current_zone"] == target and system_state["robot_status"] == "PATROLLING":
            system_state["robot_status"] = "WAITING_PICKUP"
            system_state["timer_remaining"] = 300
        else:
            system_state["robot_status"] = "EN_ROUTE_EMERGENCY"
        system_state["target_zone"] = target
        system_state["active_request"] = {"type": "EMERGENCY", "requester": session.get("name"), "target_zone": target}
    log_event(f"Emergency order: {item} dispatched to {target} for {session.get('name')}.")
    return jsonify({"success": True, "message": f"NIRAPOD en route to {target} with {item}."})

@app.route("/api/resident/call-r2r", methods=["POST"])
def call_r2r():
    sender_zone = request.json.get("sender_zone")
    with state_lock:
        if system_state["active_request"]: return jsonify({"success": False, "message": "Robot occupied."}), 400
        if system_state["current_zone"] == sender_zone and system_state["robot_status"] == "PATROLLING":
            system_state["robot_status"] = "WAITING_SENDER"
            system_state["timer_remaining"] = 300
        else:
            system_state["robot_status"] = "EN_ROUTE_SENDER"
        system_state["target_zone"] = sender_zone
        system_state["active_request"] = {"type": "R2R", "sender": session.get("name")}
    log_event(f"Peer Courier Call: {session.get('name')} requested bot to {sender_zone}.")
    return jsonify({"success": True, "message": f"NIRAPOD en route to your zone ({sender_zone})."})

@app.route("/api/resident/dispatch-r2r", methods=["POST"])
def dispatch_r2r():
    destination_zone = request.json.get("destination_zone")
    with state_lock:
        if system_state["robot_status"] != "WAITING_SENDER": return jsonify({"success": False, "message": "Robot not ready."}), 400
        system_state["target_zone"] = destination_zone
        system_state["robot_status"] = "EN_ROUTE_RECEIVER"
    log_event(f"Peer Courier Dispatched: Heading to {destination_zone}.")
    return jsonify({"success": True, "message": f"Parcel secured. Heading to {destination_zone}."})

@app.route("/api/resident/confirm-arrival", methods=["POST"])
def confirm_arrival():
    with state_lock:
        if "WAITING" in system_state["robot_status"]:
            zone = system_state["current_zone"]
            system_state["robot_status"] = "PATROLLING"
            system_state["active_request"] = None
            system_state["target_zone"] = None
            system_state["timer_remaining"] = 0
            log_event(f"Pickup confirmed at {zone}. Patrol resumed.")
            return jsonify({"success": True, "message": "Collection confirmed. Resuming patrol."})
        return jsonify({"success": False, "message": "Robot is not waiting at your zone."}), 400

@app.route("/api/admin/update-config", methods=["POST"])
def update_config():
    data = request.json
    with state_lock:
        if data.get("start_time"): system_config["monitoring_start"] = data.get("start_time")
        if data.get("end_time"): system_config["monitoring_end"] = data.get("end_time")
        if data.get("items") is not None: system_config["inventory"] = [i.strip() for i in data.get("items") if i.strip()]
        if data.get("privacy_mode") is not None: system_state["privacy_mode"] = data.get("privacy_mode")
    log_event(f"Admin updated system settings. Privacy Mode: {system_state['privacy_mode']}.")
    return jsonify({"success": True, "message": "Parameters updated."})

@app.route("/api/admin/toggle-camera", methods=["POST"])
def toggle_camera():
    activate = request.json.get("camera_active", False)
    with state_lock:
        system_state["camera_active"] = activate
    log_event(f"Admin toggled Camera Live Stream: {'ENABLED' if activate else 'DISABLED'}")
    return jsonify({"success": True, "camera_active": activate})

@app.route("/api/security/decision", methods=["POST"])
def security_decision():
    action = request.json.get("action")
    with state_lock:
        if action == "THREAT":
            system_state["alarm_active"] = True
            system_state["security_alert"] = False
            log_event(f"SECURITY ALERT: {session.get('name')} CONFIRMED THREAT! 10s Alarm fired.")
            def reset_alarm():
                time.sleep(10)
                with state_lock: system_state["alarm_active"] = False
                log_event("10s Warning buzzer finished.")
            threading.Thread(target=reset_alarm, daemon=True).start()
            return jsonify({"success": True, "message": "Hostel buzzer triggered for 10 seconds."})
        else:
            system_state["security_alert"] = False
            log_event(f"Alert dismissed by {session.get('name')}.")
            return jsonify({"success": True, "message": "Alert dismissed as non-threat."})

@app.route("/api/simulate/detect-human", methods=["POST"])
def simulate_human_detection():
    with state_lock:
        system_state["security_alert"] = True
        system_state["alert_timestamp"] = datetime.datetime.now().strftime("%I:%M:%S %p")
        system_state["alert_zone"] = system_state["current_zone"] # Tag the zone
        captures = sorted([f for f in os.listdir("static/captures") if f.endswith(".jpg")])
        if captures: system_state["alert_image_url"] = f"/static/captures/{captures[-1]}"
    log_event("Simulated human presence detected.")
    return jsonify({"success": True})

@app.route("/api/simulate/rfid", methods=["POST"])
def simulate_rfid():
    zone = request.json.get("zone")
    with state_lock:
        system_state["current_zone"] = zone
        if system_state["target_zone"] == zone:
            if system_state["robot_status"] == "EN_ROUTE_EMERGENCY": system_state["robot_status"] = "WAITING_PICKUP"
            elif system_state["robot_status"] == "EN_ROUTE_SENDER": system_state["robot_status"] = "WAITING_SENDER"
            elif system_state["robot_status"] == "EN_ROUTE_RECEIVER": system_state["robot_status"] = "WAITING_RECEIVER"
            system_state["timer_remaining"] = 300
    log_event(f"Simulated RFID arrival at: {zone}")
    return jsonify({"success": True, "current_zone": zone})

def emergency_stop(sig=None, frame=None):
    motors.stop()
    security_buzzer.off()
    if picam2 is not None:
        try:
            picam2.stop()
        except:
            pass
    sys.exit(0)

signal.signal(signal.SIGINT, emergency_stop)

if __name__ == "__main__":
    threading.Thread(target=camera_worker, daemon=True).start()
    threading.Thread(target=rfid_worker, daemon=True).start()
    threading.Thread(target=robot_loop, daemon=True).start()
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
