"""เทส pacer.py — ใช้นาฬิกาจำลอง (FakeClock) แทนเวลาจริง ไม่ต้องรอวินาทีจริงเลย"""

from src.pacer import replay_paced


class FakeClock:
    """now()/sleep() จำลอง — sleep() แค่เดินนาฬิกาไปข้างหน้า ไม่รอจริง"""

    def __init__(self) -> None:
        self.value = 0.0
        self.sleep_calls: list[float] = []

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.value += seconds

    def advance(self, seconds: float) -> None:
        """จำลองว่า on_event (เช่นส่งเข้า backend) กินเวลาไปเท่านี้"""
        self.value += seconds


def make_event(video_time: float, **overrides) -> dict:
    event = {"videoTimeSec": video_time, "trackId": f"car-{video_time}"}
    event.update(overrides)
    return event


def test_empty_events_does_nothing():
    clock = FakeClock()
    calls: list[dict] = []
    replay_paced([], calls.append, sleep_fn=clock.sleep, now_fn=clock.now)
    assert calls == []
    assert clock.sleep_calls == []


def test_single_event_sent_immediately_no_wait():
    clock = FakeClock()
    calls: list[dict] = []
    replay_paced([make_event(2.0)], calls.append, sleep_fn=clock.sleep, now_fn=clock.now)
    assert len(calls) == 1
    assert clock.sleep_calls == []  # event แรกไม่มีอะไรให้รอ


def test_events_passed_through_unchanged():
    clock = FakeClock()
    calls: list[dict] = []
    events = [make_event(2.0, type="car"), make_event(3.0, type="bus")]
    replay_paced(events, calls.append, sleep_fn=clock.sleep, now_fn=clock.now)
    assert calls == events


def test_waits_match_video_time_deltas_when_sending_is_instant():
    clock = FakeClock()
    landing_times: list[float] = []

    def on_event(event: dict) -> None:
        landing_times.append(clock.now())

    events = [make_event(2.0), make_event(3.0), make_event(3.5), make_event(6.0)]
    replay_paced(events, on_event, sleep_fn=clock.sleep, now_fn=clock.now)

    # เทียบกับ videoTimeSec ของ event แรก (2.0): ควรลงเวลาไว้ที่ 0.0, 1.0, 1.5, 4.0
    assert landing_times == [0.0, 1.0, 1.5, 4.0]


def test_no_drift_accumulates_when_sending_takes_real_time():
    """ตัวอย่างเดียวกับที่อธิบายให้ผู้ใช้ฟัง — ส่งแต่ละ event กินเวลาจริง 0.3 วิ
    ทุก event ต้องยังลงเวลาให้ตรง target แม้เวลาส่งจะกินเวลาไปด้วยก็ตาม (ไม่สะสมความคลาดเคลื่อน)
    """
    clock = FakeClock()
    landing_times: list[float] = []

    def on_event(event: dict) -> None:
        landing_times.append(clock.now())
        clock.advance(0.3)  # จำลองว่าส่งเข้า backend กินเวลา 0.3 วิ

    events = [make_event(2.0), make_event(3.0), make_event(3.5), make_event(6.0)]
    replay_paced(events, on_event, sleep_fn=clock.sleep, now_fn=clock.now)

    assert landing_times == [0.0, 1.0, 1.5, 4.0]


def test_falling_behind_sends_immediately_without_negative_sleep():
    """ถ้า event ควรจะส่งไปแล้วตั้งแต่เมื่อครู่ (wait <= 0) ให้ส่งทันที ไม่ sleep ติดลบ"""
    clock = FakeClock()
    landing_times: list[float] = []

    def on_event(event: dict) -> None:
        landing_times.append(clock.now())
        clock.advance(2.0)  # ส่งช้ามาก กินเวลา 2 วิ ทำให้ event ถัดไปตามหลังทันที

    events = [make_event(0.0), make_event(1.0), make_event(1.5)]
    replay_paced(events, on_event, sleep_fn=clock.sleep, now_fn=clock.now)

    # event 2 (videoTime=1.0) ควรอยู่ที่ T=1.0 แต่พอถึงคิวจริง T=2.0 ไปแล้ว (ตามหลัง)
    # => ส่งทันทีไม่รอ, ไม่มี sleep ติดลบ
    assert landing_times == [0.0, 2.0, 4.0]
    assert all(s >= 0 for s in clock.sleep_calls)
