"""
server.py : รับรูปที่วาดจากหน้าเว็บ แล้วสั่งโดรนบินตามรูป
  หน้าเว็บ --ส่งจุดที่วาด--> server.py --MAVLink--> โดรนจำลอง
  หน้าเว็บ <--ถามสถานะทุก 0.3 วิ-- server.py <-- โดรนจำลอง
"""
import math
import os
import threading
import time

from flask import Flask, jsonify, request, send_from_directory
from pymavlink import mavutil

# ===================== ส่วนที่ 1: ค่าที่ปรับได้ =====================
CONNECTION = "tcp:127.0.0.1:5762"   # พอร์ตของโดรนจำลอง (5760 ให้ QGroundControl)
REACH = 1.5                         # ห่างจุดเป้าหมายไม่เกินกี่เมตรถึงนับว่า "ถึงแล้ว"
MAX_POINTS = 120                    # จำนวนจุดสูงสุดที่ส่งให้โดรน
PORT = 5000                         # พอร์ตของหน้าเว็บ

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

# ===================== ส่วนที่ 2: เชื่อมต่อโดรน =====================
print("กำลังเชื่อมต่อโดรนจำลอง...")
master = mavutil.mavlink_connection(CONNECTION)
if master.wait_heartbeat(timeout=15) is None:
    print("เชื่อมต่อไม่ได้ ตรวจว่า sim_vehicle.py รันอยู่ใน terminal แรกหรือไม่")
    raise SystemExit
print("เชื่อมต่อสำเร็จ!")

MODES = {v: k for k, v in master.mode_mapping().items()}  # เลขโหมด -> ชื่อโหมด

# ขอให้โดรนส่งข้อมูลมาถี่ๆ (10 ครั้ง/วินาที)
master.mav.request_data_stream_send(
    master.target_system, master.target_component,
    mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
for msg_id in (32, 33):  # 32 = LOCAL_POSITION_NED, 33 = GLOBAL_POSITION_INT
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
        0, msg_id, 100000, 0, 0, 0, 0, 0)

# ===================== ส่วนที่ 3: ข้อมูลที่ใช้ร่วมกัน =====================
lock = threading.Lock()        # กันข้อมูลชนกันระหว่าง thread
send_lock = threading.Lock()   # กันการส่งคำสั่งซ้อนกัน
stop_flag = threading.Event()  # ถูกตั้งเมื่อกดปุ่มหยุด

state = {
    "connected": True, "alt": 0.0, "n": 0.0, "e": 0.0,
    "armed": False, "mode": "?", "mode_id": None,
    "status": "พร้อม วาดรูปแล้วกดเริ่มบิน", "running": False,
}
trail = []   # เส้นทางที่โดรนบินจริง [[เหนือ, ตะวันออก], ...]
plan = []    # เส้นทางที่วางแผนไว้
log = []     # ข้อความแสดงความคืบหน้า


def say(text):
    """อัปเดตข้อความสถานะและเก็บลงบันทึก"""
    with lock:
        state["status"] = text
        log.append(f"{time.strftime('%H:%M:%S')}  {text}")
        del log[:-60]
    print(text)


# ===================== ส่วนที่ 4: thread อ่านข้อมูลจากโดรน =====================
def reader():
    """อ่านข้อความจากโดรนตลอดเวลา (มีแค่ thread นี้ที่อ่าน)"""
    last_time = time.time()
    while True:
        msg = master.recv_match(blocking=True, timeout=1)
        now = time.time()
        if msg is None:
            with lock:
                state["connected"] = now - last_time < 5
            continue
        last_time = now
        t = msg.get_type()
        with lock:
            state["connected"] = True
            if t == "GLOBAL_POSITION_INT":
                state["alt"] = msg.relative_alt / 1000            # ความสูง (เมตร)
            elif t == "LOCAL_POSITION_NED":
                state["n"], state["e"] = msg.x, msg.y             # เหนือ, ตะวันออก (เมตร)
                if state["running"]:
                    if not trail or math.hypot(msg.x - trail[-1][0], msg.y - trail[-1][1]) > 0.3:
                        trail.append([round(msg.x, 2), round(msg.y, 2)])
                        del trail[:-3000]
            elif (t == "HEARTBEAT" and msg.get_srcSystem() == master.target_system
                  and msg.type != mavutil.mavlink.MAV_TYPE_GCS):
                state["armed"] = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                state["mode_id"] = msg.custom_mode
                state["mode"] = MODES.get(msg.custom_mode, str(msg.custom_mode))
            elif t == "STATUSTEXT":
                log.append(f"{time.strftime('%H:%M:%S')}  [โดรนแจ้ง] {msg.text}")
                del log[:-60]


