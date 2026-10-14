# คำสั่งทั้งหมด

รันจากโฟลเดอร์ `ai-worker/` (เปิด venv ก่อน: `.\.venv\Scripts\Activate.ps1`)

> ติดตั้งครั้งแรก → [`../README.md`](../README.md) · เหตุผลเชิงออกแบบ → [`CLAUDE.md`](CLAUDE.md)

---

## เริ่มตรงนี้ — 4 flow ที่ใช้จริง

| อยากทำอะไร | คำสั่ง | กี่คำสั่ง | ใช้เวลา |
|---|---|---|---|
| **จูนเกณฑ์** | `python -m src.replay --fast` | **1** | วินาที |
| **เดโม** | `npm run dev` (terminal 1) → `python -m src.replay --backend` (terminal 2) | **2** | เท่าความยาวคลิป |
| **สลับคลิป** | `python -m src.main --config configs/traffic-5.yaml --replay` | **1** | นาที |
| **คลิปใหม่** | `calibrate` → สร้างไฟล์ใน `configs/` → `calibrate --preview` → `main --replay` | **3** | นาที |
| **เดโมจากชุดที่เก็บไว้** | `npm run dev` (terminal 1) → `python -m src.replay --from runs/<ชุด> --backend` (terminal 2) | **2** | เท่าความยาวคลิป |

**ทำไมจูนเกณฑ์เหลือคำสั่งเดียว:** การ "วัด" (รัน YOLO) แยกออกจากการ "ตัดสิน" (ใช้เกณฑ์)
วัดครั้งเดียวเก็บลงไฟล์ แล้วเปลี่ยนเกณฑ์กี่รอบก็ได้โดยไม่ต้องรัน YOLO ซ้ำ

---

## 1. `calibrate` — วางโซน

```bash
python -m src.calibrate                   # วาดใหม่ 2 โซน (in, out)
python -m src.calibrate --zones out       # วาดโซนเดียว (ถนนทางเดียว)
python -m src.calibrate --preview         # ดูโซนปัจจุบันทับเฟรมจริง (ไม่วาดใหม่)
python -m src.calibrate --config configs/traffic-5.yaml --preview   # ชุดอื่น
python -m src.calibrate --preview --save zone.jpg   # เซฟเป็นภาพแทนเปิดหน้าต่าง
python -m src.calibrate --frame 90        # ใช้เฟรมอื่นเป็นพื้นหลัง (เริ่มต้น 60)
python -m src.calibrate --video data/input_videos/x.mp4
```

**ปุ่มตอนวาด:** คลิกซ้าย = เพิ่มจุด · `Enter` = จบรูป · `u` = undo · `r` = เริ่มใหม่ · `q` = เลิก

**วาด 3 รูปต่อโซน** ตามลำดับ:

| # | รูป | ใช้ทำอะไร |
|---|---|---|
| 1 | `polygon` | พื้นที่ตรวจว่ารถข้ามเส้นถูกโซนไหม |
| 2 | `line` (**2 จุดพอดี**) | เส้นนับรถ |
| 3 | `occupancyPolygon` | พื้นที่วัดความหนาแน่น — **วาดให้ครอบถนนยาวกว่ารูปที่ 1** |

จบแล้วโปรแกรม print YAML ออกมา **ก็อปไฟล์ชุดเดิมใน [`configs/`](configs/) ตั้งชื่อใหม่ แล้วแทนที่บล็อก `zones`**
(ดูวิธี → [`configs/README.md`](configs/README.md))

### สลับชุดโซน — ชี้ `--config` ไปที่ไฟล์

**ไม่มี `config.yaml` ที่ root แล้ว** ทุกชุดอยู่ใน `configs/` ไฟล์ละมุมกล้อง
แต่ละไฟล์**สมบูรณ์ในตัวเอง** (โซน + เกณฑ์ + ค่ารัน) ไม่มีการผสมไฟล์

```bash
python -m src.main --config configs/traffic-5.yaml --replay
python -m src.replay --config configs/traffic-5.yaml --fast
python -m src.calibrate --config configs/traffic-5.yaml --preview
```

