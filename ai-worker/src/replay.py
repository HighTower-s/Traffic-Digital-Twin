"""เล่นซ้ำผลที่ main.py ตรวจจับไว้ ตามจังหวะเวลาจริงของวิดีโอต้นฉบับ

    python -m src.replay                 ดูอย่างเดียว ตามจังหวะจริง (ไม่ส่งเข้า backend)
    python -m src.replay --backend       ส่งเข้า backend ด้วย (ต้องรัน backend ไว้ก่อน)
    python -m src.replay --fast          ไม่หน่วงเวลา — ใช้ตอนจูนเกณฑ์ จะได้เห็นผลทันที
    python -m src.replay --from runs/x   เล่นชุดข้อมูลที่เก็บไว้ แทนผลรันล่าสุด

อ่าน 2 ไฟล์ที่ main.py สร้างไว้ แล้วส่งเป็น 2 สายคู่ขนานตามเวลาเดียวกัน:
  events.jsonl        -> spawn event (รถ 1 คันข้ามเส้น)      -> POST /api/ingest
  traffic_state.jsonl -> สถานะจราจร (สรุปทุก window_sec)      -> POST /api/traffic-state

ปกติอ่านจาก data/output_results/ ซึ่ง main.py **เขียนทับทุกครั้งที่รัน** — ถ้าอยากเก็บ
ชุดข้อมูลของคลิปไหนไว้เล่นซ้ำโดยไม่ต้องรัน YOLO ใหม่ ก็อปไปไว้ใน runs/<ชื่อชุด>/
แล้วเรียกด้วย --from (ดู ai-worker/runs/README.md)

**การตัดสินสถานะเกิดที่นี่ ไม่ใช่ตอน main.py** เพราะการวัดแพง (ต้องรัน YOLO ทั้งคลิป)
แต่การตัดสินถูกมากและต้องปรับเกณฑ์บ่อย -> แก้เกณฑ์ใน ไฟล์ config แล้วรันไฟล์นี้ใหม่
ได้เลยโดยไม่ต้องรัน YOLO ซ้ำ (ดู ai-worker/CLAUDE.md)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from src import config
from src.constants import DEFAULT_BACKEND_URL, DEFAULT_CAMERA_ID
from src.pacer import replay_paced
from src.poster import BackendPoster
from src.timeutil import iso_timestamp
from src.traffic_state import (
    TrafficThresholds,
    classify,
    classify_zones,
    to_traffic_state_payload,
    window_from_dict,
)

HERE = Path(__file__).parent
AI_WORKER_ROOT = HERE.parent
OUT_DIR = AI_WORKER_ROOT / "data" / "output_results"
DEFAULT_EVENTS_PATH = OUT_DIR / "events.jsonl"
DEFAULT_STATE_PATH = OUT_DIR / "traffic_state.jsonl"
DEFAULT_CONFIG_PATH = AI_WORKER_ROOT / "configs" / "event-2.yaml"
RUNS_DIR = AI_WORKER_ROOT / "runs"

KIND_SPAWN = "spawn"
KIND_STATE = "state"

RUN_CONFIG_NAME = "config.yaml"
RUN_EVENTS_NAME = "events.jsonl"
RUN_STATE_NAME = "traffic_state.jsonl"


def resolve_run_dir(run_dir: Path) -> tuple[Path, Path, Path]:
    """แปลงโฟลเดอร์ชุดข้อมูลเป็น (config, events, traffic_state)

    ชุดข้อมูลต้องสมบูรณ์ในตัวเอง — เกณฑ์ตัดสินผูกกับขนาดกรอบและมุมกล้อง ย้ายข้ามชุดไม่ได้
    (event-1 วัด occupancy ได้ 14-17 ส่วน event-2 ได้ 0-11 ทั้งที่รถติดพอกัน) จึงบังคับให้
    config.yaml อยู่ในโฟลเดอร์เดียวกับข้อมูล ไม่ถอยไปใช้ค่าเริ่มต้นให้เงียบ ๆ
    """
    if not run_dir.is_dir():
        available = (
            sorted(d.name for d in RUNS_DIR.iterdir() if d.is_dir()) if RUNS_DIR.is_dir() else []
        )
        raise config.ConfigError(
            f"Dataset folder not found: {run_dir.resolve()}"
            + (f"\n  Datasets in runs/: {available}" if available else "")
        )

    events_path = run_dir / RUN_EVENTS_NAME
    config_path = run_dir / RUN_CONFIG_NAME
    missing = [name for name in (RUN_EVENTS_NAME, RUN_CONFIG_NAME) if not (run_dir / name).exists()]
    if missing:
        found = sorted(f.name for f in run_dir.iterdir())
        hint = (
            f"\n  Copy {RUN_CONFIG_NAME} from configs/<the camera angle used>.yaml"
            if RUN_CONFIG_NAME in missing
            else ""
        )
        raise config.ConfigError(
            f"Dataset {run_dir} is incomplete — missing {missing}"
            f"\n  Files present: {found}{hint}"
        )

    return config_path, events_path, run_dir / RUN_STATE_NAME


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replay events.jsonl + traffic_state.jsonl at the original video pace"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--file", type=Path, default=DEFAULT_EVENTS_PATH, help="path to events.jsonl"
    )
    parser.add_argument(
        "--state-file", type=Path, default=DEFAULT_STATE_PATH, help="path to traffic_state.jsonl"
    )
    parser.add_argument(
        "--backend", action="store_true", help="also POST to the backend (not just print)"
    )
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    parser.add_argument(
        "--fast",
        action="store_true",
        help="no pacing delay — use while tuning thresholds to see results instantly",
    )
    # dest ต้องไม่ใช่ "from" — เป็น keyword ของ Python เข้าถึงผ่าน args.from ไม่ได้
    parser.add_argument(
        "--from",
        dest="from_dir",
        type=Path,
        default=None,
        help=f"dataset folder under runs/ — reads {RUN_CONFIG_NAME} + "
        f"{RUN_EVENTS_NAME} + {RUN_STATE_NAME} from it",
    )
    args = parser.parse_args(argv)

    if args.from_dir is not None:
        # ถ้าปล่อยให้ --from ทับเงียบ ๆ จะเกิดกรณี "สั่ง --config ไว้แต่ไม่มีผล"
        # ซึ่งมองไม่เห็นจนกว่าจะเทียบตัวเลขเอง — ขัดกฎ No silent failures
        overridden = [
            flag
            for flag, value, default in (
                ("--config", args.config, DEFAULT_CONFIG_PATH),
                ("--file", args.file, DEFAULT_EVENTS_PATH),
                ("--state-file", args.state_file, DEFAULT_STATE_PATH),
            )
            if value != default
        ]
        if overridden:
            parser.error(f"--from cannot be combined with {' '.join(overridden)} — pick one")
        args.config, args.file, args.state_file = resolve_run_dir(args.from_dir)

    return args


def load_jsonl(path: Path, required: bool = True) -> list[dict[str, Any]]:
    if not path.exists():
        if required:
            raise SystemExit(
                f"File not found: {path.resolve()}\n  Run python -m src.main first to create it"
            )
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def build_timeline(
    events: list[dict[str, Any]],
    windows: list[dict[str, Any]],
    thresholds: TrafficThresholds,
    camera_id: str,
) -> list[dict[str, Any]]:
    """รวม 2 สายเป็นไทม์ไลน์เดียว เรียงตามเวลาในวิดีโอ

    spawn event ใช้เวลาที่รถข้ามเส้น ส่วน traffic state ใช้เวลา "ปลาย" ของหน้าต่าง
    (เพราะกว่าจะสรุปได้ต้องดูจนจบช่วงนั้นก่อน)
    """
    timeline: list[dict[str, Any]] = [
        {"videoTimeSec": event["videoTimeSec"], "kind": KIND_SPAWN, "payload": event}
        for event in events
    ]

    # เก็บผลตัดสินไว้ แต่ **ยังไม่ประกอบ payload** — timestamp ต้องเป็นเวลาที่ส่งจริง
    # ไม่ใช่เวลาที่สร้างไทม์ไลน์ ไม่งั้นทุกก้อนจะได้เวลาเดียวกันหมดทั้งที่ส่งห่างกันเป็นนาที
    for raw in windows:
        window = window_from_dict(raw)
        timeline.append(
            {
                "videoTimeSec": window.window_end_sec,
                "kind": KIND_STATE,
                "window": window,
                "state": classify(window, thresholds),
                "zoneStates": classify_zones(window, thresholds),
            }
        )

    timeline.sort(key=lambda item: item["videoTimeSec"])
    return timeline


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        raw_config = config.load_yaml_config(args.config)
        _, thresholds = config.parse_traffic_state(raw_config.get("traffic_state"), args.config)
    except config.ConfigError as exc:
        # ข้อความบอกวิธีแก้อยู่แล้ว — traceback มีแต่จะกลบมันเฉย ๆ
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    camera_id = str(raw_config.get("camera_id", DEFAULT_CAMERA_ID))

    events = load_jsonl(args.file)
    windows = load_jsonl(args.state_file, required=False)
    timeline = build_timeline(events, windows, thresholds, camera_id)

    if not timeline:
        print("[replay] Nothing to replay")
        return 0

    span = timeline[-1]["videoTimeSec"] - timeline[0]["videoTimeSec"]
    if args.from_dir is not None:
        print(f"[replay] Dataset: {args.from_dir}")
    print(f"[replay] {len(events)} spawn events | {len(windows)} traffic-state windows")
    if not windows:
        print(f"[replay] WARNING: no {args.state_file.name} — spawn events only, no traffic state")
    print(f"[replay] Video time span: {span:.2f} s")
    print(
        f"[replay] Thresholds: busy_occupancy={thresholds.busy_occupancy} "
        f"standstill_flow={thresholds.standstill_flow} slow_flow={thresholds.slow_flow}"
    )
    if args.fast:
        print("[replay] --fast mode: no pacing delay")
    if args.backend:
        print(f"[replay] Posting to backend at {args.backend_url}")
    else:
        # เคยมีคนงงว่าทำไม dashboard ไม่ขึ้นสถานะ — โหมดนี้พิมพ์อย่างเดียว ต้องบอกให้ชัด
        print("[replay] Print-only mode — nothing is sent anywhere")
        print("         Add --backend so the dashboard / Unity can see it")
    print()

    poster = BackendPoster(args.backend_url) if args.backend else None
    if poster is not None:
        # ล้างก่อนส่ง เพื่อให้ไฟล์ capture + ตัวนับบน dashboard = ผลของรอบนี้รอบเดียว
        # ล้มเหลวก็ไปต่อได้ แต่ต้องบอกให้ชัดว่าตัวเลขที่เห็นจะรวมรอบก่อนด้วย
        if not poster.reset_session():
            print("[replay] WARNING: backend was not reset — output will include earlier runs")
            print()

    states = Counter()

    def handle(item: dict[str, Any]) -> None:
        if item["kind"] == KIND_STATE:
            # ประกอบ payload ตรงนี้ -> timestamp = เวลาที่ส่งจริง ตรงตาม data-contract
            payload = to_traffic_state_payload(
                item["window"], item["state"], item["zoneStates"], camera_id=camera_id
            )
            states[payload["trafficState"]] += 1
            # veh = รถยนต์/บรรทุก/บัส (ใช้ตัดสิน) · mc = มอเตอร์ไซค์ (แสดงให้ดูเฉย ๆ)
            # [...] = คำตัดสินของโซนนั้นเอง — ถนน 2 ฝั่งติดไม่พร้อมกัน ต้องเห็นแยก
            zones = "  ".join(
                f"{name}[{z.get('trafficState', '?').upper()}]"
                f"(occ={z['occupancy']:.2f} "
                f"veh={z['vehicleFlowRate']:.1f} mc={z['motorcycleFlowRate']:.1f})"
                for name, z in payload["zones"].items()
            )
            print(
                f"[{payload['windowStartSec']:6.1f}-{payload['windowEndSec']:6.1f}s] "
                f"{payload['trafficState'].upper():<13} {zones}"
            )
            if poster is not None:
                poster.post_traffic_state(payload)
        else:
            # timestamp ในไฟล์คือเวลาที่ "ตรวจพบ" ตอนรัน main.py (อาจเป็นสัปดาห์ก่อน)
            # replay คือการจำลองสายสด จึงประทับเวลาใหม่ให้ตรงกับตอนส่ง
            # เวลาในวิดีโอยังอยู่ครบที่ videoTimeSec / frameCount
            payload = {**item["payload"], "timestamp": iso_timestamp()}
            print(f"  spawn {payload['trackId']:>18}  {payload['type']:<11} {payload['direction']}")
            if poster is not None:
                poster.post(payload)

    if args.fast:
        for item in timeline:
            handle(item)
    else:
        replay_paced(timeline, handle)

    print()
    if states:
        print("Traffic-state summary for the whole clip:")
        for state, n in states.most_common():
            print(f"  {state:<13} {n:3d} windows  ({n / sum(states.values()) * 100:.0f}%)")
    if poster is not None:
        print(f"\n[replay] Posted to backend: {poster.sent} ok | {poster.failed} failed")
        poster.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
