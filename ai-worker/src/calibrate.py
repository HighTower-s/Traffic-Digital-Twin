"""เครื่องมือคลิกหาพิกัด polygon/line จากเฟรมจริงของวิดีโอ

    python -m src.calibrate                                  ใช้ video: จากไฟล์ config
    python -m src.calibrate --video data/input_videos/x.mp4  หรือระบุเอง
    python -m src.calibrate --frame 90                       เลือกเฟรมอื่น (ค่าเริ่มต้น = 60)
    python -m src.calibrate --zones out                      วาดโซนเดียว (ถนนทางเดียว)
    python -m src.calibrate --preview                        ดูโซนที่ตั้งไว้แล้ว ไม่ต้องวาดใหม่

วิธีใช้ระหว่างรัน:
    คลิกซ้าย  = เพิ่มจุด
    Enter     = จบรูปปัจจุบัน ไปรูปถัดไป (polygon -> line -> zone ถัดไป)
    u         = ลบจุดล่าสุด (คลิกพลาด)
    r         = เริ่มรูปปัจจุบันใหม่
    q         = เลิกทั้งหมด

จบแล้ว print YAML ที่พร้อมวางใน `zones:` ของ ไฟล์ config — พิกัดที่ได้อ้างอิงตาม
ขนาดเฟรมจริงของวิดีโอเสมอ ต่อให้หน้าต่างที่เห็นถูกย่อลงมาแสดงผล (ดู _to_frame_coords)
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from src import config, overlay
from src.constants import DISPLAY_MAX_SIDE

HERE = Path(__file__).parent
AI_WORKER_ROOT = HERE.parent
DEFAULT_CONFIG_PATH = AI_WORKER_ROOT / "configs" / "event-2.yaml"
WINDOW_NAME = "Calibrate (click=add point, Enter=finish, u=undo, r=reset, q=quit)"

ZONE_PRESETS = (("in", "toward"), ("out", "away"))
ZONE_DIRECTIONS = dict(ZONE_PRESETS)
POINT_COLOR = (0, 220, 255)
LINE_COLOR = (60, 200, 60)
TEXT_COLOR = (255, 255, 255)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Click to pick zone coordinates from a real video frame"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--video", type=Path, default=None, help="omit to use video: from the config file"
    )
    parser.add_argument(
        "--frame", type=int, default=60, help="frame number to grab for clicking (default 60)"
    )
    parser.add_argument(
        "--zones",
        default=",".join(name for name, _ in ZONE_PRESETS),
        help=(
            "zones to calibrate, comma separated (default 'in,out') — "
            "for a one-way road or a clip showing a single side, use '--zones out' alone"
        ),
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="draw the configured zones over a real frame (no new drawing) "
        "— check before running YOLO",
    )
    parser.add_argument(
        "--save",
        type=Path,
        default=None,
        help="--preview mode: save an image file instead of opening a window",
    )
    return parser.parse_args(argv)


def _selected_zones(spec: str) -> list[tuple[str, str]]:
    """แปลง '--zones out' เป็น [('out', 'away')] — พังดังถ้าใส่ชื่อที่ไม่รู้จัก"""
    names = [name.strip() for name in spec.split(",") if name.strip()]
    if not names:
        raise SystemExit(f"--zones is empty — give at least 1 zone from {list(ZONE_DIRECTIONS)}")
    unknown = [name for name in names if name not in ZONE_DIRECTIONS]
    if unknown:
        raise SystemExit(f"Unknown zone {unknown} — choose from {list(ZONE_DIRECTIONS)}")
    return [(name, ZONE_DIRECTIONS[name]) for name in names]


def _resolve_video_path(args: argparse.Namespace) -> Path:
    if args.video is not None:
        return args.video
    if not args.config.exists():
        raise SystemExit(f"[error] Config not found: {args.config.resolve()}")
    raw = config.load_yaml_config(args.config)
    video = raw.get("video")
    if not video:
        raise SystemExit(f"[error] {args.config}: no 'video' set and no --video given")
    return AI_WORKER_ROOT / video


def _grab_frame(video_path: Path, frame_index: int) -> tuple[Any, tuple[int, int]]:
    """เปิดวิดีโอ อ่านไปถึงเฟรมที่ขอ แล้วคืนเฟรมนั้น + ขนาดเฟรมจริง"""
    import cv2

    if not video_path.exists():
        raise SystemExit(f"[error] Video file not found: {video_path.resolve()}")

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"[error] Cannot open video: {video_path.resolve()}")

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    frame = None
    for _ in range(frame_index + 1):
        ok, frame = cap.read()
        if not ok:
            break
    cap.release()

    if frame is None:
        raise SystemExit(
            f"[error] Cannot reach frame {frame_index} (the video is shorter than that)"
        )
    return frame, (width, height)


class _Session:
    """เก็บสถานะจุดที่คลิกแล้วของรูปปัจจุบัน + วาดตัวช่วยลงบนภาพที่แสดง"""

    def __init__(self, display_ratio: float) -> None:
        self.display_ratio = display_ratio
        self.points: list[tuple[int, int]] = []  # พิกัดบนเฟรมจริง (แปลงแล้ว)

    def add_click(self, display_x: int, display_y: int) -> None:
        self.points.append(self._to_frame_coords(display_x, display_y))

    def undo(self) -> None:
        if self.points:
            self.points.pop()

    def reset(self) -> None:
        self.points.clear()

    def _to_frame_coords(self, display_x: int, display_y: int) -> tuple[int, int]:
        """แปลงพิกัดบนหน้าต่างที่ย่อแสดงผล กลับเป็นพิกัดเฟรมจริง"""
        ratio = self.display_ratio or 1.0
        return round(display_x / ratio), round(display_y / ratio)

    def to_display_point(self, point: tuple[int, int]) -> tuple[int, int]:
        ratio = self.display_ratio or 1.0
        return round(point[0] * ratio), round(point[1] * ratio)


def _draw_overlay(base_frame: Any, session: _Session, prompt: str) -> Any:
    import cv2

    canvas = base_frame.copy()
    display_points = [session.to_display_point(p) for p in session.points]

    for i, (dx, dy) in enumerate(display_points):
        cv2.circle(canvas, (dx, dy), 5, POINT_COLOR, -1)
        cv2.putText(
            canvas,
            str(i + 1),
            (dx + 8, dy - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            POINT_COLOR,
            1,
            cv2.LINE_AA,
        )
    for i in range(len(display_points) - 1):
        cv2.line(canvas, display_points[i], display_points[i + 1], LINE_COLOR, 2)

    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 34), (20, 24, 30), -1)
    cv2.putText(canvas, prompt, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, TEXT_COLOR, 1, cv2.LINE_AA)
    return canvas


def _collect_points(
    base_frame: Any, session: _Session, prompt: str, min_points: int
) -> list[tuple[int, int]]:
    """เปิดลูปรับคลิก/คีย์บอร์ด จนกด Enter ครบเงื่อนไข หรือ q เพื่อเลิกทั้งหมด"""
    import cv2

    session.reset()
    clicked: list[tuple[int, int]] = []

    def on_mouse(event: int, x: int, y: int, flags: int, userdata: Any) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            session.add_click(x, y)

    cv2.setMouseCallback(WINDOW_NAME, on_mouse)

    while True:
        canvas = _draw_overlay(
            base_frame, session, f"{prompt}  ({len(session.points)}/{min_points}+ points)"
        )
        cv2.imshow(WINDOW_NAME, canvas)
        key = cv2.waitKey(30) & 0xFF

        if key == ord("q"):
            cv2.destroyAllWindows()
            raise SystemExit("[aborted] cancelled by user")
        if key == ord("u"):
            session.undo()
        elif key == ord("r"):
            session.reset()
        elif key in (13, 10):  # Enter
            if len(session.points) >= min_points:
                clicked = list(session.points)
                break
            print(f"  Click at least {min_points} points before pressing Enter")

    return clicked


ZONE_FILL_ALPHA = 0.35
PREVIEW_COLORS = ((0, 220, 255), (255, 170, 40), (140, 255, 140), (255, 130, 255))


def run_preview(args: argparse.Namespace) -> int:
    """วาดโซนจาก ไฟล์ config ทับเฟรมจริง — ตรวจว่าวางถูกก่อนเสียเวลารัน YOLO ทั้งคลิป"""
    import cv2
    import numpy as np

    video_path = _resolve_video_path(args)
    frame, frame_size = _grab_frame(video_path, args.frame)

    raw = config.load_yaml_config(args.config)
    try:
        cfg = config.build_run_config(raw, frame_size, args.config)
    except config.ConfigError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    print(f"Video: {video_path}  frame: {args.frame}  size: {frame_size[0]}x{frame_size[1]}")
    if cfg.is_auto:
        print("[warn] The config file uses 'zones: auto' — these are guessed zones, not your own")

    # ระบายสีลงภาพสำรองก่อน แล้วค่อยผสมกลับ เพื่อให้โซนโปร่งแสง (ยังเห็นถนนข้างใต้)
    overlay_frame = frame.copy()
    for i, zone in enumerate(cfg.zones):
        color = PREVIEW_COLORS[i % len(PREVIEW_COLORS)]
        occupancy = np.array(zone.occupancy_area, np.int32)
        cv2.fillPoly(overlay_frame, [occupancy], color)
        cv2.polylines(frame, [occupancy], True, color, 6)
        cv2.polylines(frame, [np.array(zone.polygon, np.int32)], True, (255, 255, 255), 4)
        a, b = zone.line
        cv2.line(frame, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), (0, 0, 255), 8)

        has_own = bool(zone.occupancy_polygon)
        print(
            f"  {zone.name:>4} ({zone.expected_direction}): polygon {len(zone.polygon)} points, "
            f"occupancyPolygon {'custom' if has_own else 'not set -> uses the counting polygon'}"
        )

    cv2.addWeighted(overlay_frame, ZONE_FILL_ALPHA, frame, 1 - ZONE_FILL_ALPHA, 0, frame)
    for i, zone in enumerate(cfg.zones):
        anchor = min(zone.occupancy_area, key=lambda p: p[1])
        cv2.putText(
            frame,
            zone.name,
            (int(anchor[0]), max(40, int(anchor[1]) - 15)),
            cv2.FONT_HERSHEY_SIMPLEX,
            2.0,
            PREVIEW_COLORS[i % len(PREVIEW_COLORS)],
            5,
            cv2.LINE_AA,
        )

    print(
        "\nColours: filled = occupancyPolygon (density) | "
        "white = counting polygon | red = counting line"
    )

    display = overlay.resize_for_display(frame, overlay.fit_ratio(frame_size, DISPLAY_MAX_SIDE))
    if args.save:
        cv2.imwrite(str(args.save), display)
        print(f"Image saved to: {args.save}")
        return 0

    print("Press any key on the window to close")
    cv2.imshow("Zone preview (press any key to close)", display)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    return 0


def run(args: argparse.Namespace) -> int:
    if args.preview:
        return run_preview(args)

    video_path = _resolve_video_path(args)
    frame, frame_size = _grab_frame(video_path, args.frame)

    display_ratio = overlay.fit_ratio(frame_size, DISPLAY_MAX_SIDE)
    display_frame = overlay.resize_for_display(frame, display_ratio)
    session = _Session(display_ratio)

    import cv2

    cv2.namedWindow(WINDOW_NAME)
    print(f"Video: {video_path}  frame size: {frame_size[0]}x{frame_size[1]}  frame: {args.frame}")
    print("Left click=add point  Enter=finish shape  u=undo  r=reset  q=quit\n")

    zones_yaml: list[str] = []
    for name, direction in _selected_zones(args.zones):
        polygon = _collect_points(
            display_frame, session, f"Zone '{name}': click polygon (>=3 points)", 3
        )
        line = _collect_points(display_frame, session, f"Zone '{name}': click line (2 points)", 2)
        # polygon ที่ 3 สำหรับวัดความหนาแน่น — ต้องครอบถนน "ยาวกว่า" polygon นับ
        # เพราะต้องเห็นแถวรถที่ต่อคิวอยู่ ไม่ใช่แค่บริเวณรอบเส้นนับ
        # (ยิ่งครอบยาว ยิ่งแยก "รถติดสนิท" ออกจาก "ถนนว่าง" ได้ชัด)
        occupancy = _collect_points(
            display_frame,
            session,
            f"Zone '{name}': click occupancyPolygon covering a long stretch of road (>=3 points)",
            3,
        )
        zones_yaml.append(_format_zone_yaml(name, direction, polygon, line, occupancy))

    cv2.destroyAllWindows()

    print("\n" + "=" * 60)
    print("Copy this into your config file (replacing the 'zones:' block):\n")
    print("zones:")
    for block in zones_yaml:
        print(block)
    print("=" * 60)
    return 0


def _format_zone_yaml(
    name: str,
    direction: str,
    polygon: list[tuple[int, int]],
    line: list[tuple[int, int]],
    occupancy_polygon: list[tuple[int, int]] | None = None,
) -> str:
    polygon_str = ", ".join(f"[{x}, {y}]" for x, y in polygon)
    line_str = ", ".join(f"[{x}, {y}]" for x, y in line)
    block = (
        f"  - name: {name}\n"
        f"    expectedDirection: {direction}\n"
        f"    polygon: [{polygon_str}]\n"
        f"    line: [{line_str}]"
    )
    if occupancy_polygon:
        occupancy_str = ", ".join(f"[{x}, {y}]" for x, y in occupancy_polygon)
        block += f"\n    occupancyPolygon: [{occupancy_str}]"
    return block


def main(argv: Sequence[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
