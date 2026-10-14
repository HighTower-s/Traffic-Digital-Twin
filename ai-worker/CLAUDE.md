# AI Worker — CLAUDE.md

> อ่าน `../CLAUDE.md` และ `../docs/architecture.md` ก่อนไฟล์นี้
> ไฟล์นี้ครอบคลุมเฉพาะ context ของ AI Worker
> ทบทวนล่าสุด: 2026-08-12

---

## 0. สองชั้นของโมดูลนี้ — อ่านก่อน

| | **MVP Main** (เป้าหมายปลายทาง) | **Prototype** (รันได้ตอนนี้) |
|---|---|---|
| แหล่งภาพ | RTSP จากกล้อง CCTV (SICA) | ไฟล์ `.mp4` ที่ถ่ายถนนมาเอง |
| ตำแหน่ง (x, z) | พิกัดโลกจริง (เมตร) | **ไม่มี** — นับอย่างเดียว ไม่คำนวณตำแหน่ง |
| ความเร็ว | วัดจากภาพจริง | **ไม่มี** — ตัดออกจนกว่าจะวัดจริงได้ (§5) |
| เลนที่วิ่ง | ระบุได้ | **ไม่มี** — ตัดออกจนกว่าจะวัดจริงได้ (§5) |
| ปลายทาง | สตรีมเข้า backend ต่อเนื่อง | ไฟล์ใน `data/output_results/` เสมอ + POST เข้า backend ด้วยถ้าเปิด `send_to_backend: true` (ปิดเป็นค่าเริ่มต้น) |

ของที่โค้ดทำได้ **ตอนนี้** คือชั้น Prototype (§2) ส่วน MVP Main (§1) คือเป้าที่กำลังไต่ไปหา

---

## 1. MVP Main — เป้าหมายปลายทาง

Pipeline ที่ออกแบบไว้ (ตรงกับ `architecture.md` §2 และ `project-status.md` M2):

```
RTSP (CCTV) → YOLOv8 + ByteTrack → tracking ต่อคัน → payload (data-contract) → POST backend → Unity
```

ต่อรถ 1 คันต้องได้: **ชนิด**, **ทิศทาง**, **ตำแหน่ง (x, y=0, z)**, **ความเร็ว**, **เลน**
แล้วส่ง payload ตาม `docs/data-contract.md` เข้า backend ทุก ~1 วินาที

### Business Rules (จาก `architecture.md` §6 — บังคับ)

- conf < 0.5 → ทิ้ง detection
- `trackId` ต้องเสถียรข้ามเฟรมสำหรับรถคันเดิม (ByteTrack)
- `position.y` = `0.0` เสมอ (ระนาบพื้น)
- ห้าม `NaN` / `Infinity` หลุดเข้า payload
- เพดาน 120 คัน/เฟรม
- เป้าจังหวะส่ง ~1 เฟรม/วินาที

> **หมายเหตุ homography:** การหา position/speed จริง เดิมวางแผนใช้ homography แต่
> 2026-07-21 วัดกับวิดีโอจริงแล้วเพี้ยน (ความเร็วพุ่ง 200–290 km/h, พิกัดลอย) จึง **ยัง
> เปิดค้าง** ว่าจะกลับไปแก้ homography หรือหาวิธีอื่น — ดู pivot ใน `project-status.md`

---

## 2. Prototype — ของจริงที่รันได้ตอนนี้

รับ **ไฟล์วิดีโอ** (ยังไม่ได้สิทธิ์เข้า RTSP ของ SICA) แล้วนับรถที่ข้ามเส้น
**เวอร์ชันนี้นับอย่างเดียว ไม่มี lane และไม่มี speed** (ดู §5 — เหตุผลที่ตัดออก)

```
main.py  (อ่าน configs/<มุมกล้อง>.yaml)
  → detector.py  YOLOv8 + ByteTrack  (4 ชนิด: car / motorcycle / bus / truck)
  → counter.py   ข้ามเส้น → โหวตชนิด+ล็อก → ตรวจทิศ (toward/away) → กันนับซ้ำ → anomaly
  → emitter.py   spawn event → data/output_results/events.jsonl
  → poster.py    (ถ้า send_to_backend: true) POST payload เดียวกัน → backend/api/ingest
  → สรุปตอนจบ (รวมจำนวนที่ส่ง backend สำเร็จ/ล้มเหลว ถ้าเปิดใช้)
```

