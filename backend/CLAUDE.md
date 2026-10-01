# Backend — CLAUDE.md

> Read `../CLAUDE.md` and `../docs/architecture.md` before this file.
> This file covers only Backend-specific context.

---

## What This Module Does

Backend is the **validate → broadcast relay** between AI Worker (or Mock Server)
and Unity. What exactly it validates/broadcasts differs by phase — see below.

1. Receives a payload via `POST /api/ingest` from AI Worker or Mock Server
2. Validates the payload against `docs/data-contract.md` — rejects invalid with HTTP 400
3. Broadcasts the valid payload to all Unity clients via Socket.io — event name
   depends on phase (`spawn` in Prototype, `frame` in MVP)
4. Exposes `GET /health` for uptime monitoring

**Never transform the payload on the `spawn`/`frame` channel** — emit exactly what
was received. The one documented exception (Prototype only): `spawn_vehicle`, a
second broadcast alongside `spawn` that wraps and trims the payload specifically
for Unity — see `docs/data-contract.md` §2c.

---

## Phases

The project runs in two phases (see `../CLAUDE.md` for the reasoning behind the
pivot away from homography/position tracking). **Build Prototype first.** MVP
extends it — it does not replace it.

| Concern | **Prototype** (current) | **MVP** (later) |
|---|---|---|
| Ingest schema | `spawn-event` — one vehicle per POST | `frame` — `vehicles[]` with position + speed |
| Payload has position/speed | ❌ no | ✅ yes |
| WebSocket emit | `emit("spawn", event)` + `emit("spawn_vehicle", envelope)` + `emit("traffic_state", payload)` | `emit("frame", frame)` |
| Counting | in-memory counters + `GET /api/stats` | counters optional, carried over |
| Database | ❌ none — no TimescaleDB, no `db/` module | ✅ async TimescaleDB log, gated by `ENABLE_DB_LOGGING` (default `false`) |
| Vehicle types | `car`, `truck`, `motorcycle`, `bus` | `car`, `truck`, `motorcycle`, `bus` |

Why Prototype has no DB: the current AI Worker output is a **count/spawn event**
(vehicle crossed a line → emit type + direction), not a positioned frame — there's
nothing time-series/spatial yet worth persisting. Adding TimescaleDB now would be
building storage for data that doesn't exist. See `docs/project-status.md`
(2026-07-21 entry) for why the pipeline moved away from homography positions.

---

## Prototype

### Endpoints

| Method + Path | Purpose |
|---|---|
| `POST /api/ingest` | Receive one spawn-event, validate, update counters, `emit("spawn", event)` + `emit("spawn_vehicle", envelope)` |
| `POST /api/traffic-state` | Receive one traffic-state window, validate, `emit("traffic_state", payload)` — ไม่แปลง payload |
| `GET /api/stats` | Return current in-memory counters |
| `POST /api/stats/reset` | Zero all counters (demo convenience) |
| `GET /health` | Uptime check |
| `GET /` | Serve live dev dashboard (`backend/src/view/` — `index.html` + `styles.css` + `app.js`) **3 หน้า สลับด้วย URL hash**: `#overview` (สถานะปัจจุบัน + timeline + สรุป `/api/stats` + การ์ดต่อโซนพร้อม sparkline + feed ของ `spawn`) · `#state` (ตารางทุกหน้าต่างที่ได้รับ พร้อม occ/veh/mc และคำตัดสิน + สรุป % ต่อสถานะ) · `#json` (payload ดิบทั้ง 2 ช่อง กรองตามช่องได้). Dev-only, no auth, **ไม่พึ่ง CDN/ฟอนต์ภายนอก** (เซิร์ฟเวอร์ on-premise อาจไม่มีเน็ต) |

### Spawn-event schema (from AI Worker output)

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

No `position`, no `speed` — the Prototype only tracks that a vehicle of a given
`type` crossed the camera line in a given `direction`.

### `spawn_vehicle` — Unity-specific broadcast

Alongside `emit("spawn", event)` (unmodified), backend also emits
`emit("spawn_vehicle", envelope)` — a wrapped, trimmed view built via the pure
function `toUnitySpawnPayload()` in `src/sockets/unityPayload.ts`:

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

Drops `schema`, `videoTimeSec`, `frameCount`, `confidence` — see
`docs/data-contract.md` §2c for the full field reference and rationale. The
backend's dev dashboard (`GET /`) still listens to the unmodified `spawn` channel,
not `spawn_vehicle` — it is unaffected by this.

### `traffic_state` — สภาพจราจรต่อช่วงเวลา

คนละสายกับ spawn-event: spawn-event = รถ 1 คัน, traffic-state = สภาพถนนช่วงนั้น
(~1 ครั้งต่อ 10 วินาที) AI Worker เป็นคนวัดและ**ตัดสิน**มาแล้ว backend แค่ validate
แล้ว broadcast ต่อโดยไม่แปลง

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

`vehicleFlowRate` (car+truck+bus) คือค่าเดียวที่ใช้ตัดสิน — `motorcycleFlowRate` แยกออกมา
เพราะมอเตอร์ไซค์มุดผ่านรถที่จอดติดได้ ถ้ารวมกันจะกลบสัญญาณ `standstill`
(ดู `docs/data-contract.md` §2d) เป็น field ไม่บังคับ ไม่ส่งมา = 0

