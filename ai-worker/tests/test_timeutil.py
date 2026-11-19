"""เทสรูปแบบ timestamp — ต้องตรงกับ docs/data-contract.md เป๊ะ"""

from datetime import UTC, datetime, timedelta

from src.timeutil import iso_timestamp


def test_format_matches_data_contract():
    moment = datetime(2026, 9, 1, 9, 15, 55, 123000, tzinfo=UTC)
    assert iso_timestamp(moment) == "2026-09-01T09:15:55.123Z"


def test_always_ends_with_z_not_plus_offset():
    """Unity/JS parse ได้ทั้งคู่ แต่สัญญาระบุ Z — ห้ามหลุดเป็น +00:00"""
    assert iso_timestamp(datetime(2026, 1, 1, tzinfo=UTC)).endswith("Z")
    assert "+00:00" not in iso_timestamp(datetime(2026, 1, 1, tzinfo=UTC))


def test_keeps_milliseconds_only():
    """ไมโครวินาทีถูกตัดเหลือ 3 ตำแหน่ง — ไม่งั้นความยาวสตริงไม่คงที่"""
    moment = datetime(2026, 9, 1, 9, 15, 55, 123456, tzinfo=UTC)
    assert iso_timestamp(moment) == "2026-09-01T09:15:55.123Z"


def test_different_moments_give_different_strings():
    """กันบั๊กเดิม: ทุก payload เคยได้ timestamp เดียวกันเพราะประทับเวลาพร้อมกันทีเดียว"""
    base = datetime(2026, 9, 1, 9, 0, 0, tzinfo=UTC)
    assert iso_timestamp(base) != iso_timestamp(base + timedelta(seconds=20))


def test_defaults_to_now_when_not_injected():
    stamped = iso_timestamp()
    assert stamped.endswith("Z")
    assert len(stamped) == len("2026-09-01T09:15:55.123Z")
