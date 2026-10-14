"""วาดกล่อง/โซน/เส้น/HUD บนเฟรมสำหรับ cv2.imshow

ใช้ cv2 ตรง ๆ โดยตั้งใจ — โมดูลนี้เป็นทางแสดงผลสด ไม่ใช่แกนการนับ จึงไม่ต้องบริสุทธิ์
เหมือน counter/config/emitter
"""

from __future__ import annotations

from typing import Any

from src.constants import (
    COLOR_BY_TYPE,
    COLOR_HUD_BG,
    COLOR_HUD_TEXT,
    COLOR_LINE,
    COLOR_UNKNOWN,
    COLOR_WARN,
    COLOR_ZONE,
)
from src.counter import Detection, VehicleCounter, Zone


def fit_ratio(frame_size: tuple[int, int], max_side: int) -> float:
    """คำนวณอัตราส่วนย่อภาพให้ด้านที่ยาวที่สุดไม่เกิน max_side"""
    longest = max(frame_size)
    return min(1.0, max_side / longest) if longest > 0 else 1.0


def resize_for_display(frame: Any, ratio: float) -> Any:
    import cv2

    if ratio >= 1.0:
        return frame
    height, width = frame.shape[:2]
    return cv2.resize(frame, (int(width * ratio), int(height * ratio)))


def draw_zones(frame: Any, zones: tuple[Zone, ...]) -> None:
    import cv2

    for zone in zones:
        polygon = [(int(x), int(y)) for x, y in zone.polygon]
        for i in range(len(polygon)):
            cv2.line(frame, polygon[i], polygon[(i + 1) % len(polygon)], COLOR_ZONE, 1)

        line_color = COLOR_LINE.get(zone.expected_direction, COLOR_ZONE)
        a, b = zone.line
        cv2.line(frame, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), line_color, 2)
        cv2.putText(
            frame,
            zone.name,
            (int(a[0]), int(a[1]) - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            line_color,
            1,
            cv2.LINE_AA,
        )


def draw_detections(frame: Any, detections: list[Detection], counter: VehicleCounter) -> None:
    import cv2

    for det in detections:
        vehicle_type = counter.current_type(det.track_id)
        color = COLOR_BY_TYPE.get(vehicle_type, COLOR_UNKNOWN) if vehicle_type else COLOR_UNKNOWN
        x1, y1, x2, y2 = (int(v) for v in det.box)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label = f"{vehicle_type or '?'} #{det.track_id}"
        cv2.putText(
            frame, label, (x1, max(0, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA
        )


def draw_hud(
    frame: Any,
    counter: VehicleCounter,
    frame_index: int,
    fps: float,
    device: str,
    warning: str | None,
) -> None:
    import cv2

    lines = [f"frame={frame_index}  fps={fps:.1f}  device={device}", *counter.summary_lines()]
    if warning:
        lines.append(f"[warn] {warning}")

    pad = 8
    line_height = 22
    box_width = 420
    box_height = pad * 2 + line_height * len(lines)
    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (box_width, box_height), COLOR_HUD_BG, -1)
    cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    for i, line in enumerate(lines):
        color = COLOR_WARN if line.startswith("[warn]") else COLOR_HUD_TEXT
        y = pad + line_height * i + 16
        cv2.putText(frame, line, (pad, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)


def render(
    frame: Any,
    zones: tuple[Zone, ...],
    detections: list[Detection],
    counter: VehicleCounter,
    frame_index: int,
    fps: float,
    device: str,
    warning: str | None,
) -> None:
    """วาดทุกอย่างลงเฟรมโดยตรง (in-place) — เรียงลำดับ: โซน -> กล่อง -> HUD ทับบนสุด"""
    draw_zones(frame, zones)
    draw_detections(frame, detections, counter)
    draw_hud(frame, counter, frame_index, fps, device, warning)