### track ทั้งคลิป → ออกเป็น JSON/CSV (`data/output_results/`)

| ไฟล์ | 1 บรรทัด = | ฟิลด์หลัก |
|---|---|---|
| `events.jsonl` | รถ 1 คันที่ข้ามเส้น | `trackId`, `type`, `direction` (in/out), `confidence` |
| `counts.csv` | รถ 1 คันที่นับได้ | `frame`, `trackId`, `type`, `zone`, `direction` |
| `anomalies.csv` | รถ 1 คันที่ถูกปฏิเสธ | + `reason` (wrong_direction / outside_polygon / already_counted / no_type_votes) |

### 4 ชนิด

COCO id → ชนิด: `2=car`, `3=motorcycle`, `5=bus`, `7=truck` — ส่งตรงตามชนิด ไม่ map
`bus`→`truck` (ยังไม่ส่งเข้า `data-contract.md` รอบนี้ จึงไม่ติดข้อจำกัดของ contract)

---

## 3. โครงไฟล์จริง

```
data/{input_videos, output_results, weights}/   ← วิดีโอ / ผลลัพธ์ / ไฟล์โมเดล
src/
  main.py       อ่านไฟล์ config + ลูปวิดีโอ + เขียนไฟล์ + สรุป                [cv2]
  detector.py   ครอบ YOLO.track() + ByteTrack → list[Detection]              [ultralytics]
  counter.py    geometry + VehicleCounter (แกนการนับ)                        [บริสุทธิ์]
  config.py     โหลดไฟล์ config + auto_zones + validation                   [บริสุทธิ์]
  constants.py  ค่าคงที่ทั้งหมด (COCO map, ทิศ, เหตุผล, สี)                    [บริสุทธิ์]
  emitter.py    spawn event → events.jsonl                                   [บริสุทธิ์]
  poster.py     POST spawn event → backend/api/ingest (opt-in, fail-safe)     [httpx]
  overlay.py    วาดกล่อง/โซน/เส้น/HUD                                        [cv2]
  calibrate.py  เครื่องมือคลิกหาพิกัด polygon/line จากเฟรมจริง → print YAML     [cv2]
tests/          test_counter.py, test_config.py, test_emitter.py, test_detector.py, test_poster.py
configs/*.yaml  ตั้งค่าทั้งหมดต่อมุมกล้อง (path วิดีโอ, โมเดล, conf, imgsz, โซน, เกณฑ์)
```

`counter` / `emitter` / `config` / `constants` **ไม่ import cv2/torch/ultralytics โดยตั้งใจ**
→ บั๊กการนับกลายเป็น unit test ที่รันเสร็จในเสี้ยววินาที แทนการเปิดวิดีโอดูใหม่ทุกครั้ง
(บทเรียนจากโค้ดชุดก่อนหน้า — พิสูจน์แล้ว: 53 tests รันเสร็จใน ~0.1 วินาที)

---

## 4. Roadmap → ส่งข้อมูลแบบ real-time

1. ✅ **Prototype (offline, ไม่มี lane/speed)** — mp4 → JSON ทั้งคลิป (`events.jsonl`)
2. ⏳ **เพิ่ม lane + speed จริง** — งานแยกในอนาคต (ดู §5 ว่าทำไมยังไม่ทำตอนนี้)
3. ✅ **Live bridge** (2026-08-12) — `poster.py` ส่ง spawn event เดียวกับที่เขียนลง
   `events.jsonl` เข้า `backend/api/ingest` แบบ real-time (ทีละ event ตอนข้ามเส้น) เปิดด้วย
   `send_to_backend: true` ใน ไฟล์ config (ปิดเป็นค่าเริ่มต้น) ทดสอบกับ backend ตัวจริงแล้ว —
   spawn-event schema ตรงกับ `validateSpawnEvent()` ของ backend 100% ไม่ต้องแปลง field ใด ๆ
   backend ล่ม/ปฏิเสธไม่ทำให้การนับหยุด (log แล้วนับต่อ) ← *อยู่ตรงนี้*