**ไม่ใส่ `--config` = ใช้ `configs/event-2.yaml`** (ค่าเริ่มต้น)

> ⚠️ **ชี้ `--config` ให้ตรงกันทั้ง `main` และ `replay`** — ถ้า `main` ใช้ event-2 แล้ว
> `replay` ใช้ traffic-5 จะเอาเกณฑ์ผิดชุดมาตัดสินข้อมูลโดยไม่มี error
> (ใช้ `main --config ... --replay` ปลอดภัยกว่า เพราะส่ง `--config` ต่อให้อัตโนมัติ)

### กฎ 2 ข้อของโซน

**ชื่อโซนต้องเป็น `in` หรือ `out` เท่านั้น** — ชื่อถูกส่งออกเป็น field `direction` ของ spawn event
ตรง ๆ ตั้งชื่ออื่นจะ error ตั้งแต่โหลด config

**`expectedDirection` ตั้งอิสระจากชื่อโซน** — บอกว่ารถในโซนนั้นเคลื่อนที่ทางไหน **ในภาพ**

```
toward = เลื่อนลงล่างในภาพ (วิ่งเข้าหากล้อง)
away   = เลื่อนขึ้นบนในภาพ (วิ่งออกจากกล้อง)
```

เลนขาเข้าอาจวิ่งออกจากกล้องก็ได้ ขึ้นกับว่ากล้องหันทางไหน → `name: in` คู่กับ
`expectedDirection: away` **ถูกต้องและใช้ได้**

> 💡 ถ้า `polygon`/`line` เดิมนับแม่นอยู่แล้ว **ก็อปแค่บรรทัด `occupancyPolygon`** ไปแปะเพิ่ม
> อย่าแทนทั้งบล็อก จะได้ไม่เสียค่าที่จูนไว้

**สีในโหมด preview:** โซนทึบ = `occupancyPolygon` · เส้นขาว = `polygon` นับ · เส้นแดง = เส้นนับ

---

## 2. `main` — ตรวจจับ + วัด (ขั้นที่ใช้เวลา)

```bash
python -m src.main                      # ใช้ configs/event-2.yaml (ค่าเริ่มต้น)
python -m src.main --config configs/traffic-5.yaml
python -m src.main --replay             # ตรวจจับ -> โชว์ผลตัดสินต่อทันที   <-- ใช้บ่อยสุด
python -m src.main --replay-backend     # ตรวจจับ -> ส่งเข้า backend ต่อทันที
```

**ปุ่มระหว่างรัน:** `q` = ออก · `เว้นวรรค` = หยุด/เล่นต่อ

`--replay` ช่วยให้ไม่ต้องสั่ง `python -m src.replay` แยกอีกคำสั่ง

---

## 3. `replay` — ตัดสิน + ดูผล

```bash
python -m src.replay --fast      # ดูผลทันที (พิมพ์อย่างเดียว ไม่ส่งออก)  <-- ใช้ตอนจูนเกณฑ์
python -m src.replay --config configs/traffic-5.yaml --fast   # ชุดอื่น
python -m src.replay             # เล่นตามจังหวะจริง (พิมพ์อย่างเดียว ไม่ส่งออก)
python -m src.replay --backend   # ส่งเข้า backend จริง (ต้องเปิด backend ก่อน)

python -m src.replay --from runs/event-2_slow-moving --backend   # ชุดที่เก็บไว้
python -m src.replay --backend-url http://192.168.1.5:3000 --backend
```

### `--from` — เล่นชุดที่เก็บไว้ ไม่ต้องรัน YOLO ใหม่

`main` เขียนทับ `data/output_results/` ทุกครั้งที่รัน ชุดที่อยากเก็บต้องย้ายออกไปไว้ใน
[`runs/`](runs/) เอง (3 ไฟล์: `config.yaml` + `events.jsonl` + `traffic_state.jsonl`)
แล้วเรียกด้วยโฟลเดอร์เดียว

```bash
python -m src.replay --from runs/event-2_slow-moving --fast
```

`config.yaml` ต้องอยู่ในโฟลเดอร์ด้วยเสมอ ไม่งั้น error — เกณฑ์ผูกกับมุมกล้อง เอาของชุดอื่น
มาตัดสินไม่ได้ · ใส่ `--config` / `--file` / `--state-file` ซ้ำกับ `--from` ไม่ได้ (error)

