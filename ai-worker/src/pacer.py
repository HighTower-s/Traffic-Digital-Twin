"""จัดจังหวะการส่ง event ให้ตรงกับเวลาจริงในวิดีโอต้นฉบับ

ใช้เฉพาะตอนเดโมด้วยไฟล์วิดีโอ (Prototype) — เมื่อเปลี่ยนเป็นกล้องสด (RTSP) ในอนาคต
โมดูลนี้จะไม่จำเป็นอีกต่อไป เพราะไม่มี "เส้นเวลาที่บันทึกไว้ล่วงหน้า" ให้ pace ตาม
(ทุกอย่างเกิดสด real-time โดยธรรมชาติอยู่แล้ว)

หลักการ: ผูกกับจุดเริ่มต้นคงที่ (playback_start, videoTimeSec ของ event แรก) เสมอ
ไม่ผูกกับ event ก่อนหน้า — กันความคลาดเคลื่อนสะสม (drift) จากเวลาที่กินไปตอนส่งแต่ละ event
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from typing import Any


def replay_paced(
    events: Iterable[dict[str, Any]],
    on_event: Callable[[dict[str, Any]], None],
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], float] = time.monotonic,
) -> None:
    """เรียก on_event(event) ตามจังหวะ videoTimeSec จริง ไม่สะสมความคลาดเคลื่อน

    sleep_fn/now_fn ใส่เองได้เพื่อเทสโดยไม่ต้องรอเวลาจริง (ดู tests/test_pacer.py)
    ใช้ time.monotonic() ไม่ใช่ time.time() — เดินหน้าอย่างเดียว ไม่โดนกระทบถ้านาฬิการะบบถูกปรับ
    """
    events = list(events)
    if not events:
        return

    playback_start = now_fn()
    first_video_time = events[0]["videoTimeSec"]

    for event in events:
        target_elapsed = event["videoTimeSec"] - first_video_time
        actual_elapsed = now_fn() - playback_start
        wait = target_elapsed - actual_elapsed
        if wait > 0:
            sleep_fn(wait)
        on_event(event)
