"""AI Worker — Count vehicles from a video file, configured via a config file

    python -m src.main                    ใช้ configs/event-2.yaml (ค่าเริ่มต้น)
    python -m src.main --config other.yaml

ปุ่มระหว่างรัน:  q = ออก   ช่องว่าง = หยุด/เล่นต่อ

**เวอร์ชันนี้ไม่มี lane และไม่มี speed** (ตัดออก 2026-08-09 — ดู ai-worker/CLAUDE.md §5)
ผลลัพธ์อยู่ใน data/output_results/ เสมอ — ส่งเข้า backend ด้วยถ้าตั้ง send_to_backend: true
ใน ไฟล์ config (ปิดเป็นค่าเริ่มต้น) ดู ai-worker/CLAUDE.md §4 Roadmap ขั้น 3
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from src import config, overlay, replay
from src.config import RunConfig
from src.constants import DISPLAY_MAX_SIDE, ZERO_COUNT_WARN_FRAMES
from src.counter import AnomalyEvent, CountEvent, VehicleCounter
from src.detector import DetectorError, VehicleDetector
from src.emitter import SpawnEventWriter
from src.poster import BackendPoster
from src.traffic_state import WindowAccumulator, window_to_dict

HERE = Path(__file__).parent
AI_WORKER_ROOT = HERE.parent
DEFAULT_CONFIG_PATH = AI_WORKER_ROOT / "configs" / "event-2.yaml"
OUT_DIR = AI_WORKER_ROOT / "data" / "output_results"
WINDOW_NAME = "AI Worker - vehicle counting (q=quit, space=pause)"

COUNT_COLUMNS = ["frame", "videoTimeSec", "trackId", "type", "zone", "direction", "x", "y"]
ANOMALY_COLUMNS = [*COUNT_COLUMNS, "reason"]


# ==================================================== อ่านค่าจากบรรทัดคำสั่ง


# Command-line interface
def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count vehicles from a video file, configured via a config file"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="path to a config file under configs/",
    )
    # ต่อขั้น "ตัดสิน" ให้อัตโนมัติ — ปกติต้องสั่ง python -m src.replay แยกอีกคำสั่ง
    parser.add_argument(
        "--replay",
        action="store_true",
        help="after detection, immediately show the traffic-state verdicts",
    )
    parser.add_argument(
        "--replay-backend",
        action="store_true",
        help="after detection, immediately post to the backend (start the backend first)",
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
            f"  The file may be corrupt, or OpenCV may not support this codec\n"
            f"  — try converting it to H.264 mp4 first"
        )

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

    if width <= 0 or height <= 0:
        cap.release()
        raise SystemExit(f"[error] Cannot read frame size from {path.name} (got {width}x{height})")
    return cap, (width, height), fps, total


def print_header(
    cfg: RunConfig, frame_size: tuple[int, int], fps: float, total_frames: int, device: str
) -> None:
    print(f"video     : {cfg.video_path}")
    print(f"Frame_size   : {frame_size[0]}x{frame_size[1]}  fps={fps:.2f}  frames={total_frames}")
    print(
        f"model       : {cfg.model}  tracker={cfg.tracker}  "
        f"imgsz={cfg.imgsz}  conf={cfg.conf_threshold}"
    )
    print(f"device      : {device}")
    if cfg.send_to_backend:
        # ย้ำว่าส่งแค่ spawn — ขั้นนี้ยังไม่มีคำตัดสินสถานะให้ส่ง (ดู traffic_state.py)
        print(f"backend     : posting spawn events to {cfg.backend_url}/api/ingest in real time")
        print("              (traffic state is NOT sent here — it is decided later by")
        print("               python -m src.replay --backend)")
    else:
        print("backend     : off (results go to data/output_results/ only)")
    if cfg.is_auto:
        print(
            "zone         : **auto-guessed** from the frame size (not defined by you)\n"
            "              Useful for a quick look, but not reliable enough to cite\n"
            "              For better accuracy: define zones yourself in the config file"
        )
    else:
        print("zone         : defined manually in the config file")
    for zone in cfg.zones:
        print(f"              - {zone.name}: {zone.expected_direction}")
    print()


# ==================================================== ลูปหลัก


def run(args: argparse.Namespace) -> int:
    import cv2

    if not args.config.exists():
        print(f"[error] Config file not found: {args.config.resolve()}", file=sys.stderr)
        return 1

    try:
        raw = config.load_yaml_config(args.config)
    except config.ConfigError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    video_path = AI_WORKER_ROOT / raw["video"] if raw.get("video") else None
    if video_path is None:
        print(f"[error] {args.config}: 'video' is required", file=sys.stderr)
        return 1

    cap, frame_size, fps, total_frames = open_video(video_path)

    try:
        cfg = config.build_run_config(raw, frame_size, args.config)
    except config.ConfigError as exc:
        cap.release()
        print(f"[error] {exc}", file=sys.stderr)
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
        print(f"[error] {exc}", file=sys.stderr)
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
                    warning = (
                        f"still 0 counted after {ZERO_COUNT_WARN_FRAMES} frames"
                        " - check zones/counting line"
                    )
                    print(f"\n[warn] {warning}\n")
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
                    print("\n[stopped] q pressed")
                    break
                if key == ord(" "):
                    paused = not paused
    except KeyboardInterrupt:
        print("\n[stopped] Ctrl-C")
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
    print(f"Processed {frames_processed} frames")
    for line in vehicle_counter.summary_lines():
        print("  " + line)
    print(f"\n  Total {vehicle_counter.total_count} vehicles  |  {events_written} spawn events")
    if poster is not None:
        print(f"  Posted to backend: {poster.sent} ok  |  {poster.failed} failed")
    print(f"  Traffic-state windows: {windows_written} (each {cfg.window_sec:.0f} s)")
    if windows_written:
        # ข้อความสุดท้ายก่อนผู้ใช้ไปเปิด dashboard — ถ้าไม่บอกตรงนี้จะงงว่าทำไม State ว่าง
        print("    ^ measurements only — not yet classified and not sent to the backend")
        print("      Next step: python -m src.replay --backend")
    print(f"\n  {OUT_DIR / 'counts.csv'}     details of every counted vehicle")
    print(f"  {OUT_DIR / 'anomalies.csv'}  rejected vehicles, with reasons")
    print(f"  {OUT_DIR / 'events.jsonl'}   payload sent to Unity (draft, no lane/speed)")
    print(f"  {OUT_DIR / 'traffic_state.jsonl'}  density/flow measurements (not yet classified)")
    # ไฟล์ข้างบนถูกเขียนทับทุกครั้งที่รัน main — อยากเก็บชุดนี้ไว้ต้องย้ายออกไปเอง
    print(
        "\n  To replay this dataset later without re-running YOLO:\n"
        "  copy events.jsonl + traffic_state.jsonl and the config file into runs/<dataset-name>/\n"
        "      python -m src.replay --from runs/<dataset-name> --backend"
    )
    if cfg.is_auto:
        print(
            "\n  Note: this run used auto-guessed zones — the numbers are not yet reliable\n"
            "  For better accuracy: define zones yourself in the config file"
        )
    print("=" * 60)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    status = run(args)
    if status != 0:
        return status

    # เรียก replay ต่อในโพรเซสเดียวกัน — มันอ่าน traffic_state.jsonl ที่ run() เพิ่งเขียนไป
    # (replay.py ไม่ได้ import main.py จึงไม่มี circular import)
    if args.replay or args.replay_backend:
        replay_args = ["--config", str(args.config)]
        replay_args += ["--backend"] if args.replay_backend else ["--fast"]
        print()
        return replay.main(replay_args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