**เพื่อนที่ทำ Unity ใช้แค่คำสั่งนี้** ไม่ต้องมีคลิป ไม่ต้องลง YOLO ไม่ต้องมี GPU —
ดู [`runs/README.md`](runs/README.md)

**ผลที่ได้:**

```
[   0.0-  20.0s] NORMAL        in[NORMAL](occ=0.79 veh=3.0 mc=9.0)  out[NORMAL](occ=1.78 veh=12.0 mc=9.0)
[  60.0-  80.0s] SLOW_MOVING   in[NORMAL](occ=2.68 veh=15.0 mc=9.0)  out[SLOW_MOVING](occ=4.97 veh=30.0 mc=15.0)
[ 180.0- 200.0s] SLOW_MOVING   in[SLOW_MOVING](occ=10.90 veh=9.0 mc=9.0)  out[NORMAL](occ=0.00 veh=0.0 mc=0.0)

Traffic-state summary for the whole clip:
  normal          5 windows  (50%)
  slow_moving     5 windows  (50%)
```

**`in[...]` / `out[...]` = คำตัดสินของฝั่งนั้นเอง** ส่วนตัวใหญ่ข้างหน้าคือค่ารวม (โซนที่แย่สุด)

ถนน 2 ฝั่งติดไม่พร้อมกัน — ตัวอย่างข้างบนช่วง 60–80s **ขาออกติดขณะขาเข้าปกติ** แต่พอถึง
180–200s **กลับด้านกัน** ขาเข้าติดหนัก (occ 10.90) ส่วนขาออกว่างสนิท (occ 0.00)

ส่ง 2 สายคู่ขนาน: `events.jsonl` → `POST /api/ingest` · `traffic_state.jsonl` → `POST /api/traffic-state`

---

## 4. `backend` — dashboard / Unity

```bash
cd ../backend
npm run dev          # http://localhost:3000
npm test             # 59 เทส
npm run typecheck    # tsc --noEmit
npm run lint         # eslint
```

**Dashboard มี 3 หน้า** สลับด้วย URL hash:

| หน้า | URL | เนื้อหา |
|---|---|---|
| Overview | `localhost:3000/#overview` | สถานะปัจจุบัน + timeline แยกรายโซน + การ์ดโซน + feed |
| Traffic state | `localhost:3000/#state` | ตารางทุกหน้าต่าง occ/veh/mc + คำตัดสิน + สรุป % |
| JSON | `localhost:3000/#json` | payload ดิบทั้ง 3 ช่อง กรองได้ |

**2 ทางเลือกในการส่ง:**

| วิธี | ส่งอะไร | จังหวะเวลา |
|---|---|---|
| `send_to_backend: true` ใน config (ตอน `main`) | **spawn เท่านั้น** ❌ ไม่มีสถานะจราจร | ❌ ไม่ตรงจังหวะ |
| `replay --backend` | ✅ spawn **+ สถานะจราจร** | ✅ ตรงจังหวะวิดีโอ |

---

## จูนเกณฑ์สถานการณ์จราจร

แก้ในไฟล์ชุดโซนที่ใช้อยู่ แล้ว `python -m src.replay --fast` เห็นผลทันที

เกณฑ์อยู่ใน **ไฟล์ชุดที่ `--config` ชี้** (ค่าเริ่มต้น [`configs/event-2.yaml`](configs/event-2.yaml))
เพราะเกณฑ์ผูกกับขนาดกรอบและมุมกล้อง ย้ายข้ามชุดไม่ได้

```yaml
traffic_state:
  window_sec: 20
  thresholds:
    busy_occupancy: 4         # รถในกรอบเฉลี่ยเกินนี้ = หนาแน่น
    standstill_flow: 2.0      # = รถยนต์ข้าม 0 คัน
    slow_flow: 32.0           # = รถยนต์ข้าม 1-10 คัน
```

### แปลงเกณฑ์เป็น "จำนวนคัน"

