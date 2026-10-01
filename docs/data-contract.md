# Data Contract — Smart Flow

> **⚠️ CRITICAL FILE — Do not modify without team agreement.**
> This schema is shared by AI Worker, Backend, and Unity.
> A breaking change here breaks all 3 modules simultaneously.

> Last reviewed: 2026-09-02
> Schema version: `1.5.0`

---

## 1. Overview

This file defines the JSON structures used for all communication between:

- `AI Worker → Backend` (HTTP POST)
- `Mock Server → Backend` (HTTP POST)
- `Backend → Unity` (WebSocket emit — two channels, see below)

The project has **two schemas**, one per project phase — see `../backend/CLAUDE.md`
for the full phase breakdown:

- **§2 Frame schema (MVP)** — full payload with `vehicles[]`, `position`, `speed`.
  This was the original schema and remains canonical for MVP.
- **§2b Spawn-event schema (Prototype, current)** — one event per vehicle crossing
  the camera line, no position/speed. This is what AI Worker emits today (see
  `ai-worker/data/output_results/events.jsonl`).

- **§2d Traffic-state schema (Prototype, current)** — สรุปสภาพจราจรต่อช่วงเวลา
  (occupancy + อัตราการไหล + คำตัดสิน) ส่งคู่ขนานไปกับ spawn-event คนละช่องทาง

All producers/consumers use **identical payload format** on the `spawn` WebSocket
channel — Backend must not transform that payload before forwarding it. Backend
also broadcasts a second, Unity-specific channel (`spawn_vehicle`) that
intentionally wraps and trims the payload — a documented, narrowly-scoped exception
to the "no transform" rule. See §2c.

### ช่องทางทั้งหมด (Prototype)

| POST endpoint | WebSocket emit | ความถี่ | payload |
|---|---|---|---|
| `/api/ingest` | `spawn` (ดิบ) + `spawn_vehicle` (ห่อ+ตัด) | ต่อรถ 1 คัน | §2b / §2c |
| `/api/traffic-state` | `traffic_state` | ต่อช่วงเวลา (~10 วิ) | §2d |

---

## 2. Canonical Schema (MVP — Frame)

```json
{
  "timestamp": "2026-06-12T08:15:55.000Z",
  "cameraId":  "cam-chalongkrung-01",
  "frameCount": 1450,
  "vehicles": [
    {
      "trackId":  "car-01",
      "type":     "car",
      "speed":    45.5,
      "position": {
        "x":  12.5,
        "y":  0.0,
        "z": -45.2
      }
    }
  ]
}
```

---

## 3. Field Reference

### Root fields

| Field | Type | Required | Description |
|---|---|---|---|
| `timestamp` | `string` (ISO 8601) | ✅ | UTC time when frame was captured |
| `cameraId` | `string` | ✅ | Unique camera identifier |
| `frameCount` | `integer` | ✅ | Monotonically increasing frame number (resets on restart) |
| `vehicles` | `array` | ✅ | List of detected vehicles. May be empty `[]` if no vehicles detected |

### Vehicle object

| Field | Type | Required | Constraints |
|---|---|---|---|
| `trackId` | `string` | ✅ | Stable across frames for the same vehicle. Format: `"car-01"`, `"truck-03"` |
| `type` | `string` | ✅ | Enum: `"car"` \| `"truck"` \| `"motorcycle"` \| `"bus"` |
| `speed` | `number` | ✅ | Speed in km/h. Range: `0.0` – `200.0` |
| `position.x` | `number` | ✅ | World space X coordinate (meters). Must be finite |
| `position.y` | `number` | ✅ | Always `0.0` for MVP (ground plane) |
| `position.z` | `number` | ✅ | World space Z coordinate (meters). Must be finite |

---

## 2b. Prototype Schema (Spawn-event) — Current

Used while position/speed tracking (homography) is unreliable — see
`docs/project-status.md` (2026-07-21 entry) for why the pipeline pivoted here.
One event per vehicle, fired when it crosses the camera's counting line.

### Example

```json
{
  "schema": "spawn-event/0.2-draft",
  "timestamp": "2026-08-10T15:42:47.671Z",
  "cameraId": "cam-chalongkrung-01",
  "videoTimeSec": 2.398891,
  "frameCount": 72,
  "trackId": "car-0025",
  "type": "car",
  "direction": "out",
  "confidence": 0.757
}
```

