# Architecture — Smart Flow

> Last reviewed: 2026-06-12
> Update this file when: adding a module, changing tech stack, or making a significant design decision.

---

## 1. System Overview

Smart Flow is a **3-module pipeline** that converts a CCTV video stream into a
real-time 3D Digital Twin rendered in a web browser.

```
CCTV (RTSP)
    │
    ▼
┌─────────────┐     JSON payload      ┌─────────────┐     WebSocket     ┌──────────────┐
│  AI Worker  │ ──────────────────▶   │   Backend   │ ────────────────▶ │    Unity     │
│  (Python)   │   HTTP POST /ingest   │  (Node.js)  │   emit("frame")   │   (WebGL)    │
└─────────────┘                       └─────────────┘                   └──────────────┘
                                             │
                                             ▼
                                      ┌─────────────┐
                                      │ TimescaleDB │
                                      │  (log only) │
                                      └─────────────┘
```

During development, **Mock Server** replaces AI Worker entirely.
Backend cannot tell the difference — same JSON format, same endpoint.

```
Mock Server  ──────────────────▶  Backend  ──────▶  Unity
(Node.js)       HTTP POST /ingest
```

---

## 2. Module Responsibilities

### AI Worker (`/ai-worker`)
- Pull frames from RTSP stream via OpenCV
- Detect and track vehicles using YOLOv8
- Convert 2D bounding box center → 3D world coordinates (Homography)
- Validate output against data contract schema
- POST JSON payload to Backend every ~1 second

**Does NOT:** store data, manage connections, or know about Unity.

### Backend (`/backend`)
- Receive JSON payload from AI Worker (or Mock Server) via `POST /ingest`
- Validate incoming payload (schema check before any processing)
- Broadcast payload to all connected Unity clients via WebSocket (`emit("frame")`)
- Asynchronously log each frame to TimescaleDB
- Expose a simple health check endpoint `GET /health`

**Does NOT:** process images, run AI, or know about Unity's rendering logic.

### Unity Frontend (`/unity`)
- Connect to Backend WebSocket on startup
- Receive `frame` events and update vehicle positions
- Manage car models using Object Pooling (pool size: 120)
- Smooth movement between frames using `Vector3.Lerp`
- Render on WebGL build target (Chrome-compatible)

**Does NOT:** compute coordinates, store data, or call any API directly.

### Mock Server (`/mock-server`)
- Simulate AI Worker output for development and demo
- Support 3 scenarios: `normal`, `congestion`, `edge`
- POST to the same `/ingest` endpoint as the real AI Worker
- Vehicles move continuously (bounce within road boundary)

---

## 3. Data Flow (Detail)

```
1. AI Worker detects vehicles in frame N
2. For each vehicle: compute (x, y=0, z) in world space via Homography
3. Build JSON payload (see data-contract.md for schema)
4. POST to http://localhost:3000/api/ingest
5. Backend validates payload → rejects with 400 if invalid
6. Backend emits payload to all WebSocket clients
7. Backend inserts row into TimescaleDB (async, non-blocking)
8. Unity receives "frame" event
9. Unity updates car positions in pool → Lerp toward new position
10. Unity hides cars not present in latest frame
```

---

## 4. Tech Stack

| Module | Technology | Version | Notes |
|---|---|---|---|
| AI Worker | Python | 3.11 | |
| | OpenCV | 4.x | RTSP / video capture |
| | Ultralytics YOLOv8 | latest stable | Object detection + ByteTrack |
| | FastAPI + Uvicorn | latest stable | เว็บอัปโหลด + calibrate homography + สตรีม |
| | httpx | >=0.27 | POST เฟรมเข้า backend/api/ingest |
| | python-dotenv | >=1.0 | อ่านค่า config จาก .env |
| | pyyaml | >=6.0 | อ่าน config YAML ของ prototype line-counting (2026-08-09) |
| Backend | Node.js | 20 LTS | |
| | Express | 4.x | HTTP server |
| | Socket.io | 4.x | WebSocket abstraction |
| | TimescaleDB | 2.x | Via Docker |
| Frontend | Unity | 2022 LTS | WebGL build target |
| | C# | — | Unity scripting |
| Mock Server | Node.js | 20 LTS | Same runtime as backend |
| Infra | Docker Compose | — | Local + on-premise |

---

## 5. Tech Decisions (Why)

### Why TimescaleDB instead of MongoDB
Traffic logs are pure time-series data. Every query will be time-range based
(e.g. "vehicles between 08:00–09:00"). TimescaleDB is a PostgreSQL extension
optimized for exactly this pattern — range queries are significantly faster
and storage is compressed automatically. MongoDB would work but is not
optimized for this workload. Setup complexity is similar for MVP.

### Why on-premise instead of AWS (MVP)
RTSP stream from CCTV is on KMITL's internal network. Routing it to a cloud
server adds unnecessary latency and creates a security exposure. On-premise
eliminates both issues. AWS remains an option for Phase 2 if public access
or scaling is required.