หน้าต่าง 20 วินาที → **รถ 1 คัน = 3 คัน/นาที** เสมอ ค่าที่วัดได้จึงมีแค่ `0, 3, 6, 9, …`

| รถข้าม/20วิ | 0 | 1 | 2 | 4 | 8 | 10 | 11 |
|---|---|---|---|---|---|---|---|
| flow | 0 | 3 | 6 | 12 | 24 | 30 | 33 |

เกณฑ์ปัจจุบันจึงแปลว่า: `standstill` = 0 คัน · `slow_moving` = 1–10 คัน · `high_density` = 11 คันขึ้นไป

### ตรรกะการตัดสิน

`src/traffic_state.py` → `classify_zone()` ตรวจเรียงลงมา เจอข้อไหนก่อนตอบทันที

```python
if occupancy         < busy_occupancy:    return NORMAL        # ด่าน 1: รถเยอะไหม
if vehicle_flow_rate < standstill_flow:   return STANDSTILL
if vehicle_flow_rate < slow_flow:         return SLOW_MOVING
                                          return HIGH_DENSITY
```

| | รถขยับได้ดี | รถขยับช้า | รถแทบไม่ขยับ |
|---|---|---|---|
| **occ ต่ำ** | `normal` | `normal` | `normal` (ถนนว่าง) |
| **occ สูง** | `high_density` | `slow_moving` | `standstill` |

> **ต้องดู occupancy ก่อนเสมอ** ไม่งั้น "ถนนว่าง" (flow = 0) จะถูกตัดสินเป็น `standstill`

**flow ที่ใช้ตัดสินไม่รวมมอเตอร์ไซค์** — มอเตอร์ไซค์มุดผ่านรถที่จอดติดได้ ถ้านับรวมจะกลบ
สัญญาณรถติดจนไม่มีวันเจอ `standstill` (`mc` ในผลลัพธ์มีไว้ดูเฉย ๆ)

### ⚠️ ยังขาดข้อมูล 2 สถานะ

`high_density` กับ `standstill` **ยังไม่เคยปรากฏ เพราะยังไม่มีคลิปที่เป็นสภาพนั้นจริง**
ไม่ใช่เพราะเกณฑ์ตั้งผิด — ต้องถ่ายคลิปเพิ่มในช่วงเวลาที่รถติดหนักกว่านี้

---

## แก้อะไร ต้องรันอะไรใหม่

| เปลี่ยน | ต้องทำ |
|---|---|
| เกณฑ์ / ตรรกะตัดสิน / รูปแบบ payload | **`replay` พอ** |
| `window_sec` · `zones` · `imgsz` · โมเดล · คลิป · เปลี่ยน `--config` | **รัน `main` ใหม่** |
| อยากดูคลิปที่เคยวิเคราะห์ไว้แล้ว | **`replay --from runs/<ชุด>`** — ไม่ต้องรัน `main` ซ้ำ |

**กฎง่าย ๆ:** อะไรที่เกี่ยวกับ *การมองภาพ* หรือ *ขอบเขตเวลา* → ต้องรัน `main`
อะไรที่เป็น *การตีความตัวเลข* → `replay` พอ

> เช็คว่าข้อมูลเก่ากว่า config ไหม: ดูว่า `windowEndSec - windowStartSec` ใน
> `traffic_state.jsonl` ตรงกับ `window_sec` ใน config หรือเปล่า

---

## ไฟล์ผลลัพธ์อยู่ที่ไหนบ้าง

**`ai-worker/data/output_results/`** — จาก `main`

| ไฟล์ | 1 บรรทัด = | เนื้อหา |
|---|---|---|
| `counts.csv` | รถ 1 คันที่นับได้ | `frame, videoTimeSec, trackId, type, zone, direction, x, y` |
| `anomalies.csv` | รถ 1 คันที่ถูกปฏิเสธ | + `reason` — **ใช้ไล่หาว่าทำไมตัวเลขไม่ตรงกับที่นับมือ** |
| `events.jsonl` | รถ 1 คันที่ข้ามเส้น | spawn event |
| `traffic_state.jsonl` | 1 หน้าต่างเวลา | occupancy + flow (**ไม่มีคำตัดสิน** — ตัดสินตอน replay) |

