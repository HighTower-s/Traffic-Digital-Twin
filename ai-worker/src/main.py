"""AI Worker — นับรถจากไฟล์วิดีโอ ตั้งค่าผ่าน config.yaml

    python -m src.main                    ใช้ config.yaml ที่ root ของ ai-worker/
    python -m src.main --config other.yaml

ปุ่มระหว่างรัน:  q = ออก   ช่องว่าง = หยุด/เล่นต่อ

**เวอร์ชันนี้ไม่มี lane และไม่มี speed** (ตัดออก 2026-08-09 — ดู ai-worker/CLAUDE.md §5)
ผลลัพธ์อยู่ใน data/output_results/ เสมอ — ส่งเข้า backend ด้วยถ้าตั้ง send_to_backend: true
ใน config.yaml (ปิดเป็นค่าเริ่มต้น) ดู ai-worker/CLAUDE.md §4 Roadmap ขั้น 3
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from src import config, overlay
from src.config import RunConfig
from src.constants import DISPLAY_MAX_SIDE, ZERO_COUNT_WARN_FRAMES
from src.counter import AnomalyEvent, CountEvent, VehicleCounter
from src.detector import DetectorError, VehicleDetector
from src.emitter import SpawnEventWriter
from src.poster import BackendPoster
from src.traffic_state import WindowAccumulator, window_to_dict

HERE = Path(__file__).parent
AI_WORKER_ROOT = HERE.parent
DEFAULT_CONFIG_PATH = AI_WORKER_ROOT / "config.yaml"
OUT_DIR = AI_WORKER_ROOT / "data" / "output_results"
WINDOW_NAME = "AI Worker - vehicle counting (q=quit, space=pause)"

COUNT_COLUMNS = ["frame", "videoTimeSec", "trackId", "type", "zone", "direction", "x", "y"]
ANOMALY_COLUMNS = [*COUNT_COLUMNS, "reason"]


# ==================================================== อ่านค่าจากบรรทัดคำสั่ง


# Command-line interface
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="นับรถจากไฟล์วิดีโอ ตั้งค่าผ่าน config.yaml")
    parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG_PATH, help="path ไปยัง config.yaml"
    )
    return parser.parse_args(argv)


# ==================================================== เขียนไฟล์ผลลัพธ์


def _row(event: CountEvent | AnomalyEvent, fps: float) -> list[Any]:
    seconds = round(event.frame_index / fps, 3) if fps > 0 else 0.0
    return [
        event.frame_index,
        seconds,
        event.track_id,
        event.vehicle_type,
        event.zone,
        event.direction,
        round(event.point[0], 1),
        round(event.point[1], 1),
    ]


def open_csv(path: Path, columns: list[str]) -> tuple[TextIO, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("w", newline="", encoding="utf-8-sig")  # BOM ให้ Excel อ่านภาษาไทยออก
    writer = csv.writer(handle)
    writer.writerow(columns)
    return handle, writer


def open_jsonl(path: Path) -> TextIO:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("w", encoding="utf-8")


def write_jsonl(handle: TextIO, payload: dict[str, Any]) -> None:
    """เขียนทีละบรรทัด + flush ทุกครั้ง — กด Ctrl-C กลางทางแล้วข้อมูลที่วัดมาต้องไม่หาย"""
    handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    handle.flush()


# ==================================================== วิดีโอ


def open_video(path: Path) -> tuple[Any, tuple[int, int], float, int]:
    """เปิดวิดีโอแล้วคืน (cap, ขนาดเฟรม, fps, จำนวนเฟรม) Fail Fast"""
    import cv2

    if not path.exists():
        raise SystemExit(f"Video Files not found: {path.resolve()}")

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise SystemExit(
            f"error cant open video: {path.resolve()}\n"
            f"  ไฟล์อาจเสีย หรือ OpenCV ไม่รองรับ codec นี้ ลองแปลงเป็น H.264 mp4 ก่อน"
        )

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    if width <= 0 or height <= 0:
        cap.release()
        raise SystemExit(f"[ผิดพลาด] อ่านขนาดเฟรมจาก {path.name} ไม่ได้ (ได้ {width}x{height})")
    return cap, (width, height), fps, total


def print_header(
    cfg: RunConfig, frame_size: tuple[int, int], fps: float, total_frames: int, device: str
) -> None:
    print(f"video     : {cfg.video_path}")
    print(f"Frame_size   : {frame_size[0]}x{frame_size[1]}  fps={fps:.2f}  เฟรม={total_frames}")
    print(
        f"model       : {cfg.model}  tracker={cfg.tracker}  "
        f"imgsz={cfg.imgsz}  conf={cfg.conf_threshold}"
    )
    print(f"device      : {device}")
    if cfg.send_to_backend:
        # ย้ำว่าส่งแค่ spawn — ขั้นนี้ยังไม่มีคำตัดสินสถานะให้ส่ง (ดู traffic_state.py)
        print(f"backend     : ส่ง spawn event เข้า {cfg.backend_url}/api/ingest แบบ real-time")
        print("              (สถานะจราจรไม่ได้ส่งตรงนี้ — ตัดสินทีหลังด้วย")
        print("               python -m src.replay --backend)")
    else:
        print("backend     : ปิด (ผลลัพธ์อยู่ใน data/output_results/ เท่านั้น)")
    if cfg.is_auto:
        print(
            "zone         : **เดาให้อัตโนมัติ** จากขนาดเฟรม (ยังไม่ได้กำหนดเอง)\n"
            "              ตัวเลขที่ได้ใช้ดูภาพรวมได้ แต่ยังไม่ควรเอาไปอ้างอิง\n"
            "              ทำให้แม่นขึ้น: กำหนด zones เองใน config.yaml"
        )
    else:
        print("zone         : กำหนดเองใน config.yaml")
    for zone in cfg.zones:
        print(f"              - {zone.name}: {zone.expected_direction}")
    print()


# ==================================================== ลูปหลัก


def run(args: argparse.Namespace) -> int:
    import cv2

    if not args.config.exists():
        print(f"[ผิดพลาด] ไม่พบไฟล์ config: {args.config.resolve()}", file=sys.stderr)
        return 1

    try:
        raw = config.load_yaml_config(args.config)
    except config.ConfigError as exc:
        print(f"[ผิดพลาด] {exc}", file=sys.stderr)
        return 1

    video_path = AI_WORKER_ROOT / raw["video"] if raw.get("video") else None
    if video_path is None:
        print(f"[ผิดพลาด] {args.config}: ต้องระบุ 'video'", file=sys.stderr)
        return 1

    cap, frame_size, fps, total_frames = open_video(video_path)

    try:
        cfg = config.build_run_config(raw, frame_size, args.config)
    except config.ConfigError as exc:
        cap.release()
        print(f"[ผิดพลาด] {exc}", file=sys.stderr)
        return 1

    try:
        detector = VehicleDetector(
            model_path=cfg.model,
            tracker_config=cfg.tracker,
            imgsz=cfg.imgsz,
            conf_threshold=cfg.conf_threshold,
            device=cfg.device,
        )
    except DetectorError as exc:
        cap.release()
        print(f"[ผิดพลาด] {exc}", file=sys.stderr)
        return 1

    print_header(cfg, frame_size, fps, total_frames, detector.device)

    vehicle_counter = VehicleCounter(cfg.zones, conf_threshold=cfg.conf_threshold)
    display_ratio = overlay.fit_ratio(frame_size, DISPLAY_MAX_SIDE)
    show_window = cfg.show_window

    counts_handle, counts_writer = open_csv(OUT_DIR / "counts.csv", COUNT_COLUMNS)
    anomalies_handle, anomalies_writer = open_csv(OUT_DIR / "anomalies.csv", ANOMALY_COLUMNS)
    events = SpawnEventWriter(
        OUT_DIR / "events.jsonl",
        fps=fps,
        camera_id=cfg.camera_id,
        echo=True,
        echo_limit=cfg.emit_preview or None,
    )
    events.open()
    poster = BackendPoster(cfg.backend_url) if cfg.send_to_backend else None

    # วัดความหนาแน่น/อัตราการไหล -> traffic_state.jsonl (ยังไม่ตัดสินสถานะที่นี่
    # การตัดสินอยู่ใน replay.py จะได้จูนเกณฑ์ใหม่โดยไม่ต้องรัน YOLO ซ้ำ)
    windows = WindowAccumulator(cfg.zones, window_sec=cfg.window_sec)
    state_handle = open_jsonl(OUT_DIR / "traffic_state.jsonl")
    windows_written = 0

    frame_index = 0
    warned_zero = False
    warning: str | None = None
    paused = False

    # finally ครอบทั้งลูป: กด q, Ctrl-C, หรือ crash กลางทาง ผลที่นับมาแล้วต้องไม่หาย
    try:
        while True:
            if not paused:
                ok, frame = cap.read()
                if not ok:
                    break

                detections = detector.track(frame)
                new_counts, new_anomalies = vehicle_counter.update(frame_index, detections)

                for event in new_counts:
                    counts_writer.writerow(_row(event, fps))
                    payload = events.emit(event)
                    if poster is not None:
                        poster.post(payload)
                for anomaly in new_anomalies:
                    anomalies_writer.writerow([*_row(anomaly, fps), anomaly.reason])
                if new_counts or new_anomalies:
                    counts_handle.flush()
                    anomalies_handle.flush()

                video_time = frame_index / fps if fps > 0 else 0.0
                window = windows.observe(video_time, detections, new_counts)
                if window is not None:
                    write_jsonl(state_handle, window_to_dict(window))
                    windows_written += 1

                # เตือนเร็วถ้าโซนวางผิด: รู้ตัวใน ~20 วินาที แทนที่จะรู้ตอนรันจบ
                if (
                    not warned_zero
                    and frame_index >= ZERO_COUNT_WARN_FRAMES
                    and vehicle_counter.total_count == 0
                ):
                    warning = f"ยังนับไม่ได้เลยหลัง {ZERO_COUNT_WARN_FRAMES} เฟรม - ตรวจโซน/เส้นนับ"
                    print(f"\n[เตือน] {warning}\n")
                    warned_zero = True

                if show_window:
                    overlay.render(
                        frame,
                        cfg.zones,
                        detections,
                        vehicle_counter,
                        frame_index,
                        fps,
                        detector.device,
                        warning,
                    )
                    cv2.imshow(WINDOW_NAME, overlay.resize_for_display(frame, display_ratio))

                frame_index += 1
                if cfg.max_frames and frame_index >= cfg.max_frames:
                    break

            if show_window:
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    print("\n[หยุด] กด q")
                    break
                if key == ord(" "):
                    paused = not paused
    except KeyboardInterrupt:
        print("\n[หยุด] Ctrl-C")
    finally:
        cap.release()
        if show_window:
            cv2.destroyAllWindows()
        counts_handle.close()
        anomalies_handle.close()
        events.close()
        # ปิดหน้าต่างสุดท้ายที่ยังไม่ครบช่วง ไม่งั้นข้อมูลท้ายคลิปจะหายไปเฉย ๆ
        last = windows.flush(frame_index / fps if fps > 0 else 0.0)
        if last is not None:
            write_jsonl(state_handle, window_to_dict(last))
            windows_written += 1
        state_handle.close()
        if poster is not None:
            poster.close()

    print_summary(vehicle_counter, frame_index, events.emitted, cfg, poster, windows_written)
    return 0


def print_summary(
    vehicle_counter: VehicleCounter,
    frames_processed: int,
    events_written: int,
    cfg: RunConfig,
    poster: BackendPoster | None,
    windows_written: int = 0,
) -> None:
    print("\n" + "=" * 60)
    print(f"ประมวลผล {frames_processed} เฟรม")
    for line in vehicle_counter.summary_lines():
        print("  " + line)
    print(
        f"\n  รวมทั้งหมด {vehicle_counter.total_count} คัน  |  spawn event {events_written} รายการ"
    )
    if poster is not None:
        print(f"  ส่งเข้า backend: {poster.sent} สำเร็จ  |  {poster.failed} ล้มเหลว")
    print(f"  หน้าต่างสถานะจราจร {windows_written} ช่วง (ช่วงละ {cfg.window_sec:.0f} วินาที)")
    if windows_written:
        # ข้อความสุดท้ายก่อนผู้ใช้ไปเปิด dashboard — ถ้าไม่บอกตรงนี้จะงงว่าทำไม State ว่าง
        print("    ^ เป็นผลวัดล้วน ยังไม่ได้ตัดสินและยังไม่ได้ส่งเข้า backend")
        print("      ขั้นต่อไป: python -m src.replay --backend")
    print(f"\n  {OUT_DIR / 'counts.csv'}     รายละเอียดรถที่นับได้")
    print(f"  {OUT_DIR / 'anomalies.csv'}  รถที่ถูกปฏิเสธ พร้อมเหตุผล")
    print(f"  {OUT_DIR / 'events.jsonl'}   payload ที่จะส่งให้ Unity (draft, ไม่มี lane/speed)")
    print(f"  {OUT_DIR / 'traffic_state.jsonl'}  ผลวัดความหนาแน่น/การไหล (ยังไม่ตัดสินสถานะ)")
    if cfg.is_auto:
        print(
            "\n  หมายเหตุ: รอบนี้ใช้โซนที่เดาให้ ตัวเลขยังไม่ควรเอาไปอ้างอิง\n"
            "  ทำให้แม่นขึ้น: กำหนด zones เองใน config.yaml"
        )
    print("=" * 60)


def main(argv: Sequence[str] | None = None) -> int:
    return run(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
