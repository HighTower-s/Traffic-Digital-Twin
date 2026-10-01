"""เทส build_timeline — โดยเฉพาะกฎว่า payload ต้องยังไม่ถูกประกอบตอนสร้างไทม์ไลน์"""

from src.constants import STATE_NORMAL, STATE_STANDSTILL
from src.replay import KIND_SPAWN, KIND_STATE, build_timeline
from src.traffic_state import TrafficThresholds

THRESHOLDS = TrafficThresholds(busy_occupancy=3.0, standstill_flow=2.0, slow_flow=12.0)

WINDOWS = [
    {
        "windowStartSec": 0.0,
        "windowEndSec": 20.0,
        "zones": {"in": {"occupancy": 1.0, "vehicleFlowRate": 30.0, "motorcycleFlowRate": 0.0}},
    },
    {
        "windowStartSec": 20.0,
        "windowEndSec": 40.0,
        "zones": {"in": {"occupancy": 9.0, "vehicleFlowRate": 0.0, "motorcycleFlowRate": 12.0}},
    },
]

EVENTS = [
    {"videoTimeSec": 5.0, "trackId": "car-0001", "type": "car", "direction": "in"},
    {"videoTimeSec": 25.0, "trackId": "car-0002", "type": "car", "direction": "in"},
]


def test_state_items_carry_no_prebuilt_payload():
    """บั๊กจริง 2026-10-01: payload ถูกประกอบพร้อมกันทีเดียวตอนสร้างไทม์ไลน์
    ทำให้ทุกก้อนได้ timestamp เดียวกันทั้งที่ส่งห่างกันเป็นนาที
    ต้องเก็บแค่วัตถุดิบไว้ แล้วประกอบตอนส่งจริง"""
    timeline = build_timeline([], WINDOWS, THRESHOLDS, "cam-test")

    for item in timeline:
        assert item["kind"] == KIND_STATE
        assert (
            "payload" not in item
        ), "ห้ามประกอบ payload ตอนสร้างไทม์ไลน์ ไม่งั้น timestamp จะเพี้ยน"
        assert "window" in item and "state" in item and "zoneStates" in item


def test_state_items_keep_the_verdicts():
    timeline = build_timeline([], WINDOWS, THRESHOLDS, "cam-test")

    assert timeline[0]["state"] == STATE_NORMAL
    assert timeline[0]["zoneStates"] == {"in": STATE_NORMAL}
    assert timeline[1]["state"] == STATE_STANDSTILL
    assert timeline[1]["zoneStates"] == {"in": STATE_STANDSTILL}


def test_spawn_events_pass_through_untouched():
    timeline = build_timeline(EVENTS, [], THRESHOLDS, "cam-test")

    assert [i["kind"] for i in timeline] == [KIND_SPAWN, KIND_SPAWN]
    assert timeline[0]["payload"]["trackId"] == "car-0001"


def test_timeline_is_sorted_by_video_time_across_both_streams():
    """2 สายต้องถูกถักเข้าด้วยกันตามเวลาในวิดีโอ ไม่ใช่ต่อท้ายกัน"""
    timeline = build_timeline(EVENTS, WINDOWS, THRESHOLDS, "cam-test")

    times = [i["videoTimeSec"] for i in timeline]
    assert times == sorted(times)
    assert [i["kind"] for i in timeline] == [KIND_SPAWN, KIND_STATE, KIND_SPAWN, KIND_STATE]
