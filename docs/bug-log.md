# Bug Log — Smart Flow

> Record bugs found during development and testing.
> Format: one entry per bug, newest at top.
> Status: ✅ Fixed | ⏳ Deferred | 🔲 Open

---

## BUG-004 — Mock server generates unrealistic vehicle data

**Date found:** 2026-06-13
**Module:** `mock-server`
**Status:** ⏳ Deferred (fix in next mock-server session)

**Symptom:**
Vehicle speeds and positions in the `normal` scenario are not realistic for Chalong Krung Road. Speed values exceed typical urban traffic, and vehicle movement patterns are not representative of real road behaviour.

**Root cause:**
The scenario generators use arbitrary speed/position ranges without reference to real road constraints (speed limit, lane width, road length).

**How to fix (when ready):**
- Cap `normal` scenario speeds to 30–60 km/h (urban road limit)
- Constrain X positions to actual lane widths (~3.5 m per lane, 2 lanes each direction)
- Constrain Z positions to the visible road segment length from the camera
- Reference `docs/data-contract.md` § Coordinate System for axis orientation

**Files to change:** `mock-server/scenarios/normal.js`, `mock-server/scenarios/congestion.js`

---

## BUG-003 — SocketIOUnity `On()` fires on background thread, crashing Unity API calls silently

**Date found:** 2026-06-13
**Module:** `unity`
**Status:** ✅ Fixed

**Symptom:**
Vehicles never spawned in the scene despite the WebSocket connection succeeding and frames arriving with valid data (`vehicles=5` confirmed in log). No errors or warnings appeared in the Console.

**Root cause:**
`SocketIOUnity.On("frame", callback)` dispatches the callback on a background thread (confirmed by `System.Threading._ThreadPoolWaitCallback` at the bottom of the stack trace). Unity API calls — `Instantiate`, `SetActive`, `transform.position` — are main-thread-only. When called from a background thread, they throw exceptions that are silently swallowed inside SocketIOUnity's async machinery, so nothing spawned and nothing was logged.

**Fix:**
Changed `_socket.On(...)` to `_socket.OnUnityThread(...)`. This variant dispatches the callback on the Unity main thread, making all Unity API calls safe.

```csharp
// Before (wrong — background thread)
_socket.On("frame", response => { ... });

// After (correct — main thread)
_socket.OnUnityThread("frame", response => { ... });
```

**File changed:** `unity/digitaltwin/Assets/Scripts/WebSocketClient.cs`

---

## BUG-002 — `FrameData` deserialization returns null `vehicles` with SocketIOUnity

**Date found:** 2026-06-13
**Module:** `unity`
**Status:** ✅ Fixed

**Symptom:**
Console logged `[WebSocketClient] Received frame with null vehicles array` on every frame, even though the backend was sending valid payloads.

**Root cause:**
`SocketIOUnity`'s `response.GetValue<T>()` uses `System.Text.Json` internally. By default, `System.Text.Json` only serializes/deserializes **properties**, not **public fields**. Our `FrameData`, `VehicleData`, and `PositionData` classes use public fields (required by `JsonUtility`), so `System.Text.Json` skipped them and returned default values (`vehicles = null`).

**Fix:**
Extract the raw JSON string from the response and parse it with Unity's `JsonUtility`, which correctly handles `[Serializable]` classes with public fields.

```csharp
// Before (wrong — System.Text.Json ignores public fields)
frame = response.GetValue<FrameData>();

// After (correct — JsonUtility handles [Serializable] fields)
string json = response.GetValue<System.Text.Json.JsonElement>().GetRawText();
frame = JsonUtility.FromJson<FrameData>(json);
```

**File changed:** `unity/digitaltwin/Assets/Scripts/WebSocketClient.cs`

---

## BUG-001 — Five correctness bugs in initial Unity scripts (found via code review)

**Date found:** 2026-06-13
**Module:** `unity`
**Status:** ✅ Fixed

**Bugs found and fixed in one pass:**

### 1. `VehiclePool` — Acquire runs before Release (critical)
**Symptom:** When all 120 vehicles turn over in one frame, new vehicles are silently dropped.
**Root cause:** `ApplyFrame` called `Acquire` for new vehicles before `Release` for absent ones. The `_active.Count >= 120` cap check saw stale entries, returned `null` for every new vehicle.
**Fix:** Moved the release loop to run first, then the acquire loop.

### 2. `VehicleController` — Lerp uses shifting origin (high)
**Symptom:** Vehicles decelerate exponentially and never arrive at their target position cleanly within `LerpDuration`.
**Root cause:** `Vector3.Lerp(transform.position, _targetPosition, t)` uses the current (already-moved) position as the origin each frame — this is easing, not linear interpolation.
**Fix:** Added `_startPosition` field, captured in `UpdateTarget`, and changed Lerp to `Vector3.Lerp(_startPosition, _targetPosition, t)`.

### 3. `VehiclePool` — `AddComponent` without `GetComponent` check (medium)
**Symptom:** If a prefab already has `VehicleController` attached in the Editor, two instances run simultaneously, causing jitter.
**Fix:** `go.GetComponent<VehicleController>() ?? go.AddComponent<VehicleController>()`

### 4. `WebSocketClient` — `OnClose` fires on intentional `OnDestroy` close (low)
**Symptom:** `_shouldReconnect = true` set on a destroyed MonoBehaviour when `OnDestroy` closes the socket.
**Fix:** Added `private bool _isDestroying` flag, set before `Close()`, and guarded `OnClose` with `if (_isDestroying) return`.

### 5. `VehiclePool` — per-frame `new List<string>()` allocation (cleanup)
**Symptom:** GC pressure every frame from short-lived list allocation.
**Fix:** Promoted `_toRelease` to a class-level field, cleared with `.Clear()` each frame.

**Files changed:** `unity/digitaltwin/Assets/Scripts/VehiclePool.cs`, `VehicleController.cs`, `WebSocketClient.cs`
