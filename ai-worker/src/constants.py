"""ค่าคงที่ทั้งหมดของ AI Worker — ห้าม hardcode ตัวเลข/ชื่อซ้ำที่ไฟล์อื่น

บทเรียนจากโค้ดชุดก่อน (bug 2026-07-21): ค่าเดียวกันถูกเขียนไว้หลายที่แล้วหลุดกัน
เวอร์ชันนี้จึงรวมค่า invariant (ไม่เปลี่ยนตามคลิป) ไว้ที่เดียว ส่วนค่าที่ปรับต่อคลิป
(path วิดีโอ, conf, imgsz, ...) อยู่ใน config.yaml แทน
"""

from typing import Final

# ---------------------------------------------------------------- ชนิดรถ

# COCO class id -> ชนิดรถที่สนใจ
# bicycle (1) ตัดออกตั้งใจ: ไม่ใช่ยานยนต์ และมักถูกสับสนกับมอเตอร์ไซค์
COCO_TO_TYPE: Final[dict[int, str]] = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}
VEHICLE_CLASS_IDS: Final[list[int]] = sorted(COCO_TO_TYPE)
VEHICLE_TYPES: Final[tuple[str, ...]] = ("car", "motorcycle", "bus", "truck")

# แยกมอเตอร์ไซค์ออกจากชนิดอื่นตอนวัด "อัตราการไหล" (ดู traffic_state.py)
# เหตุผล: มอเตอร์ไซค์มุดผ่านช่องว่างระหว่างรถที่จอดติดได้ จึงยังข้ามเส้นเรื่อย ๆ
# แม้รถยนต์จะหยุดสนิท -> ถ้านับรวมกัน มอเตอร์ไซค์จะกลบสัญญาณรถติดจนไม่เห็น standstill
# (พิสูจน์กับคลิปจริง 2026-09-02: ช่วงที่รถยนต์ข้าม 0 คัน มอเตอร์ไซค์ข้าม 4 คัน)
MOTORCYCLE_TYPE: Final[str] = "motorcycle"
FLOW_VEHICLE_TYPES: Final[tuple[str, ...]] = ("car", "bus", "truck")

# ---------------------------------------------------------------- ทิศทาง

# กล้องอยู่บนสะพานลอยมองตามแนวถนน
# รถเข้าหากล้อง = เลื่อนลงล่างในภาพ = toward (IN)
# รถออกจากกล้อง = เลื่อนขึ้นบนในภาพ = away (OUT)
DIRECTION_TOWARD: Final[str] = "toward"
DIRECTION_AWAY: Final[str] = "away"
DIRECTIONS: Final[tuple[str, str]] = (DIRECTION_TOWARD, DIRECTION_AWAY)

# ชื่อทิศที่ใช้ใน payload ที่ส่งออก — เป็นภาษาที่ทีม Unity กับอาจารย์ใช้
#
# **in/out มาจาก "ชื่อโซน" ไม่ใช่จาก toward/away** เพราะ toward/away บอกแค่ว่ารถเคลื่อนที่
# ไปทางไหน "ในภาพ" ซึ่งขึ้นกับว่ากล้องหันทางไหน ไม่ได้บอกว่าเข้าหรือออกจากสถานที่จริง
# กล้องคนละมุมจะให้คำตอบตรงข้ามกันทั้งที่เป็นถนนเส้นเดียวกัน — ผู้ตั้งค่าจึงเป็นคนบอกเอง
# ผ่านชื่อโซนใน config.yaml (ดู emitter.to_spawn_event)
#
# ไม่เสียข้อมูลอะไร: รถที่ข้ามผิดทิศถูกปฏิเสธไปแล้วตั้งแต่ counter (wrong_direction)
# ดังนั้นรถที่นับได้ทุกคันมีทิศตรงกับ expectedDirection ของโซนตัวเองเสมอ
IO_DIRECTIONS: Final[tuple[str, str]] = ("in", "out")

# ---------------------------------------------------------------- anomaly

# เหตุผลที่ปฏิเสธการนับ — เขียนลง anomalies.csv เพื่อไล่หาว่าเลขหายไปไหน
REASON_WRONG_DIRECTION: Final[str] = "wrong_direction"
REASON_OUTSIDE_POLYGON: Final[str] = "outside_polygon"
REASON_ALREADY_COUNTED: Final[str] = "already_counted"
REASON_NO_TYPE_VOTES: Final[str] = "no_type_votes"

# ---------------------------------------------------------------- ค่ารันเริ่มต้น

# ใช้เป็นค่า default ถ้า config.yaml ไม่ได้ระบุ (override ได้ผ่าน config.yaml)
DEFAULT_MODEL: Final[str] = "data/weights/yolov8s.pt"
DEFAULT_TRACKER: Final[str] = "bytetrack.yaml"
DEFAULT_IMGSZ: Final[int] = 640
DEFAULT_CONF_THRESHOLD: Final[float] = 0.35

