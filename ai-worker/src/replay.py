"""เล่นซ้ำผลที่ main.py ตรวจจับไว้ ตามจังหวะเวลาจริงของวิดีโอต้นฉบับ

    python -m src.replay                 ดูอย่างเดียว ตามจังหวะจริง (ไม่ส่งเข้า backend)
    python -m src.replay --backend       ส่งเข้า backend ด้วย (ต้องรัน backend ไว้ก่อน)
    python -m src.replay --fast          ไม่หน่วงเวลา — ใช้ตอนจูนเกณฑ์ จะได้เห็นผลทันที

อ่าน 2 ไฟล์ที่ main.py สร้างไว้ แล้วส่งเป็น 2 สายคู่ขนานตามเวลาเดียวกัน:
  events.jsonl        -> spawn event (รถ 1 คันข้ามเส้น)      -> POST /api/ingest
  traffic_state.jsonl -> สถานะจราจร (สรุปทุก window_sec)      -> POST /api/traffic-state

**การตัดสินสถานะเกิดที่นี่ ไม่ใช่ตอน main.py** เพราะการวัดแพง (ต้องรัน YOLO ทั้งคลิป)
แต่การตัดสินถูกมากและต้องปรับเกณฑ์บ่อย -> แก้เกณฑ์ใน config.yaml แล้วรันไฟล์นี้ใหม่
ได้เลยโดยไม่ต้องรัน YOLO ซ้ำ (ดู ai-worker/CLAUDE.md)
"""

from __future__ import annotations

import argparse
import json
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
DEFAULT_CONFIG_PATH = AI_WORKER_ROOT / "config.yaml"

KIND_SPAWN = "spawn"
KIND_STATE = "state"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="เล่นซ้ำ events.jsonl + traffic_state.jsonl ตามจังหวะเวลาจริง"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--file", type=Path, default=DEFAULT_EVENTS_PATH, help="path ไปยัง events.jsonl"
    )
    parser.add_argument(
        "--state-file", type=Path, default=DEFAULT_STATE_PATH, help="path ไปยัง traffic_state.jsonl"
    )
    parser.add_argument(
        "--backend", action="store_true", help="ส่งเข้า backend ด้วย (ไม่ใช่แค่พิมพ์)"
    )
    parser.add_argument("--backend-url", default=DEFAULT_BACKEND_URL)
    parser.add_argument(
        "--fast",
        action="store_true",
        help="ไม่หน่วงเวลาตามจังหวะวิดีโอ — ใช้ตอนจูนเกณฑ์ จะได้เห็นผลทันที",
    )
    return parser.parse_args(argv)


def load_jsonl(path: Path, required: bool = True) -> list[dict[str, Any]]:
    if not path.exists():
        if required:
            raise SystemExit(
                f"ไม่พบไฟล์: {path.resolve()}\n  รัน python -m src.main ก่อนเพื่อสร้างไฟล์นี้"
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
    args = parse_args(argv)

    raw_config = config.load_yaml_config(args.config)
    _, thresholds = config.parse_traffic_state(raw_config.get("traffic_state"), args.config)
    camera_id = str(raw_config.get("camera_id", DEFAULT_CAMERA_ID))

    events = load_jsonl(args.file)
    windows = load_jsonl(args.state_file, required=False)
    timeline = build_timeline(events, windows, thresholds, camera_id)

    if not timeline:
        print("[replay] ไม่มีอะไรให้เล่นซ้ำ")
        return 0

    span = timeline[-1]["videoTimeSec"] - timeline[0]["videoTimeSec"]
    print(f"[replay] spawn event {len(events)} รายการ | สถานะจราจร {len(windows)} ช่วง")
    print(f"[replay] ช่วงเวลาตามวิดีโอ: {span:.2f} วินาที")
    print(
        f"[replay] เกณฑ์: busy_occupancy={thresholds.busy_occupancy} "
        f"standstill_flow={thresholds.standstill_flow} slow_flow={thresholds.slow_flow}"
    )
    if args.fast:
        print("[replay] โหมด --fast: ไม่หน่วงเวลา")
    if args.backend:
        print(f"[replay] ส่งเข้า backend ที่ {args.backend_url}")
    else:
        # เคยมีคนงงว่าทำไม dashboard ไม่ขึ้นสถานะ — โหมดนี้พิมพ์อย่างเดียว ต้องบอกให้ชัด
        print("[replay] โหมดดูอย่างเดียว — ไม่ได้ส่งออกไปไหน")
        print("         ใส่ --backend ถ้าต้องการให้ dashboard / Unity เห็น")
    print()

    poster = BackendPoster(args.backend_url) if args.backend else None
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
        print("สรุปสถานะจราจรตลอดคลิป:")
        for state, n in states.most_common():
            print(f"  {state:<13} {n:3d} ช่วง  ({n / sum(states.values()) * 100:.0f}%)")
    if poster is not None:
        print(f"\n[replay] ส่งเข้า backend: {poster.sent} สำเร็จ | {poster.failed} ล้มเหลว")
        poster.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
