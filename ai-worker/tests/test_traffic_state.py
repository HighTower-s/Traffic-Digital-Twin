"""เทส traffic_state.py — โมดูลบริสุทธิ์ ไม่ต้องมีวิดีโอหรือ GPU"""

from datetime import UTC, datetime

import pytest

from src.constants import (
    STATE_HIGH_DENSITY,
    STATE_NORMAL,
    STATE_SLOW_MOVING,
    STATE_STANDSTILL,
)
from src.counter import CountEvent, Detection, Zone
from src.traffic_state import (
    TrafficThresholds,
    TrafficWindow,
    WindowAccumulator,
    ZoneWindow,
    classify,
    classify_zone,
    classify_zones,
    count_in_zones,
    to_traffic_state_payload,
    window_from_dict,
    window_to_dict,
)

FIXED_NOW = datetime(2026, 9, 1, 9, 15, 55, 123000, tzinfo=UTC)

SMALL_BOX = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))
BIG_BOX = ((0.0, 0.0), (400.0, 0.0), (400.0, 400.0), (0.0, 400.0))
FAR_BOX = ((1000.0, 1000.0), (1100.0, 1000.0), (1100.0, 1100.0), (1000.0, 1100.0))

CAR, MOTORCYCLE, BUS, TRUCK = 2, 3, 5, 7


def make_zone(name="out", polygon=SMALL_BOX, occupancy_polygon=()) -> Zone:
    return Zone(
        name=name,
        expected_direction="away",
        polygon=polygon,
        line=((10.0, 50.0), (90.0, 50.0)),
        occupancy_polygon=occupancy_polygon,
    )


def make_detection(class_id=CAR, at=(50.0, 50.0), track_id=1) -> Detection:
    x, y = at
    return Detection(
        track_id=track_id, class_id=class_id, conf=0.9, box=(x - 5, y - 5, x + 5, y + 5)
    )


def make_count_event(vehicle_type="car", zone="out") -> CountEvent:
    return CountEvent(
        frame_index=1,
        track_id=1,
        vehicle_type=vehicle_type,
        zone=zone,
        direction="away",
        point=(50.0, 50.0),
    )


def make_zone_window(occupancy=0.0, flow_rate=0.0, motorcycle_flow=0.0) -> ZoneWindow:
    return ZoneWindow(
        occupancy=occupancy, vehicle_flow_rate=flow_rate, motorcycle_flow_rate=motorcycle_flow
    )


# ==================================================== count_in_zones


def test_counts_vehicles_inside_zone():
    zones = [make_zone()]
    detections = [make_detection(CAR), make_detection(MOTORCYCLE), make_detection(CAR)]
    assert count_in_zones(detections, zones)["out"] == 3


def test_ignores_vehicle_outside_zone():
    zones = [make_zone()]
    detections = [make_detection(CAR, at=(5000.0, 5000.0))]
    assert count_in_zones(detections, zones)["out"] == 0


def test_ignores_class_not_in_coco_map():
    """bicycle (1) ไม่อยู่ใน COCO_TO_TYPE — ต้องไม่ถูกนับและไม่ทำให้พัง"""
    zones = [make_zone()]
    assert count_in_zones([make_detection(class_id=1)], zones)["out"] == 0


def test_counts_all_four_vehicle_types():
    zones = [make_zone()]
    detections = [make_detection(c) for c in (CAR, MOTORCYCLE, BUS, TRUCK)]
    assert count_in_zones(detections, zones)["out"] == 4


def test_uses_occupancy_polygon_when_given():
    """รถที่อยู่นอก polygon นับ แต่อยู่ใน occupancyPolygon ที่ใหญ่กว่า ต้องถูกนับ"""
    zone = make_zone(polygon=SMALL_BOX, occupancy_polygon=BIG_BOX)
    detection = make_detection(CAR, at=(300.0, 300.0))  # นอก SMALL_BOX แต่ใน BIG_BOX
    assert count_in_zones([detection], [zone])["out"] == 1


def test_falls_back_to_counting_polygon_when_no_occupancy_polygon():
    zone = make_zone(polygon=SMALL_BOX)  # ไม่กำหนด occupancyPolygon
    assert count_in_zones([make_detection(CAR, at=(300.0, 300.0))], [zone])["out"] == 0
    assert count_in_zones([make_detection(CAR, at=(50.0, 50.0))], [zone])["out"] == 1


def test_separate_zones_counted_independently():
    zones = [make_zone("out", SMALL_BOX), make_zone("in", FAR_BOX)]
    result = count_in_zones([make_detection(CAR, at=(50.0, 50.0))], zones)
    assert result["out"] == 1
    assert result["in"] == 0