`zones.*.trafficState` = คำตัดสินแยกรายฝั่งถนน (ไม่บังคับ ถ้าไม่ส่งมาให้ใช้ค่ารวมแทน) —
ถนน 2 ฝั่งติดไม่พร้อมกัน วัดจริงแล้ว 50% ของหน้าต่างสองฝั่งคนละสถานะ ส่วน `trafficState`
ระดับบนสุดคือโซนที่แย่ที่สุด ใช้เป็นพาดหัว — **ใช้คู่กัน ไม่ใช่แทนกัน**

`trafficState` ∈ `normal` | `high_density` | `slow_moving` | `standstill`
(ต้องตรงกับ `TRAFFIC_STATES` ใน `src/constants.ts` และ `STATE_*` ใน
`ai-worker/src/constants.py`) — validation rules ดู `docs/data-contract.md` §4

### Validation rules

```
REJECT if: timestamp missing or not valid ISO 8601
REJECT if: cameraId missing or empty string
REJECT if: trackId missing or empty string
REJECT if: type not in ["car", "truck", "motorcycle", "bus"]
REJECT if: direction not in ["in", "out"]
REJECT if: confidence is not a number in range [0.0, 1.0]
REJECT if: videoTimeSec or frameCount present but negative or not finite
```

Traffic-state (`POST /api/traffic-state`) — กฎเต็มดู `docs/data-contract.md` §4:

```
REJECT if: any zone.occupancy or zone.vehicleFlowRate is negative or not finite
REJECT if: any zone.motorcycleFlowRate is present but negative or not finite
REJECT if: any zone.trafficState is present but not one of the 4 traffic states
```

On rejection: HTTP 400 + reason string. Log warning with reason + raw payload
(truncated to 500 chars).

### Counters — `GET /api/stats` response shape

```json
{
  "cameraId": "cam-chalongkrung-01",
  "since": "2026-08-10T15:42:00.000Z",
  "totals": { "in": 20, "out": 30, "all": 50 },
  "byType": {
    "car":        { "in": 10, "out": 20 },
    "truck":      { "in": 1,  "out": 2 },
    "motorcycle": { "in": 8,  "out": 6 },
    "bus":        { "in": 1,  "out": 2 }
  }
}
```

Counters live **in memory only** — they reset when the server restarts, and
`POST /api/stats/reset` clears them on demand. Counting must never block or delay
the `emit("spawn", ...)` broadcast.

---

## MVP

Extends Prototype once vehicle positions are trustworthy again (see the
homography accuracy blocker in `docs/project-status.md`).

### Frame schema

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
      "position": { "x": 12.5, "y": 0.0, "z": -45.2 }
    }
  ]
}
```

### Validation rules

```
REJECT if: timestamp missing or not valid ISO 8601
REJECT if: cameraId missing or empty string
REJECT if: vehicles is not an array
REJECT if: any position.x or .z is NaN or Infinity
REJECT if: any position.y is not 0.0
REJECT if: any vehicle.type not in ["car", "truck", "motorcycle", "bus"]
REJECT if: any vehicle.speed < 0 or > 200
REJECT if: vehicles.length > 120
```

On rejection: HTTP 400 + reason string. Log warning with reason + raw payload
(truncated to 500 chars).

Broadcasts via `emit("frame", frame)`. Asynchronously logs each frame to
TimescaleDB (non-blocking — never delays broadcast), gated by `ENABLE_DB_LOGGING`
(default `false` per `../docs/architecture.md` §5).

---

## Planned Folder Layout

```
backend/
├── CLAUDE.md
├── package.json
├── tsconfig.json
├── .env.example
└── src/
    ├── index.ts                     ← Express + Socket.io setup, server start
    ├── routes/
    │   ├── ingest.ts                ← POST /api/ingest handler (phase-aware)
    │   ├── stats.ts                 ← GET /api/stats, POST /api/stats/reset (Prototype)
    │   └── health.ts                ← GET /health handler
    ├── validation/
    │   ├── validateSpawnEvent.ts    ← Prototype schema validation (must have unit tests)
    │   └── validatePayload.ts       ← MVP frame schema validation (must have unit tests)
    ├── counters/
    │   └── vehicleCounters.ts       ← in-memory counter store (Prototype)
    ├── db/
    │   └── logger.ts                ← async TimescaleDB insert (MVP only)
    ├── view/                        ← dev dashboard (static, เสิร์ฟด้วย express.static)
    │   ├── index.html               ← markup เท่านั้น
    │   ├── styles.css               ← design tokens + layout
    │   └── app.js                   ← socket handlers, timeline, sparkline (vanilla JS)
    └── constants.ts                 ← named constants (e.g. VEHICLE_TYPES, MAX_VEHICLES)
```

---

## Environment Variables (`.env`)

```
PORT=3000

# MVP only — leave unset for Prototype
ENABLE_DB_LOGGING=false
DB_HOST=localhost
DB_PORT=5432
DB_NAME=smartflow
DB_USER=smartflow
DB_PASSWORD=...
```

---

## Standards

- TypeScript strict mode — `tsc --noEmit` must pass before committing
- Format: Prettier
- Lint: ESLint — `npm run lint`
- Unit test required for `validateSpawnEvent()` and `validatePayload()` — the most
  critical functions in this module
