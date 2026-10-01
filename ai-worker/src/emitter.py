"""แปลง CountEvent เป็น spawn event ที่ "จะ" ส่งให้ Unity/backend ในอนาคต

**เวอร์ชันนี้ไม่ส่งไปไหน** แค่ print ให้ดูและเขียนลง data/output_results/events.jsonl

การสร้าง payload (`to_spawn_event`) บริสุทธิ์: รับตัวเลข คืน dict ไม่แตะไฟล์
ทดสอบได้โดยไม่ต้องมีวิดีโอ ส่วน SpawnEventWriter เป็นเปลือกบาง ๆ ที่ทำ I/O อย่างเดียว
รูปแบบ payload จึงถูกล็อกด้วยเทส ไม่ใช่ตรวจด้วยตาตอนรัน

**ไม่มี `lane` และ `speed`** (ตัดออก 2026-08-09) — ทั้งคู่วัดจากภาพจริงไม่ได้ในเวอร์ชันนี้
เพิ่มกลับเป็นงานแยกเมื่อมีวิธีวัดที่เชื่อถือได้ (ดู ai-worker/CLAUDE.md §5)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any, TextIO

from src.constants import DEFAULT_CAMERA_ID, SPAWN_EVENT_SCHEMA
from src.counter import CountEvent
from src.timeutil import iso_timestamp

# ปัดเศษก่อนส่งออก: เลขทศนิยม 15 ตำแหน่งไม่ได้ให้ข้อมูลเพิ่ม แต่ทำให้ log อ่านยาก
CONFIDENCE_DIGITS = 3
TIME_DIGITS = 6


def to_spawn_event(
    event: CountEvent,
    fps: float,
    camera_id: str = DEFAULT_CAMERA_ID,
    now: datetime | None = None,
) -> dict[str, Any]:
    """สร้าง payload 1 คัน — ไม่มี lane/speed (ดู module docstring)"""
    # fps = 0 เกิดได้จริงกับวิดีโอบางไฟล์ที่ metadata เสีย — ห้ามหารด้วยศูนย์กลางรัน
    video_time = round(event.frame_index / fps, TIME_DIGITS) if fps > 0 else 0.0

    return {
        "schema": SPAWN_EVENT_SCHEMA,
        "timestamp": iso_timestamp(now),
        "cameraId": camera_id,
        "videoTimeSec": video_time,
        "frameCount": event.frame_index,
        "trackId": f"{event.vehicle_type}-{event.track_id:04d}",
        "type": event.vehicle_type,
        # ชื่อโซน = in/out ที่ผู้ตั้งค่ากำหนดเอง ไม่ใช่ toward/away ที่ขึ้นกับมุมกล้อง
        # (ดูเหตุผลเต็มที่ constants.IO_DIRECTIONS)
        "direction": event.zone,
        "confidence": round(event.confidence, CONFIDENCE_DIGITS),
    }


class SpawnEventWriter:
    """เขียน spawn event ลง .jsonl ทีละบรรทัด และ (ถ้าเปิด) print ให้ดูสด ๆ

    ใช้ .jsonl ไม่ใช่ .json เพราะเขียนต่อท้ายได้ทีละบรรทัด ปิดโปรแกรมกลางคัน
    แล้วไฟล์ยังอ่านได้ทั้งหมด ต่างจาก JSON array ที่ต้องมีวงเล็บปิดถึงจะ parse ผ่าน
    """

    def __init__(
        self,
        path: Path,
        fps: float,
        camera_id: str = DEFAULT_CAMERA_ID,
        echo: bool = True,
        echo_limit: int | None = None,
    ) -> None:
        self._path = Path(path)
        self._fps = fps
        self._camera_id = camera_id
        self._echo = echo
        self._echo_limit = echo_limit
        self._handle: TextIO | None = None
        self.emitted = 0
        self._echoed = 0

    def open(self) -> SpawnEventWriter:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self._path.open("w", encoding="utf-8")
        return self

    def emit(self, event: CountEvent) -> dict[str, Any]:
        if self._handle is None:
            self.open()
        assert self._handle is not None  # ช่วย type checker หลัง open()

        payload = to_spawn_event(event, fps=self._fps, camera_id=self._camera_id)
        line = json.dumps(payload, ensure_ascii=False)

        self._handle.write(line + "\n")
        # flush ทุกบรรทัด: รันแล้วเครื่องค้าง/กด Ctrl-C ต้องไม่เสียข้อมูลที่นับมาแล้ว
        self._handle.flush()
        self.emitted += 1

        if self._echo and (self._echo_limit is None or self._echoed < self._echo_limit):
            print(line, flush=True)
            self._echoed += 1
            if self._echo_limit is not None and self._echoed == self._echo_limit:
                print(
                    f"  … ถึงขีด emit_preview {self._echo_limit} แล้ว "
                    f"หยุด print แต่ยังเขียนครบทุกคันลง {self._path}",
                    flush=True,
                )

        return payload

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> SpawnEventWriter:
        return self.open()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