# ==================================================== WindowAccumulator


def test_returns_none_before_window_boundary():
    acc = WindowAccumulator([make_zone()], window_sec=10.0)
    assert acc.observe(1.0, [make_detection()]) is None
    assert acc.observe(9.9, [make_detection()]) is None


def test_emits_window_at_boundary():
    acc = WindowAccumulator([make_zone()], window_sec=10.0)
    acc.observe(1.0, [make_detection()])
    window = acc.observe(10.0, [make_detection()])
    assert window is not None
    assert window.window_start_sec == 0.0
    assert window.window_end_sec == 10.0


def test_occupancy_is_average_per_frame():
    """2 เฟรม เฟรมแรกมีรถ 2 คัน เฟรมสองมี 0 คัน -> เฉลี่ย 1.0"""
    acc = WindowAccumulator([make_zone()], window_sec=10.0)
    acc.observe(1.0, [make_detection(track_id=1), make_detection(track_id=2)])
    window = acc.observe(10.0, [])
    assert window is not None
    assert window.zones["out"].occupancy == pytest.approx(1.0)


def test_car_and_truck_crossings_count_toward_vehicle_flow():
    acc = WindowAccumulator([make_zone()], window_sec=10.0)
    acc.observe(1.0, [], [make_count_event("car"), make_count_event("truck")])
    window = acc.observe(10.0, [], [make_count_event("car")])
    assert window is not None
    assert window.zones["out"].vehicle_flow_rate == pytest.approx(18.0)  # 3 คันใน 10 วิ


def test_flow_rate_scales_crossings_to_per_minute():
    """3 คันใน 10 วินาที = 18 คัน/นาที"""
    acc = WindowAccumulator([make_zone()], window_sec=10.0)
    for _ in range(3):
        acc.observe(1.0, [], [make_count_event("car")])
    window = acc.observe(10.0, [])
    assert window is not None
    assert window.zones["out"].vehicle_flow_rate == pytest.approx(18.0)


def test_counters_reset_between_windows():
    acc = WindowAccumulator([make_zone()], window_sec=10.0)
    acc.observe(1.0, [make_detection()], [make_count_event("car")])
    acc.observe(10.0, [])
    second = acc.observe(20.0, [])
    assert second is not None
    assert second.zones["out"].vehicle_flow_rate == pytest.approx(0.0)
    assert second.zones["out"].occupancy == pytest.approx(0.0)


def test_second_window_starts_where_first_ended():
    acc = WindowAccumulator([make_zone()], window_sec=10.0)
    acc.observe(10.0, [make_detection()])
    second = acc.observe(20.0, [make_detection()])
    assert second is not None
    assert second.window_start_sec == 10.0
    assert second.window_end_sec == 20.0


def test_flush_keeps_partial_window_that_is_long_enough():
    """เศษท้ายคลิปที่ยาวพอ (>= ครึ่งหน้าต่าง) ยังเก็บ — ข้อมูลยังเชื่อถือได้"""
    acc = WindowAccumulator([make_zone()], window_sec=10.0)
    acc.observe(1.0, [make_detection()])
    window = acc.flush(9.0)
    assert window is not None
    assert window.window_end_sec == 9.0


def test_flush_drops_window_that_is_too_short():
    """เศษ 1 วินาที: รถ 1 คัน = 60 คัน/นาที -> ตัวเลขมั่ว ต้องทิ้ง"""
    acc = WindowAccumulator([make_zone()], window_sec=10.0)
    acc.observe(0.5, [make_detection()], [make_count_event("car")])
    assert acc.flush(1.0) is None


def test_flush_returns_none_when_no_frames():
    acc = WindowAccumulator([make_zone()], window_sec=10.0)
    assert acc.flush(5.0) is None


def test_rejects_non_positive_window():
    with pytest.raises(ValueError, match="window_sec"):
        WindowAccumulator([make_zone()], window_sec=0)


# ==================================================== classify_zone


THRESHOLDS = TrafficThresholds(busy_occupancy=3.0, standstill_flow=2.0, slow_flow=12.0)


def test_low_occupancy_is_normal():
    assert classify_zone(make_zone_window(occupancy=1.0, flow_rate=30.0), THRESHOLDS) == (
        STATE_NORMAL
    )


def test_empty_road_is_normal_not_standstill():
    """เคสสำคัญที่สุด: ถนนว่าง flow=0 เหมือนรถติดสนิท แต่ occupancy=0 -> ต้องเป็น normal"""
    assert classify_zone(make_zone_window(occupancy=0.0, flow_rate=0.0), THRESHOLDS) == (
        STATE_NORMAL
    )


