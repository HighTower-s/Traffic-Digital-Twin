# คำสั่งทั้งหมดของ AI Worker

รันทุกคำสั่งจากโฟลเดอร์ `ai-worker/` (เปิด venv ก่อน: `.\.venv\Scripts\Activate.ps1`)

> ภาพรวมโปรเจกต์ → [`README.md`](README.md) · เหตุผลเชิงออกแบบ → [`CLAUDE.md`](CLAUDE.md)

---

## ลำดับการใช้งานปกติ

```
1. calibrate --preview     ตรวจว่าโซนวางถูก        (วินาที)
2. main                    ตรวจจับ + วัด           (นาที — รัน YOLO)
3. replay --fast           ดูผลตัดสิน + จูนเกณฑ์    (วินาที)
4. replay --backend        ส่งเข้า backend/Unity   (เท่าความยาวคลิป)
```

**ทำไมแยก 2/3:** ขั้น 2 แพง (รัน YOLO ทั้งคลิป) แต่ขั้น 3 ถูกมากและต้องปรับเกณฑ์บ่อย
→ วัดครั้งเดียวเก็บไฟล์ไว้ แล้วจูนเกณฑ์ซ้ำได้เรื่อย ๆ โดยไม่ต้องรัน YOLO ใหม่

---

## 1. `calibrate` — กำหนด/ตรวจโซน

```bash
python -m src.calibrate --preview                  # ดูโซนปัจจุบันทับเฟรมจริง (ไม่วาดใหม่)
python -m src.calibrate --preview --save zone.jpg  # เซฟเป็นไฟล์ภาพแทนเปิดหน้าต่าง
python -m src.calibrate                            # วาดใหม่ 2 โซน (in, out)
python -m src.calibrate --zones out                # วาดโซนเดียว (ถนน/คลิปทางเดียว)
python -m src.calibrate --frame 90                 # ใช้เฟรมอื่นเป็นพื้นหลัง (เริ่มต้น 60)
python -m src.calibrate --video data/input_videos/x.mp4   # ระบุวิดีโอเอง
```

**ปุ่มตอนวาด:** คลิกซ้าย = เพิ่มจุด · `Enter` = จบรูป · `u` = undo · `r` = เริ่มรูปใหม่ · `q` = เลิก

**วาด 3 รูปต่อโซน** ตามลำดับ:
| # | รูป | ใช้ทำอะไร |
|---|---|---|
| 1 | `polygon` | พื้นที่ตรวจว่ารถข้ามเส้นถูกโซนไหม |
| 2 | `line` (2 จุด) | เส้นนับรถ |
| 3 | `occupancyPolygon` | พื้นที่วัดความหนาแน่น — **วาดให้ครอบถนนยาวกว่ารูปที่ 1** |

จบแล้ว print YAML ออกมา ก็อปวางใน `config.yaml`

> 💡 ถ้า `polygon`/`line` เดิมนับได้แม่นอยู่แล้ว **ก็อปแค่บรรทัด `occupancyPolygon`** ไปแปะเพิ่ม
> อย่าแทนที่ทั้งบล็อก จะได้ไม่เสียค่าที่จูนไว้ดีแล้ว

**สีในโหมด preview:** โซนทึบ = `occupancyPolygon` · เส้นขาว = `polygon` นับ · เส้นแดง = เส้นนับ

---

## 2. `main` — ตรวจจับและวัด (ขั้นที่ใช้เวลา)

```bash
python -m src.main                        # ใช้ config.yaml
python -m src.main --config other.yaml    # ใช้ config อื่น
```

**ปุ่มระหว่างรัน:** `q` = ออก · `เว้นวรรค` = หยุด/เล่นต่อ

