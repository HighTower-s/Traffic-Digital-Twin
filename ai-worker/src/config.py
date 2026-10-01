"""อ่านและตรวจ config.yaml

หลักการ: **พังให้ดัง** — ถ้า config ผิดหรือไม่ตรงกับวิดีโอ ต้องหยุดพร้อมบอกวิธีแก้
ดีกว่าปล่อยให้รันจนจบแล้วนับได้ 0 คันโดยไม่รู้สาเหตุ ซึ่งเป็นอาการที่เสียเวลาที่สุด

โมดูลนี้ "บริสุทธิ์" เช่นกัน — ไม่ import cv2/torch ตรรกะแยก YAML ออกจาก dict ธรรมดา
ก่อนแล้วค่อยแตะไฟล์จริงที่ main.py จึงทดสอบ validation ได้โดยไม่ต้องมีไฟล์ config.yaml จริง
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.constants import (
    DEFAULT_BACKEND_URL,
    DEFAULT_BUSY_OCCUPANCY,
    DEFAULT_CAMERA_ID,
    DEFAULT_CONF_THRESHOLD,
    DEFAULT_IMGSZ,
    DEFAULT_MODEL,
    DEFAULT_SLOW_FLOW,
    DEFAULT_STANDSTILL_FLOW,
    DEFAULT_TRACKER,
    DEFAULT_WINDOW_SEC,
    DIRECTIONS,
    IO_DIRECTIONS,
)
from src.counter import Point, Zone, point_in_polygon
from src.traffic_state import TrafficThresholds


class ConfigError(Exception):
    """config.yaml ใช้ไม่ได้ — ข้อความต้องบอกได้ว่าต้องทำอะไรต่อ"""


@dataclass(frozen=True)
class RunConfig:
    video_path: Path
    model: str
    tracker: str
    imgsz: int
    conf_threshold: float
    camera_id: str
    device: str
    show_window: bool
    max_frames: int
    emit_preview: int
    zones: tuple[Zone, ...]
    is_auto: bool = False
    send_to_backend: bool = False
    backend_url: str = DEFAULT_BACKEND_URL
    window_sec: float = DEFAULT_WINDOW_SEC
    thresholds: TrafficThresholds = field(default_factory=TrafficThresholds)


def auto_zones(frame_size: tuple[int, int]) -> tuple[Zone, ...]:
    """สร้างโซนแบบเดาให้จากขนาดเฟรม เพื่อให้รันคลิปได้ทันทีโดยไม่ต้องกำหนดโซนเอง

    สมมติฐาน: กล้องมองตามแนวถนนที่แบ่งทิศ ฝั่งขวาของภาพคือขาเข้า ฝั่งซ้ายคือขาออก
    (ตรงกับการจราจรชิดซ้ายของไทย)

    **ตัวเลขที่ได้จะยังไม่แม่น** เส้นนับถูกวางกลางภาพซึ่งอาจอยู่ในระยะที่รถเล็กเกินไป
    และ polygon กินพื้นที่ครึ่งภาพเต็ม ๆ จึงอาจรวมถนนซอยหรือราวสะพานเข้ามาด้วย
    ใช้เพื่อ "เห็นภาพก่อน" เท่านั้น ของจริงต้องกำหนดโซนเองใน config.yaml
    """
    width, height = float(frame_size[0]), float(frame_size[1])
    mid_x = width / 2.0
    # เส้นนับวางที่ 60% ของความสูง: ต่ำกว่ากลางภาพเล็กน้อยเพราะรถใกล้กล้องจะใหญ่กว่า
    line_y = height * 0.60
    top_y, bottom_y = height * 0.25, height * 0.95
    # เว้นขอบซ้าย/ขวาไว้ 4% กันกล่องที่โผล่ครึ่งตัวตรงขอบภาพ
    margin = width * 0.04
    # เส้นนับสั้นกว่า polygon นิดเดียวกันจุดตัดตกบนขอบ polygon พอดี — inset เล็กที่สุดเท่าที่พอ
    # (เคยตั้งไว้ 6% แล้วสร้างช่องตายริมภาพที่รถวิ่งผ่าน polygon แต่ไม่ข้ามเส้น — ไม่ถูกนับ
    # และไม่ขึ้น anomaly ด้วย เป็นอาการที่หาสาเหตุยากที่สุด)
    line_inset = width * 0.005

    return (
        Zone(
            name="in",
            expected_direction=DIRECTIONS[0],  # toward
            polygon=(
                (mid_x, top_y),
                (width - margin, top_y),
                (width - margin, bottom_y),
                (mid_x, bottom_y),
            ),
            line=((mid_x + line_inset, line_y), (width - margin - line_inset, line_y)),
        ),
        Zone(
            name="out",
            expected_direction=DIRECTIONS[1],  # away
            polygon=(
                (margin, top_y),
                (mid_x, top_y),
                (mid_x, bottom_y),
                (margin, bottom_y),
            ),
            line=((margin + line_inset, line_y), (mid_x - line_inset, line_y)),
        ),
    )


def load_yaml_config(path: Path) -> dict[str, Any]:
    """อ่านไฟล์ config.yaml เป็น dict ดิบ — ยังไม่ตรวจ/แปลงเป็น RunConfig"""
    import yaml

    if not path.exists():
        raise ConfigError(f"ไม่พบไฟล์ config: {path.resolve()}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"อ่าน {path} ไม่ได้ (YAML เสีย): {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{path} ต้องเป็น YAML mapping (key: value)")
    return raw


def build_run_config(
    raw: dict[str, Any], frame_size: tuple[int, int], config_path: Path
) -> RunConfig:
    """แปลง dict ดิบจาก config.yaml เป็น RunConfig พร้อมใช้งาน — พังดังถ้าค่าผิด"""
    video = raw.get("video")
    if not video:
        raise ConfigError(f"{config_path}: ต้องระบุ 'video' (path ไปยังไฟล์ .mp4)")

    imgsz = int(raw.get("imgsz", DEFAULT_IMGSZ))
    if imgsz <= 0 or imgsz % 32:
        raise ConfigError(f"{config_path}: imgsz={imgsz} ต้องเป็นจำนวนบวกที่หารด้วย 32 ลงตัว")

    conf_threshold = float(raw.get("conf", DEFAULT_CONF_THRESHOLD))
    if not 0.0 < conf_threshold < 1.0:
        raise ConfigError(
            f"{config_path}: conf={conf_threshold} ต้องอยู่ระหว่าง 0 ถึง 1 (ไม่รวมปลาย)"
        )

    zones_raw = raw.get("zones", "auto")
    is_auto = zones_raw == "auto" or zones_raw is None
    zones = auto_zones(frame_size) if is_auto else _parse_zones(zones_raw, config_path)

    window_sec, thresholds = parse_traffic_state(raw.get("traffic_state"), config_path)

    return RunConfig(
        video_path=Path(video),
        model=str(raw.get("model", DEFAULT_MODEL)),
        tracker=str(raw.get("tracker", DEFAULT_TRACKER)),
        imgsz=imgsz,
        conf_threshold=conf_threshold,
        camera_id=str(raw.get("camera_id", DEFAULT_CAMERA_ID)),
        device=str(raw.get("device", "auto")),
        show_window=bool(raw.get("show_window", True)),
        max_frames=int(raw.get("max_frames", 0)),
        emit_preview=int(raw.get("emit_preview", 0)),
        zones=zones,
        is_auto=is_auto,
        send_to_backend=bool(raw.get("send_to_backend", False)),
        backend_url=str(raw.get("backend_url", DEFAULT_BACKEND_URL)),
        window_sec=window_sec,
        thresholds=thresholds,
    )


def parse_traffic_state(raw_state: Any, config_path: Path) -> tuple[float, TrafficThresholds]:
    """อ่านค่า traffic_state จาก config.yaml — ไม่ระบุก็ได้ ใช้ค่าเริ่มต้นจาก constants.py

    แยกเป็น public เพราะ replay.py ต้องอ่านเกณฑ์โดยไม่ต้องเปิดวิดีโอ
    (build_run_config ต้องรู้ขนาดเฟรมก่อน ซึ่ง replay ไม่มี)
    """
    if raw_state is None:
        return DEFAULT_WINDOW_SEC, TrafficThresholds()
    if not isinstance(raw_state, dict):
        raise ConfigError(f"{config_path}: 'traffic_state' ต้องเป็น mapping (key: value)")

    window_sec = float(raw_state.get("window_sec", DEFAULT_WINDOW_SEC))
    if window_sec <= 0:
        raise ConfigError(f"{config_path}: traffic_state.window_sec={window_sec} ต้องมากกว่า 0")

    raw_thresholds = raw_state.get("thresholds") or {}
    if not isinstance(raw_thresholds, dict):
        raise ConfigError(f"{config_path}: 'traffic_state.thresholds' ต้องเป็น mapping")

    thresholds = TrafficThresholds(
        busy_occupancy=float(raw_thresholds.get("busy_occupancy", DEFAULT_BUSY_OCCUPANCY)),
        standstill_flow=float(raw_thresholds.get("standstill_flow", DEFAULT_STANDSTILL_FLOW)),
        slow_flow=float(raw_thresholds.get("slow_flow", DEFAULT_SLOW_FLOW)),
    )

    # ถ้าสลับกัน สถานะ slow_moving จะไม่มีวันเกิดขึ้นเลย — พังดังดีกว่าเงียบ
    if thresholds.standstill_flow > thresholds.slow_flow:
        raise ConfigError(
            f"{config_path}: traffic_state.thresholds.standstill_flow "
            f"({thresholds.standstill_flow}) ต้องไม่มากกว่า slow_flow "
            f"({thresholds.slow_flow}) — ไม่งั้นจะไม่มีสถานะ slow_moving เลย"
        )
    return window_sec, thresholds


def _parse_zones(raw_zones: Any, config_path: Path) -> tuple[Zone, ...]:
    if not isinstance(raw_zones, list) or not raw_zones:
        raise ConfigError(f"{config_path}: 'zones' ต้องเป็น 'auto' หรือลิสต์ที่มีอย่างน้อย 1 โซน")

    zones: list[Zone] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_zones):
        if not isinstance(raw, dict):
            raise ConfigError(f"{config_path}: zone ลำดับที่ {index} ไม่ใช่ mapping")
        name = str(raw.get("name", "")).strip()
        if not name:
            raise ConfigError(f"{config_path}: zone ลำดับที่ {index} ไม่มีชื่อ")
        # ชื่อโซนถูกส่งออกเป็น field `direction` ของ spawn event ตรง ๆ (ดู emitter)
        # จึงตั้งชื่ออื่นไม่ได้ ไม่งั้น backend จะปฏิเสธ payload ด้วย HTTP 400
        if name not in IO_DIRECTIONS:
            raise ConfigError(
                f"{config_path}: zone ลำดับที่ {index} ชื่อ {name!r} ใช้ไม่ได้ "
                f"ต้องเป็นหนึ่งใน {list(IO_DIRECTIONS)} เพราะชื่อโซนถูกส่งออกเป็น direction"
            )
        if name in seen:
            raise ConfigError(f"{config_path}: ชื่อโซนซ้ำกัน: {name!r}")
        seen.add(name)

        direction = str(raw.get("expectedDirection", ""))
        if direction not in DIRECTIONS:
            raise ConfigError(
                f"{config_path}: โซน {name!r} มี expectedDirection={direction!r} "
                f"ต้องเป็นหนึ่งใน {list(DIRECTIONS)}"
            )

        polygon = _parse_points(raw.get("polygon"), config_path, name, "polygon")
        if len(polygon) < 3:
            raise ConfigError(f"{config_path}: โซน {name!r} polygon ต้องมีอย่างน้อย 3 จุด")

        line = _parse_points(raw.get("line"), config_path, name, "line")
        if len(line) != 2:
            raise ConfigError(f"{config_path}: โซน {name!r} line ต้องมี 2 จุดพอดี")
        _validate_line(line[0], line[1], polygon, config_path, name)

        # ไม่บังคับ — ถ้าไม่มี Zone.occupancy_area จะ fallback ไปใช้ polygon นับแทน
        raw_occupancy = raw.get("occupancyPolygon")
        occupancy_polygon: tuple[Point, ...] = ()
        if raw_occupancy is not None:
            occupancy_polygon = _parse_points(raw_occupancy, config_path, name, "occupancyPolygon")
            if len(occupancy_polygon) < 3:
                raise ConfigError(
                    f"{config_path}: โซน {name!r} occupancyPolygon ต้องมีอย่างน้อย 3 จุด"
                )

        zones.append(
            Zone(
                name=name,
                expected_direction=direction,
                polygon=polygon,
                line=(line[0], line[1]),
                occupancy_polygon=occupancy_polygon,
            )
        )
    return tuple(zones)


def _parse_points(raw: Any, config_path: Path, zone_name: str, field: str) -> tuple[Point, ...]:
    if not isinstance(raw, list):
        raise ConfigError(f"{config_path}: โซน {zone_name!r} ไม่มี {field} หรือรูปแบบผิด")
    points: list[Point] = []
    for item in raw:
        if not isinstance(item, list) or len(item) != 2:
            raise ConfigError(f"{config_path}: โซน {zone_name!r} {field} ต้องเป็นลิสต์ของ [x, y]")
        points.append((float(item[0]), float(item[1])))
    return tuple(points)


def _validate_line(
    a: Point, b: Point, polygon: tuple[Point, ...], config_path: Path, zone_name: str
) -> None:
    """เส้นนับต้องใช้งานได้จริง 3 ข้อ: ยาวพอ, วางขวางถนน, และอยู่ในโซน"""
    dx, dy = b[0] - a[0], b[1] - a[1]

    if dx == 0 and dy == 0:
        raise ConfigError(
            f"{config_path}: โซน {zone_name!r} เส้นนับยาวเป็นศูนย์ "
            f"(จุดเดียวกันสองครั้ง) — แก้ไขค่า line"
        )

    # ถ้าเส้นตั้งเกือบดิ่ง การแยก toward/away จากด้านของเส้นจะกำกวม (ดู counter._oriented)
    if abs(dx) <= abs(dy):
        raise ConfigError(
            f"{config_path}: โซน {zone_name!r} เส้นนับตั้งเกือบดิ่ง "
            f"({a[0]:.0f},{a[1]:.0f})-({b[0]:.0f},{b[1]:.0f}) — ต้องวางขวางถนน ไม่ใช่ตามถนน"
        )

    # จุดกึ่งกลางเส้นต้องอยู่ใน polygon ไม่งั้นรถจะข้ามเส้นแล้วโดนปฏิเสธทุกคัน
    # (นับได้ 0 โดยไม่มี error) ซึ่งเป็นอาการที่หาสาเหตุยากที่สุด
    midpoint: Point = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    if not point_in_polygon(midpoint, polygon):
        raise ConfigError(
            f"{config_path}: โซน {zone_name!r} เส้นนับอยู่นอก polygon ของโซนตัวเอง "
            f"(กึ่งกลางเส้นที่ {midpoint[0]:.0f},{midpoint[1]:.0f}) — "
            f"รถจะถูกปฏิเสธด้วยเหตุผล outside_polygon ทุกคัน"
        )