def test_busy_and_flowing_is_high_density():
    assert classify_zone(make_zone_window(occupancy=8.0, flow_rate=30.0), THRESHOLDS) == (
        STATE_HIGH_DENSITY
    )


def test_busy_and_slow_is_slow_moving():
    assert classify_zone(make_zone_window(occupancy=8.0, flow_rate=6.0), THRESHOLDS) == (
        STATE_SLOW_MOVING
    )


def test_busy_and_barely_moving_is_standstill():
    assert classify_zone(make_zone_window(occupancy=8.0, flow_rate=0.5), THRESHOLDS) == (
        STATE_STANDSTILL
    )


def test_occupancy_exactly_at_threshold_counts_as_busy():
    assert classify_zone(make_zone_window(occupancy=3.0, flow_rate=0.0), THRESHOLDS) == (
        STATE_STANDSTILL
    )


def test_flow_exactly_at_standstill_threshold_is_slow_not_standstill():
    assert classify_zone(make_zone_window(occupancy=8.0, flow_rate=2.0), THRESHOLDS) == (
        STATE_SLOW_MOVING
    )


# ==================================================== classify (รวมทุกโซน)


def test_overall_state_uses_worst_zone():
    """ฝั่งหนึ่งไหลปกติ อีกฝั่งติดสนิท -> รวมต้องเป็น standstill"""
    window = TrafficWindow(
        window_start_sec=0.0,
        window_end_sec=10.0,
        zones={
            "in": make_zone_window(occupancy=1.0, flow_rate=30.0),
            "out": make_zone_window(occupancy=9.0, flow_rate=0.0),
        },
    )
    assert classify(window, THRESHOLDS) == STATE_STANDSTILL


def test_all_zones_normal_gives_normal():
    window = TrafficWindow(
        window_start_sec=0.0,
        window_end_sec=10.0,
        zones={
            "in": make_zone_window(occupancy=1.0, flow_rate=30.0),
            "out": make_zone_window(occupancy=0.5, flow_rate=24.0),
        },
    )
    assert classify(window, THRESHOLDS) == STATE_NORMAL


# ==================================================== classify_zones (รายโซน)


def test_zone_states_can_differ_between_sides():
    """บั๊กจริงที่เจอ 2026-09-24: ขาเข้าโล่งสนิท ขาออกติดแน่น

    ค่ารวมบอกว่า standstill ทั้งเส้น ทั้งที่ฝั่งหนึ่งวิ่งได้ปกติ
    (วัดกับคลิปจริงแล้ว 50% ของหน้าต่างเป็นแบบนี้) จึงต้องรู้แยกรายฝั่ง
    """
    window = TrafficWindow(
        window_start_sec=120.0,
        window_end_sec=140.0,
        zones={
            "in": make_zone_window(occupancy=0.0, flow_rate=0.0),
            "out": make_zone_window(occupancy=9.0, flow_rate=0.0),
        },
    )

    assert classify_zones(window, THRESHOLDS) == {
        "in": STATE_NORMAL,
        "out": STATE_STANDSTILL,
    }
    # ตัวรวมยังเป็นโซนที่แย่ที่สุดเหมือนเดิม — ใช้คู่กัน ไม่ใช่แทนกัน
    assert classify(window, THRESHOLDS) == STATE_STANDSTILL


def test_classify_zones_covers_every_zone_including_single_zone_roads():
    window = TrafficWindow(
        window_start_sec=0.0,
        window_end_sec=10.0,
        zones={"in": make_zone_window(occupancy=1.0, flow_rate=30.0)},
    )
    assert classify_zones(window, THRESHOLDS) == {"in": STATE_NORMAL}


def test_overall_state_always_matches_worst_zone_state():
    """กันไม่ให้ตรรกะ 2 ทางหลุดกัน — classify ต้องเป็นตัวที่แย่สุดของ classify_zones เสมอ"""
    window = TrafficWindow(
        window_start_sec=0.0,
        window_end_sec=10.0,
        zones={
            "in": make_zone_window(occupancy=8.0, flow_rate=6.0),
            "out": make_zone_window(occupancy=1.0, flow_rate=30.0),
        },
    )
    per_zone = classify_zones(window, THRESHOLDS)
    assert per_zone == {"in": STATE_SLOW_MOVING, "out": STATE_NORMAL}
    assert classify(window, THRESHOLDS) in per_zone.values()
    assert classify(window, THRESHOLDS) == STATE_SLOW_MOVING


