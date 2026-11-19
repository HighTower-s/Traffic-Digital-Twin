"""เทส counter.py — โมดูลบริสุทธิ์ ไม่ต้องมีวิดีโอ/GPU"""

from src.constants import DIRECTION_AWAY, DIRECTION_TOWARD
from src.counter import (
    CountEvent,
    Detection,
    VehicleCounter,
    Zone,
    crossing_direction,
    intersection_point,
    point_in_polygon,
    segments_intersect,
    side_of_line,
)

# โซนทดสอบ: เส้นนับแนวนอนที่ y=100, polygon กว้าง 0-200, ทิศ toward = เข้าหากล้อง (ลงล่าง)
LINE_A = (0.0, 100.0)
LINE_B = (200.0, 100.0)
POLYGON = ((0.0, 0.0), (200.0, 0.0), (200.0, 200.0), (0.0, 200.0))


def make_zone(name: str = "in", direction: str = DIRECTION_TOWARD) -> Zone:
    return Zone(name=name, expected_direction=direction, polygon=POLYGON, line=(LINE_A, LINE_B))


def det(track_id: int, class_id: int, conf: float, cx: float, cy: float) -> Detection:
    return Detection(
        track_id=track_id, class_id=class_id, conf=conf, box=(cx - 5, cy - 5, cx + 5, cy + 5)
    )


# ==================================================== geometry


def test_side_of_line_signs_are_opposite_across_line():
    a, b = (0.0, 0.0), (10.0, 0.0)
    above = side_of_line(a, b, (5.0, -5.0))
    below = side_of_line(a, b, (5.0, 5.0))
    assert (above > 0) != (below > 0)


def test_segments_intersect_crossing():
    assert segments_intersect((0.0, -5.0), (0.0, 5.0), (-5.0, 0.0), (5.0, 0.0)) is True


def test_segments_intersect_not_crossing():
    assert segments_intersect((0.0, -5.0), (0.0, -1.0), (-5.0, 0.0), (5.0, 0.0)) is False


def test_intersection_point_finds_crossing():
    point = intersection_point((0.0, -5.0), (0.0, 5.0), (-5.0, 0.0), (5.0, 0.0))
    assert point == (0.0, 0.0)


def test_intersection_point_parallel_returns_none():
    assert intersection_point((0.0, 0.0), (10.0, 0.0), (0.0, 5.0), (10.0, 5.0)) is None


def test_point_in_polygon_inside():
    assert point_in_polygon((100.0, 100.0), POLYGON) is True


def test_point_in_polygon_outside():
    assert point_in_polygon((300.0, 300.0), POLYGON) is False


def test_crossing_direction_toward_when_moving_down():
    direction = crossing_direction(LINE_A, LINE_B, (100.0, 90.0), (100.0, 110.0))
    assert direction == DIRECTION_TOWARD


def test_crossing_direction_away_when_moving_up():
    direction = crossing_direction(LINE_A, LINE_B, (100.0, 110.0), (100.0, 90.0))
    assert direction == DIRECTION_AWAY


# ==================================================== VehicleCounter


def test_counts_vehicle_that_crosses_line_in_expected_direction():
    counter = VehicleCounter([make_zone()], conf_threshold=0.3)
    counter.update(0, [det(1, 2, 0.9, 100.0, 90.0)])
    counts, anomalies = counter.update(1, [det(1, 2, 0.9, 100.0, 110.0)])

    assert len(counts) == 1
    assert anomalies == []
    event = counts[0]
    assert isinstance(event, CountEvent)
    assert event.vehicle_type == "car"
    assert event.direction == DIRECTION_TOWARD
    assert event.track_id == 1
    assert counter.total_count == 1


def test_does_not_count_before_crossing():
    counter = VehicleCounter([make_zone()], conf_threshold=0.3)
    counter.update(0, [det(1, 2, 0.9, 100.0, 50.0)])
    counts, anomalies = counter.update(1, [det(1, 2, 0.9, 100.0, 60.0)])
    assert counts == []
    assert anomalies == []


def test_rejects_wrong_direction():
    counter = VehicleCounter([make_zone(direction=DIRECTION_TOWARD)], conf_threshold=0.3)
    counter.update(0, [det(1, 2, 0.9, 100.0, 110.0)])
    counts, anomalies = counter.update(1, [det(1, 2, 0.9, 100.0, 90.0)])
    assert counts == []
    assert len(anomalies) == 1
    assert anomalies[0].reason == "wrong_direction"


def test_rejects_outside_polygon():
    zone = Zone(
        name="in",
        expected_direction=DIRECTION_TOWARD,
        polygon=((0.0, 0.0), (50.0, 0.0), (50.0, 200.0), (0.0, 200.0)),
        line=(LINE_A, LINE_B),
    )
    counter = VehicleCounter([zone], conf_threshold=0.3)
    counter.update(0, [det(1, 2, 0.9, 150.0, 90.0)])
    counts, anomalies = counter.update(1, [det(1, 2, 0.9, 150.0, 110.0)])
    assert counts == []
    assert len(anomalies) == 1
    assert anomalies[0].reason == "outside_polygon"


def test_does_not_count_same_track_twice():
    counter = VehicleCounter([make_zone()], conf_threshold=0.3)
    counter.update(0, [det(1, 2, 0.9, 100.0, 90.0)])
    counter.update(1, [det(1, 2, 0.9, 100.0, 110.0)])
    # ข้ามกลับไปกลับมาอีกครั้ง (ไม่ควรถูกนับซ้ำ)
    counter.update(2, [det(1, 2, 0.9, 100.0, 90.0)])
    counts, anomalies = counter.update(3, [det(1, 2, 0.9, 100.0, 110.0)])
    assert counts == []
    assert len(anomalies) == 1
    assert anomalies[0].reason == "already_counted"
    assert counter.total_count == 1


def test_low_confidence_detections_do_not_get_a_type_vote():
    counter = VehicleCounter([make_zone()], conf_threshold=0.5)
    counter.update(0, [det(1, 2, 0.1, 100.0, 90.0)])
    counts, anomalies = counter.update(1, [det(1, 2, 0.1, 100.0, 110.0)])
    assert counts == []
    assert len(anomalies) == 1
    assert anomalies[0].reason == "no_type_votes"


def test_type_is_locked_by_majority_vote_before_crossing():
    counter = VehicleCounter([make_zone()], conf_threshold=0.3)
    # 2 เฟรมโหวต truck, 1 เฟรมโหวต car -> truck ชนะ
    counter.update(0, [det(1, 7, 0.9, 100.0, 70.0)])
    counter.update(1, [det(1, 7, 0.9, 100.0, 80.0)])
    counter.update(2, [det(1, 2, 0.9, 100.0, 90.0)])
    counts, _ = counter.update(3, [det(1, 7, 0.9, 100.0, 110.0)])
    assert counts[0].vehicle_type == "truck"


def test_unrecognized_class_id_is_ignored():
    counter = VehicleCounter([make_zone()], conf_threshold=0.3)
    counter.update(0, [det(1, 1, 0.9, 100.0, 90.0)])  # bicycle
    counts, anomalies = counter.update(1, [det(1, 1, 0.9, 100.0, 110.0)])
    assert counts == []
    assert anomalies == []


def test_summary_lines_report_totals_by_direction_and_type():
    counter = VehicleCounter([make_zone()], conf_threshold=0.3)
    counter.update(0, [det(1, 2, 0.9, 100.0, 90.0)])
    counter.update(1, [det(1, 2, 0.9, 100.0, 110.0)])
    lines = counter.summary_lines()
    assert any("IN" in line and "car=1" in line for line in lines)
