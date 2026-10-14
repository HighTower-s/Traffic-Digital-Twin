# Smart Flow — Digital Twin for KMITL Smart Mobility

> Senior project — KMITL, Faculty of IT | Team: 2 developers | Phase: Prototype (MVP in progress)

Digital Twin that ingests traffic video, counts vehicles crossing a line with
YOLOv8 (type + direction), and renders spawn events live in a Unity scene.

---

## Architecture (Prototype — current)

```
video file (.mp4)
    │
    ▼
┌─────────────┐   HTTP POST /api/ingest   ┌─────────────┐   WebSocket ("spawn" + "spawn_vehicle")   ┌──────────────┐
│  AI Worker  │ ────────────────────────▶ │   Backend   │ ──────────────────────────────────────▶ │    Unity     │
│  (Python)   │      spawn-event JSON     │  (Node.js)  │        raw + wrapped/trimmed payload      │              │
└─────────────┘                           └─────────────┘                                           └──────────────┘
```

- **No database in this phase** — Backend keeps vehicle counts in memory only
  (`GET /api/stats`). TimescaleDB is planned for a later MVP phase, once the
  pipeline produces real positions/speed again — see `docs/architecture.md`.
- **No mock-server or RTSP in this phase** — AI Worker reads an uploaded/local
  video file, not a live camera feed. See `ai-worker/CLAUDE.md` for the roadmap
  back to real-time RTSP + position tracking.
- Backend broadcasts **two** WebSocket events per spawn-event: `"spawn"` (raw,
  unmodified — used by the backend's own dev dashboard) and `"spawn_vehicle"`
  (wrapped + trimmed to only the fields Unity needs) — see
  `docs/data-contract.md` §2c.

---

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Node.js | 20 LTS | Backend |
| Python | 3.11 | AI Worker |
| Unity | 6000.3.19f1 | Open via Unity Hub — installs this exact version if missing |
| git | any recent | Required — Unity resolves the `SocketIOUnity` package directly from a GitHub URL |
| NVIDIA GPU (optional) | CUDA 12.8+ compatible | Speeds up YOLO inference ~10x+. Not required — falls back to CPU |

---

## Quick Start

### 0. Check out the working branch

```bash
git checkout conect-ai-worker-backend-unity
git pull
```
This branch has the integrated Prototype work (backend, AI Worker, Unity connection).
`main` is behind and does not yet reflect this.

### 1. Backend

```bash
cd backend
npm install
cp .env.example .env      # optional — PORT defaults to 3000 either way
npm run dev
# → Backend running on http://localhost:3000
# → open http://localhost:3000/ for the live dev dashboard
```

### 2. AI Worker

```bash
cd ai-worker
python -m venv .venv && .venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

`ai-worker/**/data/` is entirely gitignored (video files, model weights, output
are never committed) — set up locally:

```bash
mkdir -p data/input_videos data/output_results data/weights
```

- Put your own `.mp4` in `data/input_videos/`, then point `video:` at it in the
  config file you're using — one file per camera angle under `configs/`
  (see [`ai-worker/configs/README.md`](ai-worker/configs/README.md)).
- `yolov8s.pt` doesn't need to be downloaded manually — `ultralytics` fetches it
  automatically on first run if `data/weights/` is empty.

**If you have an NVIDIA GPU**, `pip install -r requirements.txt` alone installs
a **CPU-only** build of torch (much slower). Reinstall matched to your GPU:

```bash
pip uninstall torch torchvision -y
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```
`cu128` matches RTX 40/50-series (Blackwell/Ada). Check
[pytorch.org](https://pytorch.org/get-started/locally/) for the right index URL
if your card is older/different. No GPU → skip this, CPU-only still works, just slower.

Run it:
```bash
python -m src.main                 # writes data/output_results/{events.jsonl,counts.csv,anomalies.csv,traffic_state.jsonl}
python -m src.main --config configs/traffic-5.yaml   # another camera angle
python -m src.main --replay        # detect, then classify + print verdicts in one go
```
Default config is `configs/event-2.yaml`. Set `send_to_backend: true` in that
file (off by default) to also POST each spawn-event to the running backend in
real time. Traffic-state verdicts are sent by `python -m src.replay --backend`
— see [`ai-worker/COMMANDS.md`](ai-worker/COMMANDS.md).

### 3. Unity

1. Open `unity/Smartflow/` via **Unity Hub** (installs `6000.3.19f1` if you don't have it).
2. First open resolves `Packages/manifest.json` automatically, including
   `com.itisnajim.socketiounity` pulled directly from GitHub — needs `git` on
   your PATH and internet access.
3. Check the Console for compile errors (should be none).
4. With the backend running, press Play — a Socket.io client in the scene
   connects and listens for `"spawn_vehicle"` events.

---

## Module Overview

| Folder | Language | Role |
|---|---|---|
| `ai-worker/` | Python 3.11 | Video file → YOLOv8 + ByteTrack → line-crossing counter → spawn-event JSON |
| `backend/` | Node.js 20 | Validate → in-memory counters → WebSocket broadcast (`spawn` + `spawn_vehicle`) |
| `unity/Smartflow/` | C# / Unity | Socket.io client → renders spawn events |
| `docs/` | Markdown | Architecture, data contract, project status |

---

## API Reference (Prototype)

### `POST /api/ingest`
Accepts one spawn-event JSON (see `docs/data-contract.md` §2b).
- `200 OK { ok: true }` — accepted, counted, and broadcast
- `400 Bad Request { error: reason }` — validation failed

### `GET /api/stats`
Returns in-memory vehicle counts by type × direction. `POST /api/stats/reset` zeroes them.

### `GET /health`
Returns `{ "status": "ok", "timestamp": ... }`.

### `GET /`
Live dev dashboard — connection status, `/api/stats` summary, raw `spawn` payload feed.

### WebSocket
Connect to `ws://localhost:3000`.
- `"spawn"` — raw spawn-event, unmodified (same shape as the POST body)
- `"spawn_vehicle"` — wrapped + trimmed for Unity: `{ event: "spawn_vehicle", data: { trackId, type, direction, cameraId, timestamp } }`

---

## Environment Variables

| File | Purpose |
|---|---|
| `backend/.env` | `PORT` (default 3000). MVP-only DB vars are commented out — unused in Prototype |
| `ai-worker/configs/*.yaml` | Video path, model, zones, thresholds, `send_to_backend`, `backend_url` — not a `.env`, plain YAML. One self-contained file per camera angle; default `configs/event-2.yaml` |

**Never commit `.env` files.**

---

## Docs

| File | Purpose |
|---|---|
| `docs/architecture.md` | System design, tech decisions |
| `docs/data-contract.md` | JSON schema — source of truth for all modules |
| `docs/project-status.md` | Milestones, blockers, session log |
| `CLAUDE.md` | Rules and context for AI assistants |
| `ai-worker/CLAUDE.md`, `backend/CLAUDE.md`, `unity/CLAUDE.md` | Module-specific context |