4. ⏳ **กำหนดโซนเอง + วัดความแม่นยำ** — ✅ เครื่องมือคลิก (`calibrate.py`) มีแล้ว เหลือ: นับมือเทียบ
5. ⏳ **MVP Main** — เปลี่ยนแหล่งเป็น RTSP + หา position/speed จริง (homography หรือวิธีอื่น)

---

## 5. ทำไมตัด `lane` และ `speed` ออก (2026-08-09)

ทั้งสองเป็นค่าที่ **วัดจากภาพจริงไม่ได้** ในเวอร์ชันนี้ (ไม่มี homography/พิกัดโลก):
- `speed` เดิมเป็นค่าคงที่ตามชนิดรถ ไม่ใช่ของจริง
- `lane` เดิมคำนวณจากตำแหน่งข้ามเส้นนับ ซึ่งพลาดสูงและยังไม่ได้ตรวจความแม่นยำ

ตัดสินใจ: **ทำการนับ+แยกชนิด+ทิศทางให้แม่นก่อน** แล้วค่อยกลับมาเพิ่ม lane/speed เป็นงานแยก
— ไม่ใส่ค่าที่ยังไม่น่าเชื่อถือปนไปกับของที่วัดได้จริง

ผลตามมา: ของเดิม (`road.py`/`poster.py`/`replay.py`) ที่จำลองตำแหน่งจาก lane+speed
เพื่อส่งเข้า backend ถูกลบไปด้วย เพราะไม่มี lane/speed ให้คำนวณอีกต่อไป ต้องออกแบบสะพาน
ไปหา backend ใหม่ตอนทำ Roadmap ขั้น 3 — **ทำแล้ว**: `poster.py` ตัวใหม่ (2026-08-12) ส่ง
spawn event ตรง ๆ ไม่ผ่านการจำลองตำแหน่งแบบเดิม เพราะ backend รับ spawn-event schema
(ไม่มี position/speed) ได้อยู่แล้ว ไม่ต้องรอมี lane/speed จริงก่อนถึงจะเชื่อมได้

---

## 6. รันยังไง

```bash
cd ai-worker
# แก้ path วิดีโอในไฟล์ config ที่จะใช้ก่อน แล้วรัน:
python -m src.main                      # ใช้ configs/event-2.yaml
python -m src.main --config other.yaml  # ใช้ config อื่น (ตัวเลือก)
```

ส่งเข้า backend ด้วย: ตั้ง `send_to_backend: true` ใน ไฟล์ config แล้วรัน backend ไว้ก่อน
(`cd backend && npm run dev`) — ปิดเป็นค่าเริ่มต้น เปิดค้างไว้ก็ยังเขียน `events.jsonl` ปกติ

เทส: `python -m pytest` · lint: `python -m ruff check .` · format: `python -m black --check .`

รายละเอียดการติดตั้ง/ตั้งค่า/รูปแบบผลลัพธ์: [`README.md`](README.md)

---

## 7. Standards

- Python 3.11, type hints ครบทุกฟังก์ชัน
- format `black` (line-length 100, ตั้งใน `pyproject.toml`), lint `ruff check .` — รันก่อน commit ทุกครั้ง
- ไม่มี global state — ส่ง config ผ่าน argument
- ค่า tunable อยู่ใน ไฟล์ config, ค่า invariant อยู่ใน `constants.py` — ห้าม hardcode ซ้ำ

---

## 8. ⚠️ จุดที่ยังค้าง

- **ไม่มี lane/speed** — ตั้งใจตัดออก จะกลับมาเพิ่มเป็นงานแยก (§5)
- **เชื่อมกับ backend แล้ว (§4 ขั้น 3) แต่ Unity ยังไม่รองรับ** — Unity ยังไม่มี handler รับ
  Socket.io event `"spawn"` และยังไม่มีโมเดล/prefab สำหรับ `type: "bus"`
- **ยังไม่ได้นับมือเทียบวัดความแม่นยำ** — `calibrate.py` มีแล้ว (ขั้นตอน: `python -m src.calibrate`
  → คลิก polygon+line ทีละ zone → ก็อป YAML ที่ print ออกมาใส่ไฟล์ใน `configs/`)
- **`architecture.md` §2** ยังเขียน "homography" อยู่ — ต้อง reconcile กับ pivot ภายหลัง