**`backend/data/output/`** — payload ที่ backend broadcast ออกไปจริง
**ล้างใหม่ทุกครั้งที่ `replay --backend` เริ่มส่ง** (และตอนสตาร์ตเซิร์ฟเวอร์) ไฟล์จึงเป็นผลของรอบล่าสุดรอบเดียวเสมอ

| ไฟล์ | คือ |
|---|---|
| `spawn.jsonl` | payload ดิบ |
| `spawn_vehicle.jsonl` | **ของจริงที่ Unity ได้รับ** (ห่อ + ตัดเหลือ 5 field) |
| `traffic_state.jsonl` | สถานะจราจร (Unity ได้รับตรงนี้ไม่แปลง) |

> ปิดการบันทึกได้ด้วย `CAPTURE_PAYLOADS=false` ใน `backend/.env`

**`ai-worker/runs/`** — ชุดข้อมูลที่เก็บไว้เล่นซ้ำ (ก็อปเข้าไปเอง, commit เข้า git ได้)
ดู [`runs/README.md`](runs/README.md)

---

## เครื่องมือ

```bash
python -m pytest -q           # 138 เทส (~0.3 วิ ไม่ต้องมี GPU/วิดีโอ)
python -m pytest -v           # แสดงชื่อเทสทีละตัว
python -m ruff check .        # lint
python -m ruff check --fix .  # lint + แก้อัตโนมัติ
python -m black .             # จัดรูปแบบ
python -m black --check .     # เช็คอย่างเดียว

python -c "import torch; print(torch.cuda.is_available())"   # ตรวจ GPU
```

---

## เจอปัญหาแบบนี้ทำยังไง

| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| dashboard ขึ้นรถ แต่การ์ด State ค้าง "waiting…" | ไม่ได้ใส่ `--backend` — `main` ส่งแค่ spawn ส่วน `replay` เปล่า ๆ ไม่ส่งอะไรเลย |
| ตอนรันขึ้น `zone : **เดาให้อัตโนมัติ**` | ไฟล์ที่ `--config` ชี้ไม่มี `zones:` หรือย่อหน้าผิด |
| `ไม่พบไฟล์ config` | พิมพ์ path ผิด — error จะลิสต์ไฟล์ที่มีในโฟลเดอร์นั้นให้ |
| `anomalies.csv` มี `wrong_direction` เพียบ | `expectedDirection` ไม่ตรงทิศที่รถวิ่งจริงในภาพ ลองสลับ `toward` ↔ `away` |
| `anomalies.csv` มี `outside_polygon` เยอะ | `polygon` ไม่ครอบเลนบางเลน คลิกเพิ่มจุดไล่ขอบถนน |
| ตารางหน้า `#state` เรียงมั่ว / แถวเกิน | รัน replay ซ้ำโดยไม่รีเฟรชหน้า — รีเฟรชก่อนรันใหม่ทุกครั้ง |
| dashboard ข้อมูลขาดช่วงกลาง | socket หลุดแล้วต่อกลับ — backend ไม่เก็บประวัติ ข้อความที่พลาดหายถาวร |
| อยากได้ไฟล์ของรอบเดียวสะอาด ๆ | ได้อยู่แล้ว — `replay --backend` ล้างไฟล์ capture + ตัวนับให้ก่อนส่งทุกครั้ง |
| `replay` ขึ้น "ไม่พบไฟล์" | ยังไม่ได้รัน `main` |
| backend ขึ้น `port 3000 ถูกใช้งานอยู่แล้ว` | มี backend อีกตัวเปิดค้าง — Ctrl+C ที่ terminal นั้น หรือตั้ง `PORT=3001` ใน `backend/.env` |
| นับได้ 0 คันทั้งคลิป | เส้นนับอยู่นอก `polygon` (config.py ดักให้ตั้งแต่โหลด) หรือโซนวางผิดฝั่ง |
| `torch.cuda.is_available()` = `False` | ลง torch รุ่น CPU — `pip uninstall torch torchvision -y` แล้วลงใหม่ด้วย `--index-url https://download.pytorch.org/whl/cu128` (RTX 40/50-series) |
