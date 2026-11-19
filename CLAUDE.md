c# Smart Flow — Digital Twin for KMITL Smart Mobility

> **Senior project** — KMITL, Faculty of IT
> **Team size:** 2 developers
> **Phase:** MVP (3 months)

This file is the **entry point** for any AI assistant (Claude, Cursor, etc.) or new
developer joining this project. **Read this file completely before doing anything else.**

---

## 1. What This Project Does

Smart Flow is a Digital Twin prototype that:

1. Ingests video stream (RTSP) from a CCTV camera on Chalong Krung Road, KMITL
2. Detects vehicles using YOLOv8 (Python)
3. Converts 2D image coordinates → 3D world coordinates via Homography
4. Broadcasts vehicle positions over WebSocket to a Unity WebGL frontend
5. Renders cars in a real-time 3D Digital Twin view, second-by-second

**MVP scope:** 1 camera, 1 viewpoint, ~100-120 concurrent vehicles, 3 modules.

---

## 2. Where To Find Things

**Always start by reading the file most relevant to your task. Do NOT load every doc.**

| If you are... | Read this first |
|---|---|
| New to the project | `README.md` → this file → `docs/architecture.md` |
| Implementing a feature | `docs/architecture.md` + `docs/data-contract.md` |
| Modifying JSON payload or APIs | `docs/data-contract.md` **(critical — affects 3 modules)** |
| Fixing a bug | The relevant module's `CLAUDE.md` (e.g. `backend/CLAUDE.md`) |
| Choosing a library or tech | `docs/architecture.md` § Tech Decisions |
| Checking what's done / next | `docs/project-status.md` |
| Running the project locally | `README.md` |

**Module-specific context** (load only when working inside that folder):
- `ai-worker/CLAUDE.md` — Python, YOLOv8, OpenCV
- `backend/CLAUDE.md` — Node.js, Express, Socket.io, TimescaleDB
- `unity/CLAUDE.md` — C#, Unity 2022 LTS, WebGL
- `mock-server/CLAUDE.md` — JSON mock generator

---

## 3. Hard Rules (DO NOT VIOLATE)

These are non-negotiable. If a request conflicts with these, **stop and ask the user.**

1. **Never change `docs/data-contract.md` without explicit user approval.**
   It is the contract between AI Worker, Backend, and Unity. Changes break everything.

2. **Never add a new dependency without updating `docs/architecture.md` § Tech Decisions.**
   Document *why* the new library is needed and what was considered.

3. **Never replace TimescaleDB with another database.**
   This was a deliberate decision (see `docs/architecture.md`). If you think it's wrong,
   raise the concern — don't silently swap it.

4. **Never use AWS / cloud services for MVP.**
   Deployment is on-premise (KMITL server). Cloud is Phase 2.

5. **Never write code without a matching entry plan.**
   If the task is larger than ~50 lines or touches multiple files,
   first outline the plan and confirm with the user.

6. **Always update `docs/project-status.md` after completing a task.**
   Mark the item done, add notes if anything changed.

---

## 4. Tech Stack (Locked for MVP)

| Layer | Tech | Version |
|---|---|---|
| AI Worker | Python, OpenCV, YOLOv8 (Ultralytics) | Python 3.11 |
| Backend | Node.js, Express, Socket.io | Node 20 LTS |
| Database | TimescaleDB (PostgreSQL extension) | TimescaleDB 2.x |
| Frontend | Unity, C#, WebGL build | Unity 2022 LTS |
| Mock server | Node.js (separate from real backend) | Node 20 LTS |
| Deployment | Docker Compose, on-premise | — |

Reasoning behind each choice → `docs/architecture.md` § Tech Decisions.

---

## 5. Coding Standards

### General
- **No silent failures.** Catch errors, log them, and either retry or fail loudly.
- **No magic numbers.** Use named constants (e.g. `MAX_VEHICLES = 120`).
- **Small functions.** If a function exceeds ~40 lines, split it.
- **No secrets in code.** Sensitive data (API keys, passwords, DB credentials, RTSP URLs) must strictly live in `.env` files. Never commit `.env` or hardcode secrets.
- **Comments explain *why*, not *what*.** Code should self-document the *what*.

### Naming
- JSON fields: `camelCase` — see `docs/data-contract.md` for canonical names
- Python: `snake_case` for functions and variables, `PascalCase` for classes
- JavaScript / TypeScript: `camelCase` for variables, `PascalCase` for classes
- C# (Unity): `PascalCase` for public, `_camelCase` for private fields

### Per language
- **Python:** type hints required, format with `black`, lint with `ruff`
- **JavaScript:** TypeScript strict mode, format with Prettier, ESLint enabled
- **C#:** follow Unity's C# conventions, namespace under `SmartFlow.*`

### Commits
Use Conventional Commits:
- `feat: add homography validator`
- `fix: handle WebSocket disconnect`
- `docs: update data contract`
- `refactor: extract pooling logic`

---

## 6. Definition of Done

A task is **not done** until all of these are true:

- [ ] Code passes lint (`npm run lint`, `ruff check`, etc.)
- [ ] Code passes type checks (`tsc --noEmit`, `mypy`, etc.)
- [ ] Manual smoke test passes (run mock server, observe expected behavior)
- [ ] If logic is non-trivial → at least one unit test exists
- [ ] `docs/project-status.md` is updated
- [ ] If data contract or architecture changed → relevant doc updated
- [ ] Commit message follows Conventional Commits

---

## 7. Conflict Resolution

If two documents disagree, follow this priority order:

1. `docs/data-contract.md` — highest authority (cross-module)
2. `docs/architecture.md` — system design and decisions
3. This file (`CLAUDE.md`) — rules and standards
4. `docs/project-status.md` — context only, never a rule

**If you find conflicting information, stop and ask the user. Do not assume.**

---

## 8. When You Are Unsure

- **Unsure about scope?** → Ask. Don't expand the task on your own.
- **Unsure about a library choice?** → Check `docs/architecture.md` first, then ask.
- **Unsure how the modules connect?** → Re-read `docs/data-contract.md`.
- **Unsure if a change is safe?** → Show the diff and ask before applying.

---

## 9. Update Discipline

This document evolves with the project. When updating:

- Keep it **under 250 lines.** If it grows beyond that, split content into `docs/`.
- Update the "Last reviewed" date below.
- Commit with `docs: update CLAUDE.md — <reason>`.

---

> **Last reviewed:** 2026-06-11
> **Maintainers:** [Your name], [Teammate name]
> **Next review:** When tech stack or data contract changes, or every 2 weeks.
