import time
import math
from pymavlink import mavutil

# ===================== ส่วนที่ 1: ค่าที่ปรับได้ =====================
ALT = 15        # ความสูงที่บิน (เมตร)
SCALE = 1.5     # ขนาดหัวใจ (1.5 = กว้างประมาณ 48 เมตร) เพิ่ม = ใหญ่ขึ้น
POINTS = 40     # จำนวนจุดที่ใช้วาด ยิ่งมากเส้นยิ่งเนียน
REACH = 2.0     # ถือว่า "ถึงจุดแล้ว" เมื่อห่างไม่เกินกี่เมตร

# ===================== ส่วนที่ 2: เชื่อมต่อโดรน =====================
master = mavutil.mavlink_connection("tcp:127.0.0.1:5762")  # พอร์ตของตัวจำลอง
master.wait_heartbeat()
print("เชื่อมต่อสำเร็จ!")

# ขอให้โดรนส่งข้อมูลมาถี่ๆ (10 ครั้ง/วินาที)
master.mav.request_data_stream_send(
    master.target_system, master.target_component,
    mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)

# ที่เก็บสถานะล่าสุดของโดรน
state = {"alt": 0.0, "armed": False, "mode": None, "n": 0.0, "e": 0.0}

# ===================== ส่วนที่ 3: ฟังก์ชันช่วย =====================
def poll():
    """อ่านข้อความที่ค้างทั้งหมดจากโดรน แล้วอัปเดต state"""
    while True:
        msg = master.recv_match(blocking=False)
        if msg is None:
            break
        t = msg.get_type()
        if t == "GLOBAL_POSITION_INT":
            state["alt"] = msg.relative_alt / 1000          # ความสูง (เมตร)
        elif t == "LOCAL_POSITION_NED":
            state["n"] = msg.x                              # ตำแหน่งทิศเหนือ (เมตร)
            state["e"] = msg.y                              # ตำแหน่งทิศตะวันออก (เมตร)
        elif t == "HEARTBEAT" and msg.get_srcSystem() == master.target_system:
            state["armed"] = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            state["mode"] = msg.custom_mode
        elif t == "STATUSTEXT":
            print("  [โดรนแจ้ง]", msg.text)

def wait(seconds):
    """รอตามเวลาที่กำหนด โดยอ่านข้อมูลจากโดรนไปด้วย"""
    end = time.time() + seconds
    while time.time() < end:
        poll()
        time.sleep(0.1)

def set_mode(name):
    """เปลี่ยนโหมดการบิน (GUIDED, LAND ฯลฯ)"""
    mode_id = master.mode_mapping()[name]
    master.mav.set_mode_send(
        master.target_system,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED, mode_id)
    for _ in range(50):
        wait(0.2)
        if state["mode"] == mode_id:
            print(f"เปลี่ยนเป็นโหมด {name} แล้ว")
            return True
    print(f"เปลี่ยนเป็นโหมด {name} ไม่สำเร็จ")
    return False

def goto(north, east):
    """สั่งบินไปจุดที่ห่างจากจุดเริ่มต้น north เมตรทางเหนือ, east เมตรทางตะวันออก"""
    master.mav.set_position_target_local_ned_send(
        0, master.target_system, master.target_component,
        mavutil.mavlink.MAV_FRAME_LOCAL_NED,   # พิกัดอิงจากจุดเริ่มต้น (หน่วยเมตร)
        0b0000111111111000,                    # บอกว่า "ใช้เฉพาะตำแหน่ง x,y,z" ค่าอื่นไม่สน
        north, east, -ALT,                     # z เป็นลบ = สูงขึ้น (ระบบ NED)
        0, 0, 0, 0, 0, 0, 0, 0)

def fly_to(north, east, timeout=40):
    """บินไปจุดนั้นแล้วรอจนถึง (หรือหมดเวลา)"""
    start = time.time()
    while time.time() - start < timeout:
        goto(north, east)                      # ส่งคำสั่งซ้ำเรื่อยๆ ให้แน่ใจว่าโดรนรับ
        wait(0.5)
        dist = math.hypot(state["n"] - north, state["e"] - east)
        if dist < REACH:
            return True
    return False

# ===================== ส่วนที่ 4: สร้างจุดรูปหัวใจ =====================
# สูตรหัวใจมาตรฐาน: t วิ่งจาก 0 ถึง 2π
#   x = 16 sin³(t)
#   y = 13cos(t) - 5cos(2t) - 2cos(3t) - cos(4t)
heart = []
for i in range(POINTS):
    t = 2 * math.pi * i / POINTS
    x = 16 * math.sin(t) ** 3
    y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
    heart.append((y * SCALE, x * SCALE))       # (เหนือ, ตะวันออก) y→เหนือ x→ตะวันออก

# ===================== ส่วนที่ 5: ขั้นตอนการบิน =====================
wait(3)

# 5.1 ตั้งโหมด GUIDED (โหมดที่สั่งบินไปจุดต่างๆ ได้)
if not set_mode("GUIDED"):
    raise SystemExit

# 5.2 ติดเครื่อง (ลองซ้ำจนกว่าระบบพร้อม)
print("รอระบบพร้อมแล้วติดเครื่อง...")
for attempt in range(60):
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0, 1, 0, 0, 0, 0, 0, 0)
    wait(3)
    if state["armed"]:
        break
    print(f"  ยังติดเครื่องไม่ได้ (ครั้งที่ {attempt + 1})")

if not state["armed"]:
    print("ติดเครื่องไม่สำเร็จ หยุดการทำงาน")
    raise SystemExit
print("ติดเครื่องสำเร็จ!")

# 5.3 ขึ้นบินตรงขึ้นไปที่ความสูง ALT
master.mav.command_long_send(
    master.target_system, master.target_component,
    mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
    0, 0, 0, 0, 0, 0, 0, ALT)
print("กำลังขึ้นบิน...")
start = time.time()
while time.time() - start < 40:
    wait(1)
    print(f"ความสูง: {state['alt']:.1f} เมตร")
    if state["alt"] >= ALT - 0.5:
        break

# 5.4 บินวนตามจุดรูปหัวใจ
print("เริ่มวาดหัวใจ...")
for idx, (n, e) in enumerate(heart + [heart[0]]):   # ปิดท้ายด้วยจุดแรก ให้เส้นครบวง
    ok = fly_to(n, e)
    print(f"จุดที่ {idx + 1}/{POINTS + 1}: เหนือ {n:.0f} ม. ตะวันออก {e:.0f} ม. "
          + ("ถึงแล้ว" if ok else "หมดเวลา ข้ามไปจุดต่อไป"))

# 5.5 กลับจุดเริ่มต้นแล้วลงจอด
print("วาดเสร็จ กลับจุดเริ่มต้น...")
fly_to(0, 0)
set_mode("LAND")
print("กำลังลงจอด...")
start = time.time()
while time.time() - start < 60:
    wait(1)
    print(f"ความสูง: {state['alt']:.1f} เมตร")
    if state["alt"] < 0.3 and not state["armed"]:
        break
print("จบการทำงาน")