**ได้ไฟล์ใน `data/output_results/`:**
| ไฟล์ | 1 บรรทัด = | เนื้อหา |
|---|---|---|
| `counts.csv` | รถ 1 คันที่นับได้ | `frame, videoTimeSec, trackId, type, zone, direction, x, y` |
| `anomalies.csv` | รถ 1 คันที่ถูกปฏิเสธ | + `reason` — **ใช้ไล่หาว่าทำไมตัวเลขไม่ตรงกับที่นับมือ** |
| `events.jsonl` | รถ 1 คันที่ข้ามเส้น | spawn event ส่งให้ Unity |
| `traffic_state.jsonl` | ช่วงเวลา 1 หน้าต่าง | `occupancy` + `vehicleFlowRate` + `motorcycleFlowRate` (**ยังไม่มีคำตัดสิน**) |

> หน้าต่างสุดท้ายที่สั้นกว่าครึ่งหนึ่งของ `window_sec` จะถูกทิ้ง — flow คำนวณจาก
> `คัน × 60 ÷ วินาที` ช่วงสั้นเกินไปทำให้รถคันเดียวดันตัวเลขพุ่ง (1 วิ 1 คัน = 60/นาที)

---

## 3. `replay` — ตัดสินสถานะ + เล่นซ้ำ

```bash
python -m src.replay --fast       # ดูผลทันที ไม่หน่วงเวลา (พิมพ์อย่างเดียว ไม่ส่ง)  <-- ใช้ตอนจูนเกณฑ์
python -m src.replay              # เล่นตามจังหวะจริง (พิมพ์อย่างเดียว ไม่ส่ง)
python -m src.replay --backend    # ส่งเข้า backend จริง (ต้องเปิด backend ก่อน)

python -m src.replay --file data/output_results/events_jam.jsonl --fast   # ใช้ไฟล์อื่น
python -m src.replay --backend-url http://192.168.1.5:3000 --backend      # backend เครื่องอื่น
```

**ผลที่ได้:**
```
[ 100.0- 120.0s] HIGH_DENSITY  in[NORMAL](occ=1.81 veh=3.0 mc=3.0)  out[HIGH_DENSITY](occ=4.02 veh=18.0 mc=6.0)
[ 120.0- 140.0s] STANDSTILL    in[NORMAL](occ=0.73 veh=6.0 mc=0.0)  out[STANDSTILL](occ=4.21 veh=0.0 mc=9.0)
...
สรุปสถานะจราจรตลอดคลิป:
  normal   10 ช่วง  (100%)
```

ส่ง 2 สายคู่ขนาน: `events.jsonl` → `POST /api/ingest` · `traffic_state.jsonl` → `POST /api/traffic-state`

---

## 4. เทส / ตรวจคุณภาพโค้ด

```bash
python -m pytest -q          # เทสทั้งหมด (119 ตัว, ~0.3 วิ ไม่ต้องมี GPU/วิดีโอ)
python -m pytest -v          # แสดงชื่อเทสทีละตัว
python -m ruff check .       # lint
python -m ruff check --fix . # lint + แก้อัตโนมัติ
python -m black .            # จัดรูปแบบโค้ด
python -m black --check .    # เช็คอย่างเดียว ไม่แก้
```

---

## 5. ตรวจ GPU

```bash
python -c "import torch; print(torch.cuda.is_available())"
```