### Why Mock-First development
The 3 modules have hard dependencies on each other. If AI Worker is not
ready, Backend and Unity teams cannot develop. Mock Server breaks this
dependency — all 3 modules can be developed and tested in parallel from
day 1. It also gives us a reliable demo fallback if CCTV is unavailable.

### Why Unity WebGL instead of a web-only 3D library (e.g. Three.js)
Object Pooling and Lerp interpolation in Unity are mature, well-documented
patterns for exactly this use case (100+ moving objects, position updates
every second). The team already has Unity experience. Three.js would require
reimplementing the same patterns from scratch.

### Why a web-based AI Worker (FastAPI) + video upload สำหรับ MVP
กล้อง CCTV ของ SICA มีอยู่แต่ยังไม่ได้รับอนุญาตให้เข้าถึง จึงพัฒนา/เดโมด้วย
**วิดีโออัปโหลด** แทน RTSP ไปก่อน FastAPI ให้ UI สำหรับอัปโหลด, calibrate homography
(คลิก 4 จุด), รัน YOLOv8+ByteTrack แล้วสตรีมผลตาม data-contract เข้า backend ผ่าน `httpx`
โครงนี้สลับมาใช้ RTSP จริงได้โดยเปลี่ยนแหล่งเฟรมเท่านั้น — payload และปลายทางเหมือนเดิม
สอดคล้องหลัก Mock-First: backend/Unity แยกไม่ออกว่าเฟรมมาจาก mock, วิดีโอ, หรือกล้องจริง

### Why pyyaml สำหรับ AI Worker prototype (2026-08-09)
Prototype ตัว line-counting ตั้งค่า (path วิดีโอ/โมเดล, conf, imgsz, โซนนับ) ผ่านไฟล์
ไฟล์ YAML ใน `ai-worker/configs/` แทน CLI arguments เพราะ workflow จริงคือถ่ายคลิปแล้วรันซ้ำหลายรอบ
ปรับค่าทีละนิด — YAML file อ่านง่ายกว่าพิมพ์ flag ยาว ๆ ทุกครั้ง พิจารณา JSON แล้วแต่ YAML
รองรับ comment ได้ (จำเป็นสำหรับอธิบายตัวอย่าง `zones:` ในไฟล์) `pyyaml` เป็นไลบรารีมาตรฐาน
สำหรับงานนี้ใน Python ไม่มีเหตุผลจะเขียน parser เอง

### Why TimescaleDB logging เป็น optional (ปิดเป็นค่าเริ่มต้น) สำหรับ MVP
อาจารย์ระบุว่ายังไม่ต้องมี DB และ server คณะมีทรัพยากรจำกัด จึง gate การเขียน DB ด้วย
flag `ENABLE_DB_LOGGING` (ค่าเริ่มต้น `false`) — pipeline หลัก (ingest → WebSocket → Unity)
ทำงานครบโดยไม่ต้องรัน TimescaleDB โค้ด logger เดิมคงไว้ เปิด flag กลับได้เมื่อพร้อม (Phase 2)
**หมายเหตุ:** นี่คือการเลื่อน ไม่ใช่การแทน DB — TimescaleDB ยังเป็น DB ที่เลือกไว้ (ดู Hard Rule)

### Why Monorepo
Team size is 2. Multi-repo adds overhead (separate CI, versioning, cloning)
with no benefit at this scale. A single repo lets Claude (and teammates)
read cross-module context without switching directories.

---

## 6. Business Rules

These rules must be reflected in code. They are not optional.

| Rule | Where enforced |
|---|---|
| Confidence < 0.5 → discard detection | AI Worker |
| `trackId` must be stable across frames for the same vehicle | AI Worker (ByteTrack) |
| `y` is always `0.0` (ground plane) for MVP | AI Worker + Validation |
| Payload with missing `position.x/z` → reject with HTTP 400 | Backend validation |
| `NaN` or `Infinity` in any coordinate → reject | Backend validation |
| Pool size cap: 120 vehicles max per frame | Unity |
| Lerp duration: ≤ 1.5 seconds to next position | Unity |
| Frame interval target: ~1 second | AI Worker |

---

## 7. Folder Structure

```
DIGITALTWIN/
├── CLAUDE.md               ← AI entry point
├── README.md               ← Setup and commands
├── docker-compose.yml      ← TimescaleDB + infra
├── docs/
│   ├── architecture.md     ← this file
│   ├── data-contract.md    ← JSON schema (source of truth)
│   └── project-status.md  ← milestones and progress
├── ai-worker/
│   ├── CLAUDE.md
│   └── src/
├── backend/
│   ├── CLAUDE.md
│   └── src/
├── unity/
│   ├── CLAUDE.md
│   └── Assets/
└── mock-server/
    ├── CLAUDE.md
    └── scenarios/
```

---

## 8. What This Is NOT (MVP Scope Limits)

- ❌ No NavMesh / AI traffic simulation inside Unity
- ❌ No environmental sensors (PM2.5, carbon) — planned for Phase 2
- ❌ No multi-camera support — 1 camera only
- ❌ No cloud deployment — on-premise only
- ❌ No user authentication on the WebSocket feed