# ==================================================== payload


def test_payload_carries_each_zone_verdict():
    window = TrafficWindow(
        window_start_sec=120.0,
        window_end_sec=140.0,
        zones={
            "in": make_zone_window(occupancy=0.0, flow_rate=0.0),
            "out": make_zone_window(occupancy=9.0, flow_rate=0.0),
        },
    )
    zone_states = classify_zones(window, THRESHOLDS)
    payload = to_traffic_state_payload(
        window, classify(window, THRESHOLDS), zone_states, now=FIXED_NOW
    )

    assert payload["zones"]["in"]["trafficState"] == STATE_NORMAL
    assert payload["zones"]["out"]["trafficState"] == STATE_STANDSTILL
    assert payload["trafficState"] == STATE_STANDSTILL
    # ผลวัดต้องยังอยู่ครบ ไม่ถูกแทนที่
    assert payload["zones"]["out"]["occupancy"] == 9.0


def test_payload_without_zone_states_stays_measurement_only():
    """ไม่ส่ง zone_states มา = payload รูปแบบก่อน 1.5.0 ต้องไม่มี key โผล่มาเอง"""
    window = TrafficWindow(
        window_start_sec=0.0,
        window_end_sec=10.0,
        zones={"in": make_zone_window(occupancy=1.0, flow_rate=30.0)},
    )
    payload = to_traffic_state_payload(window, STATE_NORMAL, now=FIXED_NOW)
    assert "trafficState" not in payload["zones"]["in"]


def test_zone_verdicts_never_leak_into_the_jsonl_format():
    """window_to_dict คือรูปแบบที่เขียนลงไฟล์ ต้องเป็นผลวัดล้วนเสมอ

    ถ้าคำตัดสินหลุดลงไฟล์ จะจูนเกณฑ์ใหม่โดยไม่รัน YOLO ซ้ำไม่ได้อีก
    """
    window = TrafficWindow(
        window_start_sec=0.0,
        window_end_sec=10.0,
        zones={"in": make_zone_window(occupancy=9.0, flow_rate=0.0)},
    )
    to_traffic_state_payload(window, STATE_STANDSTILL, classify_zones(window, THRESHOLDS))

    assert "trafficState" not in window_to_dict(window)["zones"]["in"]


def test_payload_has_contract_fields():
    window = TrafficWindow(
        window_start_sec=20.0,
        window_end_sec=30.0,
        zones={"out": ZoneWindow(occupancy=8.2, vehicle_flow_rate=12.0, motorcycle_flow_rate=6.0)},
    )
    payload = to_traffic_state_payload(window, STATE_STANDSTILL, now=FIXED_NOW)

    assert payload["schema"] == "traffic-state/0.1-draft"
    assert payload["timestamp"] == "2026-09-01T09:15:55.123Z"
    assert payload["cameraId"] == "cam-chalongkrung-01"
    assert payload["windowStartSec"] == 20.0
    assert payload["windowEndSec"] == 30.0
    assert payload["trafficState"] == "standstill"

    zone = payload["zones"]["out"]
    assert zone == {"occupancy": 8.2, "vehicleFlowRate": 12.0, "motorcycleFlowRate": 6.0}


def test_payload_is_json_serializable():
    import json

    acc = WindowAccumulator([make_zone()], window_sec=10.0)
    acc.observe(1.0, [make_detection()])
    window = acc.observe(10.0, [])
    assert window is not None
    payload = to_traffic_state_payload(window, STATE_NORMAL, now=FIXED_NOW)
    assert json.loads(json.dumps(payload)) == payload


# ==================================================== เขียน/อ่าน .jsonl


def test_window_dict_roundtrip_preserves_values():
    """เฟส 1 เขียนไฟล์ เฟส 2 อ่านกลับ — ค่าต้องไม่เพี้ยน ไม่งั้นการตัดสินจะผิด"""
    acc = WindowAccumulator([make_zone()], window_sec=10.0)
    acc.observe(1.0, [make_detection(CAR), make_detection(TRUCK, track_id=2)])
    original = acc.observe(10.0, [], [make_count_event("car")])
    assert original is not None

    restored = window_from_dict(window_to_dict(original))

    assert restored.window_start_sec == original.window_start_sec
    assert restored.window_end_sec == original.window_end_sec
    assert restored.zones["out"].occupancy == pytest.approx(original.zones["out"].occupancy)
    assert restored.zones["out"].vehicle_flow_rate == pytest.approx(
        original.zones["out"].vehicle_flow_rate
    )


