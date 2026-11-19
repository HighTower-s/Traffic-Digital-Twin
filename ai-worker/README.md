# AI Worker — นับรถจากไฟล์วิดีโอ

นับรถที่ข้ามเส้น แยกชนิด (`car` / `motorcycle` / `bus` / `truck`) และแยกทิศเข้า-ออก
แล้วเขียนผลเป็น JSON/CSV — นี่คือ **prototype**: ไม่มี `lane`, ไม่มี `speed`, และ
**ไม่ส่งข้อมูลออกนอกเครื่อง** ผลลัพธ์อยู่ใน `data/output_results/` และที่พิมพ์บนจอเท่านั้น

รายละเอียดเป้าหมายระยะยาวและเหตุผลของดีไซน์ ดูที่ [`CLAUDE.md`](CLAUDE.md)

---

## ติดตั้ง

```bash
cd ai-worker
python -m venv .venv
.\.venv\Scripts\Activate.ps1      # Windows
pip install -r requirements.txt
```

การ์ดจอ NVIDIA รุ่น RTX 50-series (Blackwell) ต้องลง torch แยก:

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
```

ถ้าไม่ลงรุ่น CUDA โปรแกรมจะรันบน CPU ได้ แต่ช้ากว่าหลายเท่า และจะเตือนตอนเริ่มรัน

---

## ใช้งาน

0. `data/` ไม่ถูก track ใน git (ดู root `.gitignore`) — สร้างโฟลเดอร์เองครั้งแรก:
   `mkdir -p data/input_videos data/output_results data/weights`
1. วางไฟล์วิดีโอไว้ที่ `data/input_videos/`
2. วางไฟล์โมเดล (เช่น `yolov8s.pt`) ไว้ที่ `data/weights/` (หรือปล่อยให้ ultralytics ดาวน์โหลดอัตโนมัติ)
3. แก้ไฟล์ใน [`configs/`](configs/) ให้ `video:` ชี้ไปที่ไฟล์วิดีโอ
4. รัน:

```bash
python -m src.main                                   # ใช้ configs/event-2.yaml (ค่าเริ่มต้น)
python -m src.main --config configs/traffic-5.yaml   # ใช้มุมกล้องอื่น
```

ปุ่มระหว่างรัน: `q` ออก · `เว้นวรรค` หยุด/เล่นต่อ

ค่าตั้งได้ทั้งหมดอยู่ในไฟล์ที่ `--config` ชี้ — หนึ่งไฟล์ต่อมุมกล้อง สมบูรณ์ในตัวเอง
(path วิดีโอ/โมเดล, `imgsz`, `conf`, `tracker`, `device`, `max_frames`, `emit_preview`,
`zones`, `traffic_state`) ดูชุดที่มีทั้งหมดที่ [`configs/README.md`](configs/README.md)

---

## ⚠️ โหมดโซนอัตโนมัติกับความแม่นยำ

ถ้าไฟล์ config ตั้ง `zones: auto` โปรแกรมจะเดาโซน/เส้นนับจากขนาดเฟรมให้ **เห็นภาพเร็ว**
ไม่ใช่ให้ตัวเลขที่เชื่อได้ ปัญหาที่คาดไว้:

- เส้นนับอยู่กลางภาพ ซึ่งอาจเป็นระยะที่รถเล็กเกินกว่าจะจำแนกชนิดถูก
- polygon กินครึ่งภาพเต็ม ๆ จึงอาจรวมถนนซอย ทางเท้า หรือราวสะพานเข้ามาด้วย
- เส้นแบ่งทิศถูกสมมติว่าอยู่กลางภาพพอดี ซึ่งจริง ๆ แล้วมักเอียงและไม่อยู่ตรงกลาง

ทำให้แม่นขึ้นด้วยการกำหนด `zones` เองในไฟล์ config (ดูตัวอย่างในไฟล์ที่มีอยู่แล้วใน `configs/`):
แต่ละโซนมี `name`, `expectedDirection` (`toward`/`away`), `polygon` (จุดอย่างน้อย 3 จุด),
`line` (จุดตัดกับถนน 2 จุด)

### หาพิกัดด้วยเครื่องมือคลิก

ไม่ต้องเดาพิกัดเอง ใช้ `calibrate.py` คลิกจากเฟรมจริงของวิดีโอได้เลย:

```bash
python -m src.calibrate                                  # ใช้ video: จากไฟล์ config
python -m src.calibrate --video data/input_videos/x.mp4  # หรือระบุไฟล์เอง
python -m src.calibrate --frame 90                       # เลือกเฟรมอื่น (ค่าเริ่มต้น 60)
```

คลิกซ้าย = เพิ่มจุด · `Enter` = จบรูปปัจจุบัน (polygon → line → zone ถัดไป) · `u` = undo ·
`r` = reset รูปปัจจุบัน · `q` = เลิกทั้งหมด — จบแล้วจะ print YAML พร้อมก็อปวางใส่
ไฟล์ config ทันที (พิกัดอ้างอิงตามขนาดเฟรมจริงเสมอ ต่อให้หน้าต่างที่เห็นถูกย่อแสดงผล)

---

## ผลลัพธ์ (`data/output_results/`)

| ไฟล์ | เนื้อหา |
|---|---|
| `counts.csv` | รถที่นับได้ — `frame, videoTimeSec, trackId, type, zone, direction, x, y` |
| `anomalies.csv` | รถที่ถูกปฏิเสธ + เหตุผล (`wrong_direction`, `outside_polygon`, `already_counted`, `no_type_votes`) |
| `events.jsonl` | payload ร่างสำหรับ Unity/backend ในอนาคต บรรทัดละคัน |

`anomalies.csv` คือเครื่องมือหลักตอนตัวเลขไม่ตรงกับที่นับมือ — บอกได้ว่ารถคันไหน
ถูกตัดออกเพราะอะไร แทนที่จะต้องเดา

`videoTimeSec` คือวินาทีนับจากต้นคลิป (`frame / fps`) ไม่ใช่เวลานาฬิกา
จึงเอาไปหาตำแหน่งในวิดีโอซ้ำได้

---

## รูปแบบ spawn event (`events.jsonl`)

```json
{
  "schema": "spawn-event/0.2-draft",
  "timestamp": "2026-08-09T09:15:55.000Z",
  "cameraId": "cam-chalongkrung-01",
  "videoTimeSec": 42.366667,
  "frameCount": 1271,
  "trackId": "car-0042",
  "type": "car",
  "direction": "in",
  "confidence": 0.87
}
```

**ไม่มี `lane` และไม่มี `speed`** (ตัดออก 2026-08-09 — ทั้งคู่วัดจากภาพจริงไม่ได้ในเวอร์ชันนี้
เพิ่มกลับเป็นงานแยกทีหลัง ดูเหตุผลเต็มที่ [`CLAUDE.md` §5](CLAUDE.md))

---

## เทส

```bash
python -m pytest -v          # โมดูลบริสุทธิ์ทั้งหมด รันได้ในเสี้ยววินาที ไม่ต้องมี GPU/วิดีโอ
python -m ruff check .
python -m black --check .
```

`counter.py`, `config.py`, `emitter.py`, `constants.py` ไม่ import cv2/torch/ultralytics เลย
บั๊กการนับหรือรูปแบบ output จึงกลายเป็น unit test ที่รันเสร็จในเสี้ยววินาที แทนที่จะต้อง
เปิดวิดีโอดูใหม่ทุกครั้ง

---

## โครงสร้าง

```
ai-worker/
├── data/
│   ├── input_videos/      # .mp4 ต้นฉบับ
│   ├── output_results/    # counts.csv, anomalies.csv, events.jsonl
│   └── weights/           # ไฟล์โมเดล .pt
├── src/
│   ├── main.py            # อ่านไฟล์ config + ลูปวิดีโอ + เขียนไฟล์ + สรุป
│   ├── detector.py        # ครอบ YOLOv8 + ByteTrack -> list[Detection]
│   ├── counter.py         # geometry + VehicleCounter (แกนการนับ, บริสุทธิ์)
│   ├── config.py          # โหลดไฟล์ config + auto_zones + validation (บริสุทธิ์)
│   ├── constants.py       # ค่าคงที่ทั้งหมด (บริสุทธิ์)
│   ├── emitter.py         # spawn event -> events.jsonl (บริสุทธิ์)
│   └── overlay.py         # วาดกล่อง/โซน/เส้น/HUD
├── tests/                 # test_counter, test_config, test_emitter, test_detector
├── configs/               # ไฟล์ config ต่อมุมกล้อง (default: event-2.yaml)
└── runs/                  # ชุดข้อมูลที่วิเคราะห์แล้ว เล่นซ้ำด้วย replay --from
```

สเปกเป้าหมายระยะยาวและ Roadmap → real-time: [`CLAUDE.md`](CLAUDE.md)