# ===================== ส่วนที่ 5: ฟังก์ชันสั่งโดรน =====================
def set_mode(name):
    """เปลี่ยนโหมดบิน แล้วรอจนโดรนยืนยัน"""
    mode_id = master.mode_mapping()[name]
    with send_lock:
        master.mav.set_mode_send(
            master.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, mode_id)
    for _ in range(25):
        time.sleep(0.2)
        if state["mode_id"] == mode_id:
            return True
    return False


def goto(north, east, alt):
    """สั่งบินไปจุดที่ห่างจากจุดเริ่มต้น north เมตรทางเหนือ, east เมตรทางตะวันออก"""
    with send_lock:
        master.mav.set_position_target_local_ned_send(
            0, master.target_system, master.target_component,
            mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            0b0000111111111000,        # ใช้เฉพาะตำแหน่ง x,y,z
            north, east, -alt,         # z เป็นลบ = สูงขึ้น
            0, 0, 0, 0, 0, 0, 0, 0)


def fly_to(north, east, alt, timeout=40):
    """บินไปจุดนั้นแล้วรอจนถึง (หรือหมดเวลา หรือกดหยุด)"""
    start = time.time()
    while time.time() - start < timeout and not stop_flag.is_set():
        goto(north, east, alt)
        time.sleep(0.3)
        if math.hypot(state["n"] - north, state["e"] - east) < REACH:
            return True
    return False


def land():
    say("กำลังลงจอด...")
    set_mode("LAND")
    start = time.time()
    while time.time() - start < 90:
        time.sleep(0.5)
        if state["alt"] < 0.3 and not state["armed"]:
            break
    say("ลงจอดเรียบร้อย")


def mission(path, alt):
    """GUIDED -> arm -> ขึ้นบิน -> บินตามรูป -> กลับจุดเริ่มต้น -> ลงจอด"""
    try:
        say("ตั้งโหมด GUIDED...")
        if not set_mode("GUIDED"):
            say("ตั้งโหมด GUIDED ไม่สำเร็จ")
            return

        say("กำลังติดเครื่อง (ถ้า GPS จำลองยังไม่พร้อมอาจรอ 1-3 นาที)...")
        for _ in range(60):
            if stop_flag.is_set():
                return
            with send_lock:
                master.mav.command_long_send(
                    master.target_system, master.target_component,
                    mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
                    0, 1, 0, 0, 0, 0, 0, 0)
            time.sleep(3)
            if state["armed"]:
                break
        if not state["armed"]:
            say("ติดเครื่องไม่สำเร็จ ดูข้อความ [โดรนแจ้ง] ว่า PreArm ติดเรื่องอะไร")
            return

        say(f"ขึ้นบินไปที่ความสูง {alt:.0f} เมตร...")
        with send_lock:
            master.mav.command_long_send(
                master.target_system, master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
                0, 0, 0, 0, 0, 0, 0, alt)
        start = time.time()
        while time.time() - start < 45 and not stop_flag.is_set():
            time.sleep(0.5)
            if state["alt"] >= alt - 0.7:
                break
        if stop_flag.is_set():
            return
        if state["alt"] < alt - 0.7:
            say("ขึ้นบินไม่ถึงความสูงที่ตั้งไว้ หยุดการทำงาน")
            return

        for i, (n, e) in enumerate(path, 1):
            if stop_flag.is_set():
                return
            say(f"กำลังบินตามรูป จุดที่ {i}/{len(path)}")
            fly_to(n, e, alt)

        if not stop_flag.is_set():
            say("วาดเสร็จ กำลังกลับจุดเริ่มต้น...")
            fly_to(0, 0, alt)
    finally:
        if state["armed"]:
            land()
        if stop_flag.is_set():
            say("หยุดการทำงานแล้ว")
        with lock:
            state["running"] = False