# เตือนเมื่อผ่านไปเท่านี้เฟรมแล้วยังนับไม่ได้เลย -> มักแปลว่า zone/line วางผิด
ZERO_COUNT_WARN_FRAMES: Final[int] = 500

# ล้าง track ที่หายไปนาน กันหน่วยความจำโตไม่จำกัดในวิดีโอยาว
PRUNE_EVERY_FRAMES: Final[int] = 300
TRACK_TTL_FRAMES: Final[int] = 150

# ความยาวด้านที่ยาวที่สุดของหน้าต่างที่แสดง (ภาพจริง 1920x1080 ใหญ่เกินจอโน้ตบุ๊ก)
DISPLAY_MAX_SIDE: Final[int] = 1280

# ---------------------------------------------------------------- payload

# กล้องตัวเดียวใน MVP — ตรงกับ cameraId ใน docs/data-contract.md
DEFAULT_CAMERA_ID: Final[str] = "cam-chalongkrung-01"

# เวอร์ชันของ spawn event — 0.2 เพราะตัด lane/speed ออกจาก 0.1-draft เดิม (2026-08-09)
SPAWN_EVENT_SCHEMA: Final[str] = "spawn-event/0.2-draft"

TRAFFIC_STATE_SCHEMA: Final[str] = "traffic-state/0.1-draft"

# ---------------------------------------------------------------- สถานะจราจร

# ตัดสินจาก 2 ค่า: occupancy (รถในโซน = ความหนาแน่น) และ flow (รถข้ามเส้น/นาที)
# เพราะ Flow = Density × Speed -> ถ้าดู flow อย่างเดียว "รถติดสนิท" (speed=0)
# กับ "ถนนว่าง" (density=0) จะได้ 0 เท่ากัน แยกไม่ออก
STATE_NORMAL: Final[str] = "normal"
STATE_HIGH_DENSITY: Final[str] = "high_density"
STATE_SLOW_MOVING: Final[str] = "slow_moving"
STATE_STANDSTILL: Final[str] = "standstill"
TRAFFIC_STATES: Final[tuple[str, ...]] = (
    STATE_NORMAL,
    STATE_HIGH_DENSITY,
    STATE_SLOW_MOVING,
    STATE_STANDSTILL,
)

# ค่าเริ่มต้น — override ได้ใน config.yaml ใต้ traffic_state:
# **ยังไม่ได้จูนกับคลิปรถติดจริง** ตัวเลขวัดจาก traffic-5 (จราจรปกติ) คือ
# occupancy 0.2-1.1 / flow 12-36 ด้วย polygon นับเดิม — ต้องวัดใหม่หลังวาด
# occupancyPolygon ที่ครอบถนนยาวขึ้น
DEFAULT_WINDOW_SEC: Final[float] = 10.0
DEFAULT_BUSY_OCCUPANCY: Final[float] = 3.0  # occupancy เกินนี้ = หนาแน่น
DEFAULT_STANDSTILL_FLOW: Final[float] = 2.0  # คัน/นาที ต่ำกว่านี้ + หนาแน่น = ติดสนิท
DEFAULT_SLOW_FLOW: Final[float] = 12.0  # คัน/นาที ต่ำกว่านี้ + หนาแน่น = เคลื่อนตัวช้า

# backend รันเครื่องเดียวกันในเวอร์ชัน prototype — ตรงกับ backend/.env.example PORT=3000
DEFAULT_BACKEND_URL: Final[str] = "http://localhost:3000"

# ---------------------------------------------------------------- สี (BGR)

# OpenCV ใช้ BGR ไม่ใช่ RGB
COLOR_BY_TYPE: Final[dict[str, tuple[int, int, int]]] = {
    "car": (0, 200, 255),
    "motorcycle": (255, 160, 0),
    "bus": (0, 255, 120),
    "truck": (200, 80, 255),
}
COLOR_UNKNOWN: Final[tuple[int, int, int]] = (160, 160, 160)
COLOR_ZONE: Final[tuple[int, int, int]] = (120, 120, 120)
COLOR_LINE: Final[dict[str, tuple[int, int, int]]] = {
    DIRECTION_TOWARD: (80, 220, 120),
    DIRECTION_AWAY: (245, 165, 36),
}
COLOR_HUD_BG: Final[tuple[int, int, int]] = (20, 24, 30)
COLOR_HUD_TEXT: Final[tuple[int, int, int]] = (230, 237, 243)
COLOR_WARN: Final[tuple[int, int, int]] = (60, 60, 240)
