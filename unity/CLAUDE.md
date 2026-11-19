# Unity Frontend — CLAUDE.md

> Read `../CLAUDE.md` and `../docs/architecture.md` before this file.
> This file covers only Unity-specific context.

---

## What This Module Does

1. Connects to Backend WebSocket on scene startup
2. Listens for `"frame"` events and deserializes the JSON payload
3. Manages up to 120 vehicle models using **Object Pooling** (no Instantiate/Destroy per frame)
4. Smooths vehicle movement between frames using `Vector3.Lerp`
5. Hides (deactivates) vehicles absent from the latest frame
6. Builds and runs as **WebGL** target in Chrome

---

## Planned Folder Layout

```
unity/
├── CLAUDE.md
└── Assets/
    ├── Scripts/
    │   ├── WebSocketClient.cs    ← connects, receives "frame" events
    │   ├── VehiclePool.cs        ← Object Pool (size 120)
    │   ├── VehicleController.cs  ← Lerp movement per vehicle
    │   └── FrameData.cs          ← C# classes mirroring data contract JSON
    ├── Prefabs/
    │   ├── Car.prefab
    │   ├── Truck.prefab
    │   └── Motorcycle.prefab
    └── Scenes/
        └── DigitalTwin.unity
```

---

## Business Rules (from architecture.md)

- Object Pool only — never call `Instantiate` or `Destroy` during gameplay
- Pool size cap: 120 vehicles (matches backend rejection limit)
- Lerp duration: ≤ 1.5 seconds to next position
- Hide (SetActive false), never destroy vehicles absent from latest frame
- WebGL build target — test in Chrome before marking any task done

---

## Coordinate Mapping

Data contract world coordinates map directly to Unity world space — no transform needed:
- `position.x` → `transform.position.x`
- `position.y` → `transform.position.y` (always 0.0)
- `position.z` → `transform.position.z`

---

## Naming Conventions (C#)

- Public: `PascalCase`
- Private fields: `_camelCase`
- Namespace: `SmartFlow.*` (e.g. `SmartFlow.Network`, `SmartFlow.Vehicles`)

---

## Standards

- Unity 2022 LTS, WebGL build target
- No direct API calls from Unity — all data arrives via WebSocket from Backend only