`False` = รันบน CPU (ช้ากว่าหลายเท่า) แก้ด้วย:
```bash
pip uninstall torch torchvision -y
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```
(`cu128` สำหรับ RTX 40/50-series — การ์ดรุ่นอื่นเช็คที่ [pytorch.org](https://pytorch.org/get-started/locally/))

---

## จูนเกณฑ์สถานการณ์จราจร

แก้ใน [`config.yaml`](config.yaml) แล้วรัน `python -m src.replay --fast` ดูผลทันที:

```yaml
traffic_state:
  window_sec: 10
  thresholds:
    busy_occupancy: 3.0       # occupancy เกินนี้ = หนาแน่น
    standstill_flow: 2.0      # รถยนต์/นาที ต่ำกว่านี้ + หนาแน่น = ติดสนิท
    slow_flow: 12.0           # รถยนต์/นาที ต่ำกว่านี้ + หนาแน่น = เคลื่อนตัวช้า
```

> **flow ที่ใช้ตัดสินไม่รวมมอเตอร์ไซค์** — มอเตอร์ไซค์มุดผ่านช่องว่างระหว่างรถที่จอดติดได้
> ถ้านับรวมจะกลบสัญญาณรถติดจนไม่มีวันเจอ `standstill` (พิสูจน์กับ `event-1.mp4`:
> ช่วงที่รถยนต์ข้าม 0 คัน มอเตอร์ไซค์ข้าม 4 คัน) `mc` ในผลลัพธ์จึงมีไว้ดูเฉย ๆ

**ตรรกะการตัดสิน** (อยู่ใน `src/traffic_state.py` → `classify_zone()`):

| | รถขยับได้ดี | รถขยับช้า | รถแทบไม่ขยับ |
|---|---|---|---|
| **รถน้อย** (occ ต่ำ) | `normal` | — | `normal` (ถนนว่าง) |
| **รถเยอะ** (occ สูง) | `high_density` | `slow_moving` | `standstill` |

> ต้องดู occupancy ก่อนเสมอ ไม่งั้น "ถนนว่าง" (flow=0) จะถูกตัดสินเป็น `standstill`

**`in[...]` / `out[...]` คือคำตัดสินของฝั่งนั้นเอง** ส่วนตัวใหญ่ข้างหน้าคือค่ารวม (โซนที่แย่สุด) —
ถนน 2 ฝั่งติดไม่พร้อมกัน ตัวอย่างข้างบนขาเข้าโล่งปกติขณะขาออกติดสนิท

---

## เชื่อมกับ backend

```bash
# terminal 1
cd ../backend && npm run dev        # http://localhost:3000

# terminal 2
cd ai-worker && python -m src.replay --backend
```

เปิด `http://localhost:3000/` ดู dashboard สด

**2 ทางเลือกในการส่ง:**
| วิธี | ส่งอะไรบ้าง | จังหวะเวลา | เหมาะกับ |
|---|---|---|---|
| `send_to_backend: true` ใน config.yaml (ส่งตอน `main.py`) | **spawn event เท่านั้น** ❌ ไม่มีสถานะจราจร | ❌ ไม่ตรงจังหวะจริง | ทดสอบเร็ว ๆ |
| `python -m src.replay --backend` | ✅ spawn event **+ สถานะจราจร** | ✅ ตรงจังหวะวิดีโอ | **เดโมจริง** |

> ⚠️ **ถ้า dashboard ขึ้นรถแต่การ์ด State ค้างที่ "waiting…"** แปลว่ายังไม่มีใครส่ง `traffic_state`
> ไปเลย — `main.py` ส่งแค่ spawn (ตอนนั้นยังไม่มีคำตัดสิน) และ `replay` ที่ไม่ใส่ `--backend`
> ไม่ส่งอะไรเลย **ต้องรัน `python -m src.replay --backend`**
> (ถ้าไม่ใส่ `--fast` ด้วย การ์ดจะว่าง 10 วินาทีแรกเป็นปกติ เพราะหน้าต่างแรกปิดที่วินาทีที่ 10)

---

## ⚠️ สถานะปัจจุบัน

- ✅ `POST /api/traffic-state` พร้อมใช้แล้ว — ทดสอบครบวงจรผ่าน (82 payload สำเร็จ 0 ล้มเหลว)
- ⚠️ เกณฑ์ใน `config.yaml` **ยังไม่ได้จูนกับคลิปรถติดจริง** — วัดจาก `traffic-5` (จราจรปกติ)
  ได้ occupancy 0.20–2.76 ซึ่ง `busy_occupancy: 3.0` เฉียดมาก (ห่างแค่ 0.24)
- ⚠️ **Unity ยังไม่รองรับ** — เพื่อนต้องเขียน handler รับ event `traffic_state` เอง
