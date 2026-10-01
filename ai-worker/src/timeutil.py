"""รูปแบบเวลาที่ใช้ในทุก payload — รวมไว้ที่เดียวกันหลุด

`docs/data-contract.md` กำหนดว่า `timestamp` คือ ISO 8601 UTC ลงท้ายด้วย `Z`
และหมายถึง **เวลาที่ส่ง payload ออกไป** ไม่ใช่เวลาที่ประมวลผล
"""

from __future__ import annotations

from datetime import datetime, timezone


def iso_timestamp(now: datetime | None = None) -> str:
    """คืนเวลาแบบ `2026-09-01T09:15:55.123Z`

    ฉีด now เองได้เพื่อให้เทสไม่ขึ้นกับนาฬิกาจริง
    ใช้ timezone.utc ไม่ใช่ datetime.UTC เพราะ alias นั้นมีเฉพาะ Python 3.11+
    """
    moment = now or datetime.now(timezone.utc)  # noqa: UP017
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")
