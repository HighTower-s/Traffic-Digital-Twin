"""เทส emitter.py — โมดูลบริสุทธิ์ ไม่ต้องมีไฟล์จริง"""

import json
from datetime import UTC, datetime
from pathlib import Path

from src.counter import CountEvent
from src.emitter import SpawnEventWriter, to_spawn_event

FIXED_NOW = datetime(2026, 8, 9, 9, 15, 55, 123000, tzinfo=UTC)

REQUIRED_FIELDS = {
    "schema",
    "timestamp",
    "cameraId",
    "videoTimeSec",
    "frameCount",
    "trackId",
    "type",
    "direction",
    "confidence",
}


def make_event(**overrides) -> CountEvent:
    defaults = dict(
        frame_index=1271,
        track_id=42,
        vehicle_type="car",
        zone="in",
        direction="toward",
        point=(100.0, 200.0),
        confidence=0.874,
    )
    defaults.update(overrides)
    return CountEvent(**defaults)


def test_spawn_event_has_all_required_fields():
    payload = to_spawn_event(make_event(), fps=30.0, now=FIXED_NOW)
    assert set(payload.keys()) == REQUIRED_FIELDS


def test_spawn_event_has_no_lane_or_speed_fields():
    payload = to_spawn_event(make_event(), fps=30.0, now=FIXED_NOW)
    assert "lane" not in payload
    assert "speed" not in payload
    assert "speedSource" not in payload


def test_track_id_format():
    payload = to_spawn_event(make_event(track_id=42, vehicle_type="car"), fps=30.0, now=FIXED_NOW)
    assert payload["trackId"] == "car-0042"


def test_direction_comes_from_zone_name():
    assert to_spawn_event(make_event(zone="in"), fps=30.0, now=FIXED_NOW)["direction"] == "in"
    assert to_spawn_event(make_event(zone="out"), fps=30.0, now=FIXED_NOW)["direction"] == "out"


def test_direction_ignores_the_geometric_toward_away():
    """toward/away บอกแค่ทิศ "ในภาพ" ซึ่งขึ้นกับมุมกล้อง — เลนที่วิ่งออกจากกล้อง
    อาจเป็นขาเข้าสถานที่จริงก็ได้ ผู้ตั้งค่าจึงเป็นคนบอกผ่านชื่อโซน

    (เจอจริง 2026-10-02: เลนซ้ายวิ่งออกจากกล้อง (away) แต่เป็นขาเข้า KMITL
    ของเดิมบังคับ away -> "out" เสมอ ทำให้ตั้งเป็นขาเข้าไม่ได้เลย)
    """
    toward_in = to_spawn_event(make_event(zone="in", direction="toward"), 30.0, now=FIXED_NOW)
    away_in = to_spawn_event(make_event(zone="in", direction="away"), 30.0, now=FIXED_NOW)
    assert toward_in["direction"] == away_in["direction"] == "in"

    away_out = to_spawn_event(make_event(zone="out", direction="away"), 30.0, now=FIXED_NOW)
    toward_out = to_spawn_event(make_event(zone="out", direction="toward"), 30.0, now=FIXED_NOW)
    assert away_out["direction"] == toward_out["direction"] == "out"


def test_timestamp_is_iso8601_with_z_suffix():
    payload = to_spawn_event(make_event(), fps=30.0, now=FIXED_NOW)
    assert payload["timestamp"].endswith("Z")
    datetime.fromisoformat(payload["timestamp"].replace("Z", "+00:00"))


def test_video_time_computed_from_frame_and_fps():
    payload = to_spawn_event(make_event(frame_index=60), fps=30.0, now=FIXED_NOW)
    assert payload["videoTimeSec"] == 2.0


def test_video_time_is_zero_when_fps_is_zero():
    payload = to_spawn_event(make_event(frame_index=60), fps=0.0, now=FIXED_NOW)
    assert payload["videoTimeSec"] == 0.0


def test_bus_type_is_kept_as_bus():
    payload = to_spawn_event(make_event(vehicle_type="bus"), fps=30.0, now=FIXED_NOW)
    assert payload["type"] == "bus"
    assert payload["trackId"].startswith("bus-")


def test_confidence_is_rounded():
    payload = to_spawn_event(make_event(confidence=0.123456), fps=30.0, now=FIXED_NOW)
    assert payload["confidence"] == 0.123


def test_all_numeric_values_are_finite():
    payload = to_spawn_event(make_event(), fps=30.0, now=FIXED_NOW)
    for key in ("videoTimeSec", "frameCount", "confidence"):
        value = payload[key]
        assert value == value  # NaN != NaN
        assert value not in (float("inf"), float("-inf"))


def test_payload_is_json_serializable_without_custom_encoder():
    payload = to_spawn_event(make_event(), fps=30.0, now=FIXED_NOW)
    json.dumps(payload)  # ไม่ควร raise


# ==================================================== SpawnEventWriter


def test_writer_writes_one_line_per_event(tmp_path: Path):
    out_path = tmp_path / "events.jsonl"
    with SpawnEventWriter(out_path, fps=30.0, echo=False) as writer:
        writer.emit(make_event(track_id=1))
        writer.emit(make_event(track_id=2))

    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["trackId"] == "car-0001"
    assert json.loads(lines[1])["trackId"] == "car-0002"


def test_writer_creates_parent_directory(tmp_path: Path):
    out_path = tmp_path / "nested" / "dir" / "events.jsonl"
    with SpawnEventWriter(out_path, fps=30.0, echo=False) as writer:
        writer.emit(make_event())
    assert out_path.exists()


def test_writer_tracks_emitted_count(tmp_path: Path):
    out_path = tmp_path / "events.jsonl"
    with SpawnEventWriter(out_path, fps=30.0, echo=False) as writer:
        writer.emit(make_event())
        writer.emit(make_event())
        writer.emit(make_event())
    assert writer.emitted == 3
