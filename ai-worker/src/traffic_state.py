"""วัดสถานะจราจร (ความหนาแน่น + อัตราการไหล) แล้วตัดสินว่าเป็นสถานการณ์แบบไหน

โมดูลนี้ "บริสุทธิ์" เหมือน counter.py — ไม่ import cv2/torch และไม่แตะไฟล์

**ทำไมต้องมีโมดูลนี้:** counter.py นับเฉพาะตอนรถ "ข้ามเส้น" ซึ่งวัดได้แค่ Flow
แต่ความสัมพันธ์พื้นฐานของการจราจรคือ

    Flow = Density x Speed

ถ้าดู Flow อย่างเดียว "รถติดสนิท" (Speed=0) กับ "ถนนว่าง" (Density=0) จะได้ 0
เท่ากันทั้งคู่ แยกไม่ออก จึงต้องวัด Density เพิ่ม = นับรถที่ "อยู่ในโซน" โดยไม่สนว่า
ข้ามเส้นหรือยัง (รถจอดนิ่งก็นับ) ซึ่งเป็นข้อมูลที่ YOLO ให้มาอยู่แล้วทุกเฟรม
เพียงแต่ counter.py ทิ้งไป

เลือกวัด Density แทน Speed เพราะโปรเจกต์นี้เคยวัดความเร็วด้วย homography แล้วพัง
(ได้ 200-290 km/h — ดู docs/project-status.md 2026-07-21)

**แยก "วัด" ออกจาก "ตัดสิน" โดยตั้งใจ:** WindowAccumulator (วัด) แพงเพราะต้องรัน
YOLO ทั้งคลิป ส่วน classify() (ตัดสิน) ถูกมากแต่ต้องปรับเกณฑ์บ่อย -> เก็บผลวัดลงไฟล์
ก่อน แล้วค่อยตัดสินทีหลัง จะได้จูนเกณฑ์ใหม่โดยไม่ต้องรัน YOLO ซ้ำ
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.constants import (
    COCO_TO_TYPE,
    DEFAULT_BUSY_OCCUPANCY,
    DEFAULT_CAMERA_ID,
    DEFAULT_SLOW_FLOW,
    DEFAULT_STANDSTILL_FLOW,
    DEFAULT_WINDOW_SEC,
    FLOW_VEHICLE_TYPES,
    MOTORCYCLE_TYPE,
    STATE_HIGH_DENSITY,
    STATE_NORMAL,
    STATE_SLOW_MOVING,
    STATE_STANDSTILL,
    TRAFFIC_STATE_SCHEMA,
)
from src.counter import CountEvent, Detection, Zone, point_in_polygon
from src.timeutil import iso_timestamp

SECONDS_PER_MINUTE = 60.0
OCCUPANCY_DIGITS = 2
FLOW_DIGITS = 1
TIME_DIGITS = 3

# หน้าต่างสุดท้ายที่สั้นกว่าสัดส่วนนี้ของ window_sec จะถูกทิ้ง — ตัวเลข flow ไม่น่าเชื่อถือ
MIN_WINDOW_FRACTION = 0.5

# ความรุนแรง ใช้เลือกโซนที่แย่ที่สุดมาเป็นตัวแทนทั้งภาพ
_SEVERITY: dict[str, int] = {
    STATE_NORMAL: 0,
    STATE_HIGH_DENSITY: 1,
    STATE_SLOW_MOVING: 2,
    STATE_STANDSTILL: 3,
}


@dataclass(frozen=True)
class TrafficThresholds:
    """เกณฑ์ตัดสิน — ค่าพวกนี้ขึ้นกับว่า occupancyPolygon วาดใหญ่แค่ไหน
    จึงต้องจูนใหม่ทุกครั้งที่เปลี่ยนมุมกล้องหรือขนาดโซน"""

    busy_occupancy: float = DEFAULT_BUSY_OCCUPANCY
    standstill_flow: float = DEFAULT_STANDSTILL_FLOW
    slow_flow: float = DEFAULT_SLOW_FLOW


@dataclass(frozen=True)
class ZoneWindow:
    """สรุปของโซนหนึ่งในหน้าต่างเวลาหนึ่ง

    flow แยกมอเตอร์ไซค์ออกโดยตั้งใจ — มอเตอร์ไซค์มุดผ่านรถติดได้ จึงไม่สะท้อนว่า
    ถนนไหลหรือไม่ ใช้ vehicle_flow_rate อย่างเดียวในการตัดสิน (ดู classify_zone)
    """

    occupancy: float  # จำนวนรถในโซนเฉลี่ยต่อเฟรม = ความหนาแน่น (รถเยอะไหม)
    vehicle_flow_rate: float  # รถยนต์/บรรทุก/บัส ต่อนาที = อัตราการไหล (ถนนไหลไหม)
    motorcycle_flow_rate: float = 0.0  # มอเตอร์ไซค์ต่อนาที — ส่งไปให้ดู ไม่ใช้ตัดสิน


@dataclass(frozen=True)
class TrafficWindow:
    window_start_sec: float
    window_end_sec: float
    zones: dict[str, ZoneWindow]


def count_in_zones(detections: Sequence[Detection], zones: Sequence[Zone]) -> dict[str, int]:
    """นับรถที่อยู่ในพื้นที่วัดความหนาแน่นของแต่ละโซน

    ต่างจาก counter.py ตรงที่ไม่สนว่าข้ามเส้นหรือยัง — รถที่จอดนิ่งก็ถูกนับ
    ซึ่งเป็นสิ่งเดียวที่ทำให้แยก "รถติดสนิท" ออกจาก "ถนนว่าง" ได้

    ใช้ zone.occupancy_area (fallback เป็น polygon นับถ้าไม่ได้กำหนด occupancyPolygon)
    """
    result = dict.fromkeys((zone.name for zone in zones), 0)
    for det in detections:
        if COCO_TO_TYPE.get(det.class_id) is None:
            continue  # bicycle ฯลฯ — ไม่ใช่ชนิดที่สนใจ
        for zone in zones:
            if point_in_polygon(det.anchor, zone.occupancy_area):
                result[zone.name] += 1
    return result


class WindowAccumulator:
    """สะสมค่าที่วัดได้ทุกเฟรม แล้วคืน TrafficWindow เมื่อครบช่วงเวลา

    ไม่ตัดสินสถานะใด ๆ (ดู classify) — เก็บแต่ตัวเลขดิบ ซึ่งเป็นข้อเท็จจริงของวิดีโอ
    ที่ไม่เปลี่ยนตามเกณฑ์ที่เลือกใช้
    """

    def __init__(self, zones: Sequence[Zone], window_sec: float = DEFAULT_WINDOW_SEC) -> None:
        if window_sec <= 0:
            raise ValueError(f"window_sec ต้องมากกว่า 0 (ได้ {window_sec})")
        self._zones = tuple(zones)
        self._window_sec = window_sec
        self._window_start_sec = 0.0
        self._frames = 0
        self._occupancy_sum: dict[str, float] = {}
        self._crossed_vehicle: dict[str, int] = {}
        self._crossed_motorcycle: dict[str, int] = {}
        self._reset_counters()

    def _reset_counters(self) -> None:
        self._frames = 0
        names = [zone.name for zone in self._zones]
        self._occupancy_sum = dict.fromkeys(names, 0.0)
        self._crossed_vehicle = dict.fromkeys(names, 0)
        self._crossed_motorcycle = dict.fromkeys(names, 0)

    def observe(
        self,
        video_time_sec: float,
        detections: Sequence[Detection],
        count_events: Sequence[CountEvent] = (),
    ) -> TrafficWindow | None:
        """เรียกทุกเฟรม — คืน TrafficWindow เมื่อครบหน้าต่าง ไม่งั้นคืน None"""
        for zone_name, n in count_in_zones(detections, self._zones).items():
            self._occupancy_sum[zone_name] += n

        for event in count_events:
            if event.zone not in self._occupancy_sum:
                continue
            if event.vehicle_type == MOTORCYCLE_TYPE:
                self._crossed_motorcycle[event.zone] += 1
            elif event.vehicle_type in FLOW_VEHICLE_TYPES:
                self._crossed_vehicle[event.zone] += 1

        self._frames += 1

        boundary = self._window_start_sec + self._window_sec
        if video_time_sec >= boundary:
            return self._close(boundary)
        return None

    def flush(self, video_time_sec: float) -> TrafficWindow | None:
        """ปิดหน้าต่างสุดท้ายตอนวิดีโอจบ

        **ทิ้งเศษที่สั้นเกินไป** เพราะ flow = คัน x 60 / วินาที -> ยิ่งช่วงสั้น
        รถคันเดียวยิ่งทำให้ตัวเลขพุ่ง (เจอจริง: 1 วินาที 1 คัน = 60 คัน/นาที)
        """
        if video_time_sec - self._window_start_sec < self._window_sec * MIN_WINDOW_FRACTION:
            return None
        return self._close(video_time_sec)

    def _close(self, end_sec: float) -> TrafficWindow | None:
        if self._frames == 0:
            return None

        duration = max(end_sec - self._window_start_sec, 1e-9)
        per_minute = SECONDS_PER_MINUTE / duration
        zones = {
            zone.name: ZoneWindow(
                occupancy=self._occupancy_sum[zone.name] / self._frames,
                vehicle_flow_rate=self._crossed_vehicle[zone.name] * per_minute,
                motorcycle_flow_rate=self._crossed_motorcycle[zone.name] * per_minute,
            )
            for zone in self._zones
        }

        window = TrafficWindow(
            window_start_sec=self._window_start_sec,
            window_end_sec=end_sec,
            zones=zones,
        )
        self._window_start_sec = end_sec
        self._reset_counters()
        return window


def classify_zone(zone_window: ZoneWindow, thresholds: TrafficThresholds) -> str:
    """ตัดสินสถานะของโซนเดียว จาก occupancy (รถเยอะไหม) x flow (รถขยับไหม)

        รถน้อย                       -> normal
        รถเยอะ + ไหลได้ดี             -> high_density
        รถเยอะ + ขยับช้า              -> slow_moving
        รถเยอะ + แทบไม่ขยับ           -> standstill

    ลำดับการเช็คสำคัญ: ต้องดู occupancy ก่อน ไม่งั้น "ถนนว่าง" (flow=0 ด้วย)
    จะถูกตัดสินเป็น standstill

    ใช้ vehicle_flow_rate (ไม่รวมมอเตอร์ไซค์) เพราะมอเตอร์ไซค์มุดผ่านรถติดได้
    ถ้านับรวมจะกลบสัญญาณจนไม่เห็น standstill เลย
    """
    if zone_window.occupancy < thresholds.busy_occupancy:
        return STATE_NORMAL
    if zone_window.vehicle_flow_rate < thresholds.standstill_flow:
        return STATE_STANDSTILL
    if zone_window.vehicle_flow_rate < thresholds.slow_flow:
        return STATE_SLOW_MOVING
    return STATE_HIGH_DENSITY


def classify_zones(window: TrafficWindow, thresholds: TrafficThresholds) -> dict[str, str]:
    """ตัดสินแยกรายโซน — ถนน 2 ฝั่งติดไม่พร้อมกัน จึงต้องรู้ทีละฝั่ง

    (วัดกับคลิปจริง 2026-09-24: ครึ่งหนึ่งของหน้าต่างทั้งหมด 2 ฝั่งอยู่คนละสถานะ
    เช่นขาเข้าโล่งสนิทขณะขาออกติดแน่น การยุบเหลือค่าเดียวจึงทิ้งข้อมูลไปครึ่งหนึ่ง)
    """
    return {
        name: classify_zone(zone_window, thresholds) for name, zone_window in window.zones.items()
    }


def classify(window: TrafficWindow, thresholds: TrafficThresholds) -> str:
    """ตัดสินสถานะรวมจากโซนที่แย่ที่สุด — รถติดฝั่งเดียวก็ถือว่ามีปัญหาจราจรแล้ว

    ใช้คู่กับ classify_zones() ไม่ใช่แทนกัน: ตัวนี้เป็นพาดหัว ตัวนั้นเป็นรายละเอียด
    """
    worst = STATE_NORMAL
    for state in classify_zones(window, thresholds).values():
        if _SEVERITY[state] > _SEVERITY[worst]:
            worst = state
    return worst


def window_to_dict(window: TrafficWindow) -> dict[str, Any]:
    """แปลงผลวัดเป็น dict สำหรับเขียนลง .jsonl

    **ยังไม่มี trafficState** เพราะขั้นนี้คือการ "วัด" เท่านั้น การตัดสินเกิดทีหลัง
    (replay.py) จะได้จูนเกณฑ์ใหม่โดยไม่ต้องรัน YOLO ซ้ำ
    """
    return {
        "windowStartSec": round(window.window_start_sec, TIME_DIGITS),
        "windowEndSec": round(window.window_end_sec, TIME_DIGITS),
        "zones": {
            name: {
                "occupancy": round(zone.occupancy, OCCUPANCY_DIGITS),
                "vehicleFlowRate": round(zone.vehicle_flow_rate, FLOW_DIGITS),
                "motorcycleFlowRate": round(zone.motorcycle_flow_rate, FLOW_DIGITS),
            }
            for name, zone in window.zones.items()
        },
    }


def window_from_dict(data: dict[str, Any]) -> TrafficWindow:
    """อ่านผลวัดกลับจาก .jsonl — ตรงข้ามกับ window_to_dict"""
    zones = {
        name: ZoneWindow(
            occupancy=float(zone["occupancy"]),
            vehicle_flow_rate=float(zone["vehicleFlowRate"]),
            motorcycle_flow_rate=float(zone.get("motorcycleFlowRate", 0.0)),
        )
        for name, zone in data["zones"].items()
    }
    return TrafficWindow(
        window_start_sec=float(data["windowStartSec"]),
        window_end_sec=float(data["windowEndSec"]),
        zones=zones,
    )


def to_traffic_state_payload(
    window: TrafficWindow,
    state: str,
    zone_states: dict[str, str] | None = None,
    camera_id: str = DEFAULT_CAMERA_ID,
    now: datetime | None = None,
) -> dict[str, Any]:
    """สร้าง payload ตาม docs/data-contract.md — ฟังก์ชันบริสุทธิ์ ทดสอบได้โดยไม่ต้องมีวิดีโอ

    zone_states = คำตัดสินรายโซน (จาก classify_zones) ยัดเข้าไปในแต่ละโซนของ payload
    **ไม่ไปแตะ window_to_dict** เพราะรูปแบบนั้นคือสิ่งที่เขียนลง .jsonl ซึ่งต้องเป็นผลวัดล้วน
    """
    measured = window_to_dict(window)

    for name, zone in measured["zones"].items():
        if zone_states and name in zone_states:
            zone["trafficState"] = zone_states[name]

    return {
        "schema": TRAFFIC_STATE_SCHEMA,
        "timestamp": iso_timestamp(now),
        "cameraId": camera_id,
        **measured,
        "trafficState": state,
    }
