
```bash

python -m src.main --config configs/event-2.yaml --replay
python -m src.replay --config configs/event-2.yaml --fast
python -m src.calibrate --config configs/event-2.yaml --preview
```

**ไม่ใส่ `--config`** = ใช้ `configs/event-2.yaml` (ค่าเริ่มต้นในโค้ด)

> ⚠️ ชี้ `--config` ให้ตรงกันทั้ง `main` และ `replay` ไม่งั้นจะเอาเกณฑ์ผิดชุดมาตัดสินข้อมูล

---

## ชุดที่มี

| ไฟล์ | คลิป | สถานะ | หมายเหตุ |
|---|---|---|---|
| **`event-2.yaml`** | `event-2.mp4` · 1920×1080 60fps 3.4 นาที | ✅ **ใช้งานอยู่** | กล้อง KMITL · วาดโค้งตามถนนจริง · ซ้าย=`in`(away) ขวา=`out`(toward) |
| `event-2-straight.yaml` | `event-2.mp4` | ⛔ เลิกใช้ | กรอบ 4 มุมแบบเก่า เก็บไว้เทียบผล |
| `event-1.yaml` | `event-1.mp4` · 1920×1080 25fps 21 วิ | 📦 อ้างอิง | **คลิปนอก ไม่ใช่กล้อง KMITL** · ถนนทางเดียว โซนเดียว |
| `traffic-1.yaml` | `traffic-1.mp4` · 3840×2160 30fps 34 วิ | 📦 อ้างอิง | กล้อง KMITL มุมเดิม (4K) |
| `traffic-5.yaml` | `traffic-5.mp4` · 3840×2160 30fps 93 วิ | 📦 ฐาน "จราจรปกติ" | วัดได้ occ 0.20–2.26 · ทุกหน้าต่าง `normal` |

---

## ⚠️ เกณฑ์ย้ายข้ามไฟล์ไม่ได้

`occupancy` = จำนวนรถเฉลี่ยใน `occupancyPolygon` ซึ่ง **ขึ้นกับขนาดกรอบที่วาดและมุมกล้อง**
วาดกรอบใหญ่ขึ้น 2 เท่า ค่าก็ขึ้นราว 2 เท่าทั้งที่ถนนเหมือนเดิม

เทียบให้เห็นภาพ — ช่วงที่รถติดเหมือนกัน แต่คนละกล้อง:

| | occupancy ที่วัดได้ |
|---|---|
| `event-1` (คลิปนอก) | 14 – 17 |
| `event-2` (กล้อง KMITL) | 0 – 11 |

**เกณฑ์จึงเก็บไว้ในไฟล์เดียวกับโซนเสมอ** ย้ายไปไว้ที่อื่นไม่ได้

---

## ผลที่วัดได้จาก `event-2` (ชุดที่ใช้อยู่)

เกณฑ์ปัจจุบัน `busy_occupancy: 4` · `standstill_flow: 2.0` · `slow_flow: 32.0` · `window_sec: 20`

```
normal        5 windows  (50%)
slow_moving   5 windows  (50%)
high_density  0 windows            <- ยังไม่มีคลิปที่เป็นสภาพนี้
standstill    0 windows            <- ยังไม่มีคลิปที่เป็นสภาพนี้
```

### ที่มาของ `busy_occupancy: 4`

จุดที่ flow ร่วงในโซน `in` — ความหนาแน่นวิกฤตตาม *fundamental diagram of traffic flow*

```
occ 3.77 → flow 12 (4 คัน)
occ 4.19 → flow  3 (1 คัน)   ← occ เพิ่ม 0.42 แต่ flow ร่วง 4 เท่า
```

**ยังไม่ได้ยืนยันด้วยตา** — มาจากข้อมูล 2 จุดในคลิปเดียว ถ้าถ่ายคลิปเพิ่มควรวัดใหม่

---

## เพิ่มชุดใหม่ยังไง

```bash
python -m src.calibrate                 # วาดโซน -> โปรแกรม print YAML ออกมา
```

1. **ก็อปไฟล์ชุดที่ใกล้เคียงที่สุด** ตั้งชื่อใหม่ (จะได้ค่ารันครบโดยไม่ต้องพิมพ์เอง)
2. แทนที่บล็อก `zones:` ด้วย YAML ที่ `calibrate` print ออกมา แล้วแก้ `video:`
3. `python -m src.calibrate --config configs/<ชื่อ>.yaml --preview` ตรวจกรอบ
4. `python -m src.main --config configs/<ชื่อ>.yaml --replay` รันจริง

**กฎ 2 ข้อ**
- ชื่อโซนต้องเป็น `in` หรือ `out` เท่านั้น (ถูกส่งออกเป็น field `direction`)
- `expectedDirection` บอกทิศที่รถเคลื่อนที่ **ในภาพ** (`toward` = ลงล่าง, `away` = ขึ้นบน)
  ตั้งอิสระจากชื่อโซนได้ — `name: in` คู่กับ `expectedDirection: away` ถูกต้อง