# ===================== ส่วนที่ 6: แปลงรูปที่วาดเป็นจุดบิน =====================
def seg_dist(p, a, b):
    """ระยะจากจุด p ถึงเส้นตรง a-b"""
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def simplify(points, eps):
    """ลดจำนวนจุด (Ramer-Douglas-Peucker) เก็บเฉพาะจุดที่ทำให้รูปเปลี่ยนจริง"""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        dmax, idx = 0, None
        for i in range(a + 1, b):
            d = seg_dist(points[i], points[a], points[b])
            if d > dmax:
                dmax, idx = d, i
        if idx is not None and dmax > eps:
            keep[idx] = True
            stack.append((a, idx))
            stack.append((idx, b))
    return [p for p, k in zip(points, keep) if k]


def build_path(pixels, size_m):
    """
    แปลงจุดพิกเซลบนกระดาน เป็นพิกัด (เหนือ, ตะวันออก) หน่วยเมตร
      - ด้านที่ยาวที่สุดของรูป = size_m เมตร
      - จุดกึ่งกลางของรูป = จุดเริ่มต้นของโดรน (0,0)
      - บนกระดาน ขึ้นบน = ทิศเหนือ, ขวา = ทิศตะวันออก
    """
    xs = [p[0] for p in pixels]
    ys = [p[1] for p in pixels]
    span = max(max(xs) - min(xs), max(ys) - min(ys))
    if span < 1:
        return None
    scale = size_m / span
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    pts = [((cy - y) * scale, (x - cx) * scale) for x, y in pixels]

    eps = size_m * 0.01
    out = simplify(pts, eps)
    while len(out) > MAX_POINTS:
        eps *= 1.5
        out = simplify(pts, eps)
    return [(round(n, 2), round(e, 2)) for n, e in out]


# ===================== ส่วนที่ 7: เส้นทางของหน้าเว็บ =====================
@app.route("/")
def index():
    return send_from_directory(BASE, "index.html")


@app.route("/state")
def get_state():
    with lock:
        return jsonify({**state, "trail": trail, "plan": plan, "log": log})


@app.route("/start", methods=["POST"])
def start():
    data = request.get_json(force=True)
    try:
        pixels = [[float(x), float(y)] for x, y in data["points"]]
        size = float(data.get("size", 30))
        alt = float(data.get("alt", 15))
    except (KeyError, TypeError, ValueError):
        return jsonify(ok=False, error="ข้อมูลที่ส่งมาไม่ถูกต้อง")

    if len(pixels) < 5:
        return jsonify(ok=False, error="รูปสั้นเกินไป ลองวาดใหม่")
    if not 5 <= size <= 200:
        return jsonify(ok=False, error="ขนาดรูปต้องอยู่ระหว่าง 5-200 เมตร")
    if not 3 <= alt <= 60:
        return jsonify(ok=False, error="ความสูงต้องอยู่ระหว่าง 3-60 เมตร")
    if state["running"]:
        return jsonify(ok=False, error="โดรนกำลังทำงานอยู่ รอให้จบหรือกดหยุดก่อน")

    path = build_path(pixels, size)
    if not path or len(path) < 2:
        return jsonify(ok=False, error="รูปเล็กเกินไป ลองวาดใหม่ให้ใหญ่ขึ้น")

    stop_flag.clear()
    with lock:
        state["running"] = True
        plan[:] = [list(p) for p in path]
        trail.clear()
    threading.Thread(target=mission, args=(path, alt), daemon=True).start()
    return jsonify(ok=True, points=len(path))


@app.route("/stop", methods=["POST"])
def stop():
    """ปุ่มหยุด: ยกเลิกการบินตามรูปแล้วลงจอดทันที"""
    stop_flag.set()
    set_mode("LAND")
    say("กดหยุด กำลังลงจอด...")
    return jsonify(ok=True)


# ===================== ส่วนที่ 8: เริ่มทำงาน =====================
if __name__ == "__main__":
    threading.Thread(target=reader, daemon=True).start()
    print(f"พร้อมแล้ว เปิดเบราว์เซอร์ที่ http://localhost:{PORT}")
    app.run(host="127.0.0.1", port=PORT, threaded=True)
    