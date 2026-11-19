"""ตรรกะการนับรถ — โมดูลนี้ "บริสุทธิ์" โดยตั้งใจ

ไม่ import cv2 / torch / ultralytics และไม่อ่านเขียนไฟล์ใด ๆ

เหตุผล: บั๊กการนับจะกลายเป็น unit test ที่รันเสร็จใน 1 วินาที แทนที่จะต้องเปิดวิดีโอ
ดูใหม่ทุกครั้ง ซึ่งเป็นปัญหาหลักของโค้ดชุดก่อน
"""

from __future__ import annotations

from collections import Counter as _Counter
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from src.constants import (
    COCO_TO_TYPE,
    DIRECTION_AWAY,
    DIRECTION_TOWARD,
    PRUNE_EVERY_FRAMES,
    REASON_ALREADY_COUNTED,
    REASON_NO_TYPE_VOTES,
    REASON_OUTSIDE_POLYGON,
    REASON_WRONG_DIRECTION,
    TRACK_TTL_FRAMES,
)

Point = tuple[float, float]


# ==================================================== เรขาคณิตพื้นฐาน


def side_of_line(a: Point, b: Point, p: Point) -> float:
    """cross product บอกว่า p อยู่ฝั่งไหนของเส้น a->b

    เครื่องหมายคือสิ่งที่ใช้ ไม่ใช่ขนาด
    """
    return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def segments_intersect(p1: Point, p2: Point, q1: Point, q2: Point) -> bool:
    """ส่วนของเส้นตรง p1->p2 ตัดกับ q1->q2 หรือไม่

    ใช้แทนการเทียบ y > line_y แบบโค้ดชุดเดิม เพราะ
    (1) เส้นนับเอียงได้  (2) รถเร็วกระโดดทีละ 40+ px ต่อเฟรม
    (3) กล่องที่สั่นรอบเส้นจะ trigger ซ้ำถ้าใช้การเทียบเฉย ๆ

    กรณี collinear (ทับกันพอดี) ถือว่า "ไม่ข้าม" — เกิดยากมาก และการนับให้ข้าม
    มีความเสี่ยงนับซ้ำมากกว่าประโยชน์ที่ได้
    """
    d1 = side_of_line(q1, q2, p1)
    d2 = side_of_line(q1, q2, p2)
    d3 = side_of_line(p1, p2, q1)
    d4 = side_of_line(p1, p2, q2)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def intersection_point(p1: Point, p2: Point, q1: Point, q2: Point) -> Point | None:
    """จุดตัดของเส้น p1->p2 กับ q1->q2 คืน None ถ้าขนานกัน"""
    rx, ry = p2[0] - p1[0], p2[1] - p1[1]
    sx, sy = q2[0] - q1[0], q2[1] - q1[1]
    denom = rx * sy - ry * sx
    if denom == 0:
        return None
    t = ((q1[0] - p1[0]) * sy - (q1[1] - p1[1]) * sx) / denom
    return (p1[0] + t * rx, p1[1] + t * ry)


def point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    """ray casting: ยิงรังสีไปทางขวา นับจำนวนครั้งที่ตัดขอบ (คี่ = อยู่ข้างใน)

    เขียนเองแทน cv2.pointPolygonTest เพื่อให้ counter.py ไม่ต้องพึ่ง OpenCV
    """
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_cross = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < x_cross:
                inside = not inside
    return inside


def _oriented(line_a: Point, line_b: Point) -> tuple[Point, Point]:
    """จัดเส้นให้ชี้จากซ้ายไปขวาเสมอ

    ผลคือ "ฝั่งบวก" ของเส้น = ด้านล่างของภาพเสมอ ทำให้ทิศทางที่คำนวณได้
    ไม่ขึ้นกับว่าผู้ใช้คลิกสองจุดเรียงยังไง
    (config.py กันเส้นที่ตั้งเกือบดิ่งไว้แล้ว จึงไม่มีกรณีกำกวม)
    """
    return (line_a, line_b) if line_a[0] <= line_b[0] else (line_b, line_a)


def crossing_direction(line_a: Point, line_b: Point, p1: Point, p2: Point) -> str:
    """ทิศการข้าม: ย้ายจากฝั่งลบไปฝั่งบวกของเส้น = ลงล่าง = เข้าหากล้อง (toward)"""
    a, b = _oriented(line_a, line_b)
    return DIRECTION_TOWARD if side_of_line(a, b, p2) > side_of_line(a, b, p1) else DIRECTION_AWAY