def test_measurement_file_has_no_traffic_state():
    """ไฟล์ผลวัดต้องไม่มี trafficState — ตัดสินทีหลังเพื่อจูนเกณฑ์ได้โดยไม่ต้องรัน YOLO ใหม่"""
    acc = WindowAccumulator([make_zone()], window_sec=10.0)
    acc.observe(1.0, [make_detection()])
    window = acc.observe(10.0, [])
    assert window is not None
    assert "trafficState" not in window_to_dict(window)


def test_restored_window_classifies_the_same():
    window = TrafficWindow(
        window_start_sec=0.0,
        window_end_sec=10.0,
        zones={"out": make_zone_window(occupancy=9.0, flow_rate=0.0)},
    )
    restored = window_from_dict(window_to_dict(window))
    assert classify(restored, THRESHOLDS) == classify(window, THRESHOLDS) == STATE_STANDSTILL


# ==================================================== ถนนทางเดียว (โซนเดียว)


def test_single_zone_produces_single_zone_payload():
    """คลิปที่เห็นเลนฝั่งเดียว (เช่นคลิปรถติดจากเน็ต) ต้องใช้งานได้ด้วยโซนเดียว"""
    acc = WindowAccumulator([make_zone("out")], window_sec=10.0)
    acc.observe(1.0, [make_detection()])
    window = acc.observe(10.0, [])
    assert window is not None
    assert list(window.zones) == ["out"]
    assert list(window_to_dict(window)["zones"]) == ["out"]


def test_single_zone_detects_standstill():
    """รถจอดนิ่งในโซน ไม่มีใครข้ามเส้น -> standstill (ใช้ได้แม้มีโซนเดียว)"""
    acc = WindowAccumulator([make_zone("out")], window_sec=10.0)
    jam = [make_detection(CAR, at=(40.0, 40.0), track_id=i) for i in range(1, 5)]
    acc.observe(1.0, jam)
    window = acc.observe(10.0, jam)  # จอดนิ่ง ไม่มี count event
    assert window is not None
    assert window.zones["out"].occupancy == pytest.approx(4.0)
    assert window.zones["out"].vehicle_flow_rate == 0.0
    assert classify(window, THRESHOLDS) == STATE_STANDSTILL


# ==================================================== มอเตอร์ไซค์มุดรถติด


def test_motorcycles_do_not_count_as_vehicle_flow():
    """มอเตอร์ไซค์แยกออกจาก flow ที่ใช้ตัดสิน (เคสจริงจาก event-1.mp4 2026-09-02)"""
    acc = WindowAccumulator([make_zone()], window_sec=10.0)
    for _ in range(4):
        acc.observe(1.0, [], [make_count_event("motorcycle")])
    window = acc.observe(10.0, [])
    assert window is not None
    assert window.zones["out"].vehicle_flow_rate == pytest.approx(0.0)
    assert window.zones["out"].motorcycle_flow_rate == pytest.approx(24.0)


def test_standstill_detected_even_when_motorcycles_keep_passing():
    """บั๊กจริงที่เจอ: รถยนต์หยุดสนิท แต่มอเตอร์ไซค์มุดผ่าน 4 คัน

    ก่อนแก้ระบบตอบ high_density (เพราะนับรวมกัน) ต้องได้ standstill
    """
    jam = [make_detection(CAR, track_id=i) for i in range(1, 10)]  # รถยนต์ 9 คันจอดนิ่ง
    acc = WindowAccumulator([make_zone()], window_sec=10.0)
    acc.observe(1.0, jam, [make_count_event("motorcycle")])
    acc.observe(5.0, jam, [make_count_event("motorcycle")])
    window = acc.observe(10.0, jam, [make_count_event("motorcycle")])

    assert window is not None
    assert window.zones["out"].occupancy == pytest.approx(9.0)
    assert window.zones["out"].vehicle_flow_rate == pytest.approx(0.0)
    assert window.zones["out"].motorcycle_flow_rate > 0
    assert classify(window, THRESHOLDS) == STATE_STANDSTILL


def test_motorcycle_flow_does_not_change_the_verdict():
    """เพิ่มมอเตอร์ไซค์เท่าไหร่ก็ไม่เปลี่ยนคำตัดสิน"""
    base = make_zone_window(occupancy=9.0, flow_rate=0.0)
    busy = make_zone_window(occupancy=9.0, flow_rate=0.0, motorcycle_flow=120.0)
    assert classify_zone(base, THRESHOLDS) == classify_zone(busy, THRESHOLDS) == STATE_STANDSTILL