### Field Reference

| Field | Type | Required | Description |
|---|---|---|---|
| `schema` | `string` | ✅ | Schema tag, e.g. `"spawn-event/0.2-draft"` |
| `timestamp` | `string` (ISO 8601) | ✅ | UTC time the event was emitted |
| `cameraId` | `string` | ✅ | Unique camera identifier |
| `videoTimeSec` | `number` | — | Seconds into the source video (upload-based detection) |
| `frameCount` | `integer` | — | Video frame index at detection time |
| `trackId` | `string` | ✅ | Tracker ID of the vehicle, e.g. `"car-0025"` |
| `type` | `string` | ✅ | Enum: `"car"` \| `"truck"` \| `"motorcycle"` \| `"bus"` |
| `direction` | `string` | ✅ | Enum: `"in"` \| `"out"` — direction of travel relative to camera |
| `confidence` | `number` | ✅ | Detection confidence, range `0.0` – `1.0` |

No `position` or `speed` fields exist in this schema — Prototype only counts
vehicles by `type` and `direction`.

---

## 2c. Backend → Unity Broadcast (`spawn_vehicle`) — Unity-specific envelope

Every valid spawn-event ingested triggers **two** WebSocket broadcasts:

- `emit("spawn", event)` — the exact §2b payload, byte-for-byte unmodified. Used by
  internal tooling (the backend's dev dashboard).
- `emit("spawn_vehicle", envelope)` — a wrapped, trimmed view built specifically
  for Unity's consumption.

### Example

```json
{
  "event": "spawn_vehicle",
  "data": {
    "trackId": "car-0025",
    "type": "car",
    "direction": "out",
    "cameraId": "cam-chalongkrung-01",
    "timestamp": "2026-08-10T15:42:47.671Z"
  }
}
```

### Field Reference

| Field | Type | Description |
|---|---|---|
| `event` | `string` | Always the literal `"spawn_vehicle"` |
| `data` | `object` | Trimmed vehicle fields — see below |
| `data.trackId` | `string` | Tracker ID of the vehicle |
| `data.type` | `string` | Enum: `"car"` \| `"truck"` \| `"motorcycle"` \| `"bus"` |
| `data.direction` | `string` | Enum: `"in"` \| `"out"` |
| `data.cameraId` | `string` | Unique camera identifier |
| `data.timestamp` | `string` (ISO 8601) | UTC time the event was emitted |

### Fields dropped from §2b, and why

- `schema` — an AI Worker/backend versioning tag, not meaningful to Unity's
  spawning/rendering logic.
- `videoTimeSec` / `frameCount` — meaningful only inside the AI Worker's own
  source-video processing (offset into the analyzed video file); no real-world or
  simulation-time meaning for Unity.
- `confidence` — a detection-quality signal already acted on server-side
  (validation, counting); Unity doesn't need it to spawn or animate a vehicle.

---

## 2d. Traffic State Schema (`traffic-state/0.1-draft`) — Prototype

สรุปสภาพจราจรต่อช่วงเวลา (ค่าเริ่มต้น 10 วินาที) — **คนละสายกับ spawn-event**
spawn-event = รถ 1 คัน ส่วน traffic-state = สภาพรวมของถนนช่วงนั้น

### ทำไมต้องมี
เส้นนับวัดได้แค่ **Flow** ซึ่งตามความสัมพันธ์ `Flow = Density × Speed` ทำให้
**"รถติดสนิท" (Speed=0) กับ "ถนนว่าง" (Density=0) ได้ Flow = 0 เท่ากัน แยกไม่ออก**
จึงต้องวัด **Density (occupancy)** เพิ่ม = นับรถที่อยู่ในโซนโดยไม่สนว่าข้ามเส้นหรือยัง

### ทำไมแยกอัตราการไหลของมอเตอร์ไซค์ออกมา (ห้ามรวมกลับ)
`Flow = Density × Speed` สมมติว่ารถทุกคันเคลื่อนที่ไปพร้อมกัน ซึ่งไม่จริงในไทย —
**มอเตอร์ไซค์มุดผ่านช่องว่างระหว่างรถที่จอดติดได้** ถ้ารวมเข้าไปในตัวเลขเดียว
มอเตอร์ไซค์จะกลบสัญญาณรถติดจนตรวจไม่เจอ `standstill` เลย

พิสูจน์กับคลิปจริง (2026-09-02): ช่วงที่รถยนต์ข้ามเส้น **0 คัน** (หยุดสนิท) มีมอเตอร์ไซค์
ข้าม 4 คัน → รวมกันได้ 24 คัน/นาที → ระบบตัดสินผิดเป็น `high_density`

จึงแยกเป็น 2 field: `vehicleFlowRate` (car+truck+bus) **ใช้ตัดสิน** และ
`motorcycleFlowRate` ส่งไปให้ Unity ใช้ต่อได้ แต่**ไม่มีผลต่อคำตัดสิน**

### Example
```json
{
  "schema": "traffic-state/0.1-draft",
  "timestamp": "2026-09-01T09:15:55.123Z",
  "cameraId": "cam-chalongkrung-01",
  "windowStartSec": 20.0,
  "windowEndSec": 30.0,
  "zones": {
    "in":  { "occupancy": 2.83, "vehicleFlowRate": 30.0, "motorcycleFlowRate": 12.0,
             "trafficState": "normal" },
    "out": { "occupancy": 9.50, "vehicleFlowRate": 0.6,  "motorcycleFlowRate": 24.0,
             "trafficState": "standstill" }
  },
  "trafficState": "standstill"
}
```

### ทำไมต้องมีคำตัดสินรายโซน (อย่ายุบเหลือค่าเดียว)

ถนน 2 ฝั่ง**ติดไม่พร้อมกัน** ขาเข้าอาจโล่งสนิทขณะขาออกติดแน่น การมี `trafficState`
ตัวเดียวระดับบนสุด (= โซนที่แย่ที่สุด) จะทำให้ Unity วาดถนนทั้งเส้นเป็นรถติด
ทั้งที่ฝั่งหนึ่งวิ่งได้ปกติ

วัดกับคลิปจริง `event-2` (2026-09-24): **5 จาก 10 หน้าต่าง (50%) สองฝั่งอยู่คนละสถานะ**
เช่นช่วง 120–140s ขาเข้า occupancy = 0.73 (`normal`) แต่ขาออก occupancy = 4.21 กับ
flow = 0 (`standstill`) — ค่ารวมบอก `standstill` ทั้งเส้น ข้อมูลของขาเข้าหายไปทั้งหมด

`trafficState` ระดับบนสุด**ยังอยู่** ใช้เป็นพาดหัว/สรุปภาพรวม ส่วน `zones.*.trafficState`
ใช้เมื่อต้องรู้ว่าฝั่งไหนมีปัญหา — **ใช้คู่กัน ไม่ใช่แทนกัน**

### Field Reference

| Field | Type | Required | Description |
|---|---|---|---|
| `schema` | `string` | ✅ | `"traffic-state/0.1-draft"` |
| `timestamp` | `string` (ISO 8601) | ✅ | UTC time the window was emitted |
| `cameraId` | `string` | ✅ | Unique camera identifier |
| `windowStartSec` | `number` | ✅ | วินาทีเริ่มต้นของช่วง (นับจากต้นคลิป) |
| `windowEndSec` | `number` | ✅ | วินาทีสิ้นสุด — ต้องมากกว่า `windowStartSec` |
| `zones` | `object` | ✅ | key = ชื่อโซน (`in`/`out`) อย่างน้อย 1 โซน — ถนนทางเดียวมีโซนเดียวได้ |
| `zones.*.occupancy` | `number` | ✅ | จำนวนรถในโซนเฉลี่ยต่อเฟรม = **ความหนาแน่น** (≥ 0) |
| `zones.*.vehicleFlowRate` | `number` | ✅ | `car`+`truck`+`bus` ต่อนาที ที่ข้ามเส้นนับ = **อัตราการไหล** (≥ 0) — ค่าเดียวที่ใช้ตัดสิน |
| `zones.*.motorcycleFlowRate` | `number` | ❌ | มอเตอร์ไซค์ต่อนาที (≥ 0) — ข้อมูลประกอบ **ไม่ใช้ตัดสิน** ถ้าไม่ส่งมาให้ถือเป็น `0` |
| `zones.*.trafficState` | `string` | ❌ | คำตัดสินของ**ฝั่งถนนนี้โดยเฉพาะ** — enum ชุดเดียวกับระดับบนสุด ถ้าไม่ส่งมาให้ใช้ `trafficState` ระดับบนแทน (worker ก่อน 1.5.0) |
| `trafficState` | `string` | ✅ | Enum: `"normal"` \| `"high_density"` \| `"slow_moving"` \| `"standstill"` |

### ตรรกะที่ AI Worker ใช้ตัดสิน `trafficState`

"ขยับ" ตัดสินจาก `vehicleFlowRate` เท่านั้น — `motorcycleFlowRate` ไม่มีส่วนร่วม

ตารางนี้ใช้ตัดสิน **ทีละโซน** ได้ `zones.*.trafficState` ส่วน `trafficState` ระดับบนสุด
คือโซนที่แย่ที่สุด (ความรุนแรง `normal` < `high_density` < `slow_moving` < `standstill`)

| | รถขยับได้ดี | รถขยับช้า | รถแทบไม่ขยับ |
|---|---|---|---|
| **occupancy ต่ำ** | `normal` | — | `normal` (ถนนว่าง) |
| **occupancy สูง** | `high_density` | `slow_moving` | `standstill` |

เกณฑ์ตัวเลขปรับได้ใน `ai-worker/config.yaml` → `traffic_state.thresholds`
**ค่าที่ได้ขึ้นกับขนาด `occupancyPolygon` ที่วาด** จึงต้องจูนใหม่ทุกครั้งที่เปลี่ยนมุมกล้อง

Backend broadcast ต่อด้วย `emit("traffic_state", payload)` **โดยไม่แปลง payload**

---

## 4. Validation Rules

### Frame schema (MVP)

Backend **must reject** (HTTP 400) any payload that violates these rules:

```
REJECT if: timestamp is missing or not a valid ISO 8601 string
REJECT if: cameraId is missing or empty string
REJECT if: vehicles is not an array
REJECT if: any vehicle.position.x or .z is NaN or Infinity
REJECT if: any vehicle.position.y is not 0.0
REJECT if: any vehicle.type is not one of ["car", "truck", "motorcycle", "bus"]
REJECT if: any vehicle.speed < 0 or > 200
REJECT if: vehicles.length > 120
```

### Spawn-event schema (Prototype)

Backend **must reject** (HTTP 400) any payload that violates these rules:

```
REJECT if: timestamp is missing or not a valid ISO 8601 string
REJECT if: cameraId is missing or empty string
REJECT if: trackId is missing or empty string
REJECT if: type is not one of ["car", "truck", "motorcycle", "bus"]
REJECT if: direction is not one of ["in", "out"]
REJECT if: confidence is not a number in range [0.0, 1.0]
REJECT if: videoTimeSec or frameCount is present but negative or not finite
```

### Traffic-state schema (Prototype)

Backend **must reject** (HTTP 400) any payload that violates these rules:

```
REJECT if: timestamp is missing or not a valid ISO 8601 string
REJECT if: cameraId is missing or empty string
REJECT if: windowStartSec or windowEndSec is negative or not finite
REJECT if: windowEndSec <= windowStartSec
REJECT if: trafficState is not one of ["normal", "high_density", "slow_moving", "standstill"]
REJECT if: zones is missing, not an object, or empty
REJECT if: any zone.occupancy or zone.vehicleFlowRate is negative or not finite
REJECT if: any zone.motorcycleFlowRate is present but negative or not finite
REJECT if: any zone.trafficState is present but not one of the 4 traffic states
```

Payload passes validation silently. Failed validation logs a warning with
the rejection reason and the raw payload (truncated to 500 chars).

---

## 5. Coordinate System (MVP — Frame schema only)

```
       Z+
       │
       │    (road ahead)
       │
───────┼──────── X+
       │
       │
    Camera
```

- Origin `(0, 0, 0)` = calibration reference point on Chalong Krung Road
- **X axis**: horizontal across the road (positive = right)
- **Y axis**: vertical (always 0.0 for ground-level vehicles in MVP)
- **Z axis**: along the road (positive = away from camera)
- Units: **meters**

---

## 6. Known `cameraId` Values

| cameraId | Location | Status |
|---|---|---|
| `cam-chalongkrung-01` | Chalong Krung Rd — railway crossing viewpoint | Active (MVP) |

---

## 7. Example Payloads

### Normal traffic (3 vehicles)
```json
{
  "timestamp": "2026-06-12T08:15:55.000Z",
  "cameraId": "cam-chalongkrung-01",
  "frameCount": 1450,
  "vehicles": [
    { "trackId": "car-01", "type": "car",        "speed": 45.5, "position": { "x":  12.5, "y": 0.0, "z": -45.2 } },
    { "trackId": "car-02", "type": "car",        "speed": 38.0, "position": { "x":  -3.2, "y": 0.0, "z":  12.8 } },
    { "trackId": "car-03", "type": "motorcycle", "speed": 52.1, "position": { "x":   8.0, "y": 0.0, "z":  30.0 } }
  ]
}
```

### Bus type (v1.1.0)
```json
{
  "timestamp": "2026-08-10T09:15:55.000Z",
  "cameraId": "cam-chalongkrung-01",
  "frameCount": 1271,
  "vehicles": [
    { "trackId": "bus-0042", "type": "bus", "speed": 34.2, "position": { "x": 5.1, "y": 0.0, "z": 60.4 } }
  ]
}
```

### Empty frame (no vehicles detected)
```json
{
  "timestamp": "2026-06-12T08:16:01.000Z",
  "cameraId": "cam-chalongkrung-01",
  "frameCount": 1451,
  "vehicles": []
}
```

### Invalid payload (backend will reject with HTTP 400)
```json
{
  "timestamp": "2026-06-12T08:16:02.000Z",
  "cameraId": "cam-chalongkrung-01",
  "frameCount": 1452,
  "vehicles": [
    { "trackId": "car-01", "type": "car", "speed": 40.0, "position": { "x": null, "y": 0.0, "z": NaN } }
  ]
}
```

---

## 8. Versioning Policy

- This schema uses **Semantic Versioning**: `MAJOR.MINOR.PATCH`
- **MAJOR** bump = breaking change (field removed, type changed, rename) → requires update in all 3 modules
- **MINOR** bump = new optional field added → backwards compatible
- **PATCH** bump = description / comment clarification only

Current version: `1.5.0`

---

## 9. Change Log

| Version | Date | Author | Change |
|---|---|---|---|
| 1.0.0 | 2026-06-12 | initial | Initial schema based on project proposal |
| 1.1.0 | 2026-08-12 | backend redesign | Added §2b Prototype spawn-event schema; added `"bus"` to the `type` enum in both schemas |
| 1.2.0 | 2026-08-12 | unity envelope | Added §2c `spawn_vehicle` broadcast — wrapped + trimmed Unity-specific view alongside the unchanged `spawn` channel |
| 1.3.0 | 2026-09-02 | traffic state | Added §2d `traffic-state` schema — per-window occupancy + flowRate and a `trafficState` verdict, broadcast on the new `traffic_state` channel |
| 1.4.0 | 2026-09-02 | motorcycle flow | **Breaking within §2d:** `zones.*.flowRate` แยกเป็น `vehicleFlowRate` (บังคับ, ใช้ตัดสิน) + `motorcycleFlowRate` (ไม่บังคับ) เพราะมอเตอร์ไซค์มุดผ่านรถติดได้ ทำให้กลบสัญญาณ `standstill` — นับเป็น MINOR เพราะ §2d ยังเป็น `0.1-draft` และมีผู้ใช้แค่ ai-worker/backend ซึ่งแก้พร้อมกันในคอมมิตเดียว |

| 1.5.0 | 2026-09-24 | per-zone verdict | เพิ่ม `zones.*.trafficState` — คำตัดสินแยกรายฝั่งถนน (field ใหม่ ไม่บังคับ = ไม่ breaking) `trafficState` ระดับบนสุดยังอยู่เหมือนเดิมในฐานะโซนที่แย่ที่สุด เหตุผล: วัดกับ `event-2` แล้วพบว่า **50% ของหน้าต่างสองฝั่งอยู่คนละสถานะ** เช่นขาเข้าโล่งสนิทขณะขาออกติดแน่น ค่ารวมค่าเดียวจึงทิ้งข้อมูลไปครึ่งหนึ่งและทำให้ Unity วาดถนนทั้งเส้นเป็นรถติดผิด ๆ |

> Before modifying this schema, confirm with all module owners.
> After modifying, bump the version, update the changelog above,
> and update affected module code before merging.