# ==================================================== โครงสร้างข้อมูล


@dataclass(frozen=True)
class Detection:
    """ผลตรวจจับ 1 กล่องใน 1 เฟรม (รูปแบบกลางระหว่าง detector.py กับ counter.py)"""

    track_id: int
    class_id: int
    conf: float
    box: tuple[float, float, float, float]  # x1, y1, x2, y2

    @property
    def anchor(self) -> Point:
        """จุดอ้างอิงของรถ = กึ่งกลางกล่อง

        ใช้กึ่งกลางแทนขอบล่าง เพราะขอบล่างจะกระตุกแรงตอนรถถูกราวสะพานบังบางส่วน
        """
        x1, y1, x2, y2 = self.box
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)


@dataclass(frozen=True)
class Zone:
    """ช่องจราจรหนึ่งฝั่ง: polygon เลือกพื้นที่ + line เส้นนับที่อยู่ในพื้นที่นั้น

    occupancy_polygon เป็นพื้นที่แยกสำหรับ "วัดความหนาแน่น" (ดู traffic_state.py)
    ปกติวาดให้ครอบถนนยาวกว่า polygon นับ เพราะต้องการเห็นแถวรถที่ต่อคิวอยู่
    ไม่ใช่แค่บริเวณรอบเส้นนับ — ถ้าไม่กำหนด จะใช้ polygon เดิมแทน
    """

    name: str
    expected_direction: str
    polygon: tuple[Point, ...]
    line: tuple[Point, Point]
    occupancy_polygon: tuple[Point, ...] = ()

    @property
    def occupancy_area(self) -> tuple[Point, ...]:
        """พื้นที่ที่ใช้วัด occupancy — fallback เป็น polygon นับถ้าไม่ได้กำหนดแยก"""
        return self.occupancy_polygon or self.polygon


@dataclass(frozen=True)
class CountEvent:
    frame_index: int
    track_id: int
    vehicle_type: str
    zone: str
    direction: str
    point: Point
    confidence: float = 0.0


@dataclass(frozen=True)
class AnomalyEvent:
    frame_index: int
    track_id: int
    vehicle_type: str
    zone: str
    direction: str
    point: Point
    reason: str


@dataclass
class _TrackState:
    last_point: Point
    votes: _Counter = field(default_factory=_Counter)
    conf_sum: dict = field(default_factory=lambda: defaultdict(float))


# ==================================================== ตัวนับ


