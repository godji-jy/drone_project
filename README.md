# โปรเจกต์วาดเส้นทางให้โดรนบิน (ArduPilot SITL + Flask)

วาดรูปบนหน้าเว็บ กดเริ่มบิน แล้วโดรนจำลองจะบินตามรูปที่วาด
หน้าเว็บมี 3 ส่วน: ซ้าย = ความสูง, กลาง = กระดานวาด, ขวา = การเคลื่อนที่ (มองจากด้านบน)

## ไฟล์ในโฟลเดอร์ drone_project

| ไฟล์ | หน้าที่ |
|---|---|
| `server.py` | รับรูปจากหน้าเว็บ แล้วสั่งโดรนบิน (Flask + pymavlink) |
| `index.html` | หน้าเว็บ มีกระดานวาด กราฟความสูง และแผนที่การเคลื่อนที่ |
| `fly.py` | สคริปต์ทดสอบบินแบบไม่มีหน้าเว็บ (ขึ้น-ลงจอด / รูปหัวใจ) |
| `requirements.txt` | รายการไลบรารี Python ที่ต้องติดตั้ง |
| `venv/` | virtual environment (ไม่ต้องอัปโหลดขึ้น GitHub) |

`server.py` และ `index.html` ต้องอยู่โฟลเดอร์เดียวกัน ไม่งั้นหน้าเว็บจะขึ้น 404

## ติดตั้งโปรเจกต์จาก GitHub (เครื่องใหม่หรือโหลดมาใช้)

**1. ติดตั้งโปรแกรมพื้นฐาน**
- Windows: VS Code (พร้อม extension WSL), WSL2 + Ubuntu (`wsl --install` ใน PowerShell แบบ Administrator)
- Ubuntu:
  ```
  sudo apt update
  sudo apt install -y git python3 python3-pip python3-venv
  ```

**2. ติดตั้งตัวจำลองโดรน ArduPilot**
```
cd ~
git clone --recurse-submodules https://github.com/ArduPilot/ardupilot.git
cd ardupilot
Tools/environment_install/install-prereqs-ubuntu.sh -y
. ~/.profile
```
ขั้นนี้ใช้เวลานานที่สุด

**3. ติดตั้ง QGroundControl (Windows)**
โหลดจาก qgroundcontrol.com แล้วตั้ง Application Settings > Comm Links > Add: Name `SITL`, Type `TCP`, Address `127.0.0.1`, Port `5760`

**4. โหลดโปรเจกต์นี้**
```
cd ~
git clone https://github.com/ชื่อบัญชี/ชื่อ-repo.git drone_project
cd drone_project
```
(ถ้าโหลดเป็นไฟล์ ZIP ให้แตกไฟล์ไว้ที่ `~/drone_project`)

**5. ติดตั้งไลบรารีด้วย requirements.txt**
```
cd ~/drone_project
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
ทดสอบว่าลงสำเร็จ:
```
python -c "import pymavlink, flask; print('OK')"
```

## ติดตั้งไลบรารีด้วย requirements.txt

`requirements.txt` คือรายการไลบรารีที่โปรเจกต์ต้องใช้ ติดตั้งทั้งหมดด้วยคำสั่งเดียว

| ต้องการ | คำสั่ง (ต้องมี `(venv)` หน้าบรรทัด) |
|---|---|
| ติดตั้งทุกตัวตามรายการ | `pip install -r requirements.txt` |
| ดูว่าลงอะไรไว้บ้าง | `pip list` |
| สร้างรายการจากที่ลงไว้ตอนนี้ | `pip freeze > requirements.txt` |
| อัปเดตไลบรารี | `pip install --upgrade -r requirements.txt` |

เนื้อหาในไฟล์:
```
pymavlink
flask
```

ถ้าติดตั้งแล้ว error เรื่อง Python 3.14 ให้เก็บข้อความ error ไว้ตรวจสอบ ไลบรารีบางตัวอาจยังไม่รองรับ Python เวอร์ชันใหม่มาก

## วิธีรัน (ต้องเรียงตามลำดับ)

**1. เปิด VS Code แล้วเชื่อม Ubuntu**
Ctrl+Shift+P > `WSL: Connect to WSL` แล้วเปิดโฟลเดอร์ `drone_project`

**2. Terminal 1 : เปิดโดรนจำลอง (ปล่อยค้าง ห้ามปิด)**
```
. ~/.profile
cd ~/ardupilot/ArduCopter
sim_vehicle.py -v ArduCopter --console --no-mavproxy
```

**3. เปิด QGroundControl แล้วกด Connect**
เลือก `SITL` > Connect รอจนมุมซ้ายบนขึ้น **Ready**
(ต้องทำก่อนข้อ 4 เพราะพอร์ต 5762 เปิดหลังมีโปรแกรมต่อพอร์ต 5760)

**4. Terminal 2 : เปิดเซิร์ฟเวอร์ (ปล่อยค้าง)**
```
cd ~/drone_project
source venv/bin/activate
python server.py
```
ต้องเห็น `เชื่อมต่อสำเร็จ!` และ `พร้อมแล้ว`

**5. เปิดเบราว์เซอร์บน Windows**
ไปที่ http://localhost:5000 ลากเมาส์วาดรูป แล้วกด **เริ่มบิน**

สรุปลำดับ: ตัวจำลอง -> QGroundControl -> server.py -> เบราว์เซอร์

## วิธีปิด (ย้อนกลับ)

1. ปิดแท็บเบราว์เซอร์
2. Ctrl+C ที่ `server.py`
3. Ctrl+C ที่ตัวจำลอง

## วิธีใช้หน้าเว็บ

- **กระดานกลาง:** กดค้างแล้วลากเมาส์วาด จุดเขียว = จุดเริ่มวาด จุดแดง = จุดจบ
- **ขนาดรูปจริง (เมตร):** ด้านที่ยาวที่สุดของรูปจะเท่ากับค่านี้ (ตั้งต้น 30)
- **ความสูงที่บิน (เมตร):** ตั้งต้น 15 (ช่วง 3-60)
- **เริ่มบิน:** ลำดับคือ GUIDED > ติดเครื่อง > ขึ้นบิน > บินตามรูป > กลับจุดเริ่มต้น > ลงจอด
- **หยุดและลงจอด:** ยกเลิกแล้วสั่งลงจอดทันที
- **ล้างกระดาน:** วาดใหม่
- **ซ้าย:** ความสูง แถบวัด กราฟย้อนหลัง สถานะ โหมด
- **ขวา:** เส้นประสีน้ำเงิน = เส้นที่วางแผน, เส้นสีส้ม = เส้นที่โดรนบินจริง, จุดเขียว = ตำแหน่งโดรน

## พอร์ตที่ใช้

| พอร์ต | ใครใช้ |
|---|---|
| 5760 | QGroundControl |
| 5762 | server.py / fly.py |
| 5000 | หน้าเว็บ (localhost) |

## แก้ปัญหาเร็วๆ

| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| หน้าเว็บขึ้น 404 | หา `index.html` ไม่เจอ ตรวจด้วย `ls ~/drone_project` ว่าชื่อถูกและอยู่ข้าง `server.py` แล้วกด F5 |
| `server.py` ขึ้น "เชื่อมต่อไม่ได้" | ตัวจำลองยังไม่รัน หรือยังไม่ได้ Connect QGroundControl ทำข้อ 2-3 ให้ครบแล้วรันใหม่ |
| `ModuleNotFoundError: flask` หรือ `pymavlink` | ยังไม่ได้ลงไลบรารี หรือไม่ได้อยู่ใน venv ให้รัน `source venv/bin/activate` แล้ว `pip install -r requirements.txt` |
| `python: command not found` | ยังไม่เข้า venv ให้รัน `source venv/bin/activate` |
| `sim_vehicle.py: command not found` | รัน `. ~/.profile` ก่อน |
| กดเริ่มแล้วค้างที่ "กำลังติดเครื่อง" | GPS จำลองยังไม่พร้อม รอ 1-3 นาที ดูข้อความ [โดรนแจ้ง] ในกล่องบันทึก |
| ความสูงขึ้นแต่แผนที่ขวาไม่ขยับ | ตัวจำลองอาจไม่ส่งตำแหน่งแบบ local ให้แจ้งเพื่อแก้โค้ด |
| ข้อความสีแดง WARNING development server | ปกติของ Flask ไม่ต้องสนใจ |
| `systemd-binfmt failed` ตอน apt | ปกติของ WSL ไม่กระทบงาน |

## ข้อจำกัด

- ตัวจำลองไม่มีลมและ GPS เพี้ยน รูปจึงสวยกว่าโดรนจริง ถ้าบินจริง GPS คลาดเคลื่อนประมาณ 1-3 เมตร
- เส้นที่วาดมือจะถูกลดเหลือไม่เกิน 120 จุด มุมอาจโค้งมนกว่าที่วาด
- ถ้าจะบินโดรนจริง ต้องศึกษากฎ กสทช. และ กพท. เรื่องการขึ้นทะเบียนและพื้นที่ห้ามบิน และเช็กข้อมูลล่าสุดก่อนเสมอ

## ไอเดียต่อยอด

1. ปุ่มรูปสำเร็จรูป (วงกลม ดาว หัวใจ)
2. แปลงภาพ/โลโก้เป็นเส้นทางบินด้วย OpenCV
3. บันทึกเส้นทางที่บินแล้วทำกราฟ 3 มิติด้วย matplotlib
4. เพิ่มกล้องและ AI ตรวจจับวัตถุ