class VehicleCounter:
    """นับรถที่ข้ามเส้นของแต่ละโซน — รับแต่ตัวเลข คืนแต่ event ไม่แตะไฟล์/ภาพ"""

    def __init__(self, zones: Sequence[Zone], conf_threshold: float) -> None:
        self._zones = tuple(zones)
        self._conf_threshold = conf_threshold
        self._tracks: dict[int, _TrackState] = {}
        self._last_seen: dict[int, int] = {}
        self._counted: set[int] = set()
        self._locked: dict[int, str] = {}
        self.totals: dict[tuple[str, str], int] = defaultdict(int)

    @property
    def total_count(self) -> int:
        return sum(self.totals.values())

    def current_type(self, track_id: int) -> str | None:
        """ชนิดที่ใช้แสดงผล: ถ้านับไปแล้วใช้ค่าที่ล็อก ไม่งั้นใช้เสียงข้างมากตอนนี้"""
        locked = self._locked.get(track_id)
        if locked is not None:
            return locked
        state = self._tracks.get(track_id)
        if state is None or not state.votes:
            return None
        return state.votes.most_common(1)[0][0]

    def mean_confidence(self, track_id: int) -> float:
        """conf เฉลี่ยของเฟรมที่โหวตให้ชนิดที่ชนะ — ใช้ไล่ดูว่าคันไหนน่าสงสัย"""
        state = self._tracks.get(track_id)
        vehicle_type = self.current_type(track_id)
        if state is None or vehicle_type is None:
            return 0.0
        votes = state.votes.get(vehicle_type, 0)
        if votes == 0:
            return 0.0
        return state.conf_sum[vehicle_type] / votes

    def update(
        self, frame_index: int, detections: Sequence[Detection]
    ) -> tuple[list[CountEvent], list[AnomalyEvent]]:
        counts: list[CountEvent] = []
        anomalies: list[AnomalyEvent] = []

        for det in detections:
            vehicle_type = COCO_TO_TYPE.get(det.class_id)
            if vehicle_type is None:
                continue  # เช่น bicycle — ไม่ใช่ชนิดที่สนใจ

            point = det.anchor
            self._last_seen[det.track_id] = frame_index
            state = self._tracks.get(det.track_id)

            if state is None:
                # เฟรมแรกของ track นี้ ยังไม่มีจุดก่อนหน้า จึงยังตรวจการข้ามไม่ได้
                state = _TrackState(last_point=point)
                self._tracks[det.track_id] = state
                self._vote(state, vehicle_type, det.conf)
                continue

            self._vote(state, vehicle_type, det.conf)

            previous = state.last_point
            state.last_point = point

            for zone in self._zones:
                event = self._check_zone(frame_index, det.track_id, zone, previous, point)
                if isinstance(event, CountEvent):
                    counts.append(event)
                elif isinstance(event, AnomalyEvent):
                    anomalies.append(event)

        self._prune(frame_index)
        return counts, anomalies

    def _vote(self, state: _TrackState, vehicle_type: str, conf: float) -> None:
        """นับเสียงเฉพาะเฟรมที่มั่นใจพอ — เฟรมเบลอ/ไกลไม่ควรมีสิทธิ์กำหนดชนิด"""
        if conf < self._conf_threshold:
            return
        state.votes[vehicle_type] += 1
        state.conf_sum[vehicle_type] += conf

    def _check_zone(
        self, frame_index: int, track_id: int, zone: Zone, previous: Point, current: Point
    ) -> CountEvent | AnomalyEvent | None:
        line_a, line_b = zone.line
        if not segments_intersect(previous, current, line_a, line_b):
            return None

        point = intersection_point(previous, current, line_a, line_b) or current
        direction = crossing_direction(line_a, line_b, previous, current)
        vehicle_type = self.current_type(track_id) or ""

        def rejected(reason: str) -> AnomalyEvent:
            return AnomalyEvent(
                frame_index, track_id, vehicle_type, zone.name, direction, point, reason
            )

        # ลำดับสำคัญ: เช็ค polygon ก่อน เพราะรถของอีกโซนจะตัดเส้นโซนนี้แบบไม่เกี่ยวข้อง
        if not point_in_polygon(point, zone.polygon):
            return rejected(REASON_OUTSIDE_POLYGON)
        if direction != zone.expected_direction:
            return rejected(REASON_WRONG_DIRECTION)
        if track_id in self._counted:
            return rejected(REASON_ALREADY_COUNTED)
        if not vehicle_type:
            return rejected(REASON_NO_TYPE_VOTES)

        self._counted.add(track_id)
        self._locked[track_id] = vehicle_type
        self.totals[(direction, vehicle_type)] += 1
        return CountEvent(
            frame_index=frame_index,
            track_id=track_id,
            vehicle_type=vehicle_type,
            zone=zone.name,
            direction=direction,
            point=point,
            confidence=self.mean_confidence(track_id),
        )

    def _prune(self, frame_index: int) -> None:
        """ลบ track ที่หายไปนาน

        แต่ _counted ต้องเก็บไว้ตลอด ไม่งั้น tracker ที่ใช้ id ซ้ำจะทำให้รถคันเดิมถูกนับใหม่
        """
        if frame_index % PRUNE_EVERY_FRAMES:
            return
        stale = [t for t, seen in self._last_seen.items() if frame_index - seen > TRACK_TTL_FRAMES]
        for track_id in stale:
            self._tracks.pop(track_id, None)
            self._last_seen.pop(track_id, None)
            self._locked.pop(track_id, None)

    def summary_lines(self) -> list[str]:
        """สรุปผลสำหรับพิมพ์ตอนจบ — แยกตามทิศแล้วตามชนิด"""
        lines: list[str] = []
        for direction in (DIRECTION_TOWARD, DIRECTION_AWAY):
            label = "IN  (toward)" if direction == DIRECTION_TOWARD else "OUT (away)  "
            per_type = {t: n for (d, t), n in self.totals.items() if d == direction and n}
            total = sum(per_type.values())
            detail = ", ".join(f"{t}={n}" for t, n in sorted(per_type.items())) or "-"
            lines.append(f"{label}: total={total}  {detail}")
        return lines
