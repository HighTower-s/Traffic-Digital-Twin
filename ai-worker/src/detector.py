"""ครอบ YOLO + ByteTrack ให้คืน Detection ธรรมดา

ultralytics และ torch ถูก import แบบ lazy (ตอนสร้างออบเจกต์ ไม่ใช่ตอน import โมดูล)
เพื่อให้ `detections_from_arrays` ทดสอบได้โดยไม่ต้องลงไลบรารีหนัก และเพื่อให้
เครื่องที่ยังไม่ได้ลง ultralytics ยังรัน pytest ชุดเต็มได้

detect และ track รวมเป็นไฟล์เดียวโดยตั้งใจ: ultralytics `YOLO.track()` ทำ detection
กับ ByteTrack ในคอลเดียวกันอยู่แล้ว การแยกไฟล์จะสร้างเส้นแบ่งปลอมที่ไม่มีอยู่จริงในไลบรารี
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from src.constants import VEHICLE_CLASS_IDS
from src.counter import Detection

HERE = Path(__file__).parent
# ที่ที่ไปหาไฟล์โมเดล เรียงตามลำดับความสำคัญ
MODEL_SEARCH_DIRS = (
    HERE.parent / "data" / "weights",  # ai-worker/data/weights/
    HERE.parent,  # ai-worker/
    Path.cwd(),  # ที่รันคำสั่งอยู่
)


class DetectorError(Exception):
    """โหลดโมเดลหรือรัน inference ไม่สำเร็จ — ต้องบอกว่าติดตรงไหนและแก้ยังไง"""


def resolve_model_path(model: str, search_dirs: Sequence[Path] = MODEL_SEARCH_DIRS) -> str:
    """หาไฟล์โมเดลจากหลายที่ ก่อนจะปล่อยให้ ultralytics ดาวน์โหลดใหม่

    path เต็มหรือ path ที่ชี้ไปไฟล์จริงอยู่แล้ว ใช้ตามนั้นเลย
    """
    given = Path(model)
    if given.is_absolute() or given.exists():
        return str(given)

    for directory in search_dirs:
        candidate = directory / given.name
        if candidate.exists():
            return str(candidate)

    # ไม่เจอที่ไหนเลย — คืนชื่อเดิมให้ ultralytics ดาวน์โหลดเอง (ทำได้ ไม่ใช่ error)
    return model


def detections_from_arrays(
    boxes: Sequence[Sequence[float]],
    track_ids: Sequence[int] | None,
    class_ids: Sequence[int],
    confidences: Sequence[float],
) -> list[Detection]:
    """แปลงผลดิบจาก YOLO เป็น Detection

    แยกออกมาเป็นฟังก์ชันบริสุทธิ์เพราะการแปลงนี้คือจุดที่พลาดง่ายที่สุด
    (ลืม .cpu(), ลืมว่า id เป็น None ตอนไม่มี track, ลำดับคอลัมน์สลับ)
    และทดสอบได้โดยไม่ต้องมี GPU

    track_ids เป็น None ได้จริงเมื่อ ByteTrack ยังไม่ผูก id ให้เฟรมแรก ๆ
    กรณีนั้นข้ามทั้งเฟรม ดีกว่าเดา id เอง ซึ่งจะทำให้นับซ้ำ
    """
    if track_ids is None:
        return []

    detections: list[Detection] = []
    for box, track_id, class_id, conf in zip(boxes, track_ids, class_ids, confidences, strict=True):
        x1, y1, x2, y2 = (float(v) for v in box)
        detections.append(
            Detection(
                track_id=int(track_id),
                class_id=int(class_id),
                conf=float(conf),
                box=(x1, y1, x2, y2),
            )
        )
    return detections


def detections_from_result(result: Any) -> list[Detection]:
    """ดึงข้อมูลจาก ultralytics Results หนึ่งตัว"""
    boxes = getattr(result, "boxes", None)
    if boxes is None or boxes.id is None:
        return []
    return detections_from_arrays(
        boxes=boxes.xyxy.cpu().tolist(),
        track_ids=boxes.id.int().cpu().tolist(),
        class_ids=boxes.cls.int().cpu().tolist(),
        confidences=boxes.conf.cpu().tolist(),
    )


def resolve_device(preference: str = "auto") -> str:
    """เลือก device ตามที่ ไฟล์ config ระบุ และ **เตือนดัง ๆ** ถ้าตกไป CPU

    การตกไป CPU เงียบ ๆ ทำให้เข้าใจผิดว่า "โปรแกรมช้า" ทั้งที่จริงคือติดตั้ง torch ผิดรุ่น
    """
    if preference == "cpu":
        return "cpu"
    if preference not in ("auto", "0"):
        return preference  # ผู้ใช้ระบุ device id เอง (เช่น "1" สำหรับ GPU ตัวที่สอง)

    try:
        import torch
    except ImportError:
        print("[warn] torch not found — falling back to CPU, which is much slower")
        return "cpu"

    if torch.cuda.is_available():
        return "0"

    print(
        "[warn] torch.cuda.is_available() = False — running on CPU (several times slower)\n"
        "       If this machine has an NVIDIA GPU, the installed torch is a CPU-only build\n"
        "       Install the CUDA build: pip install torch --index-url "
        "https://download.pytorch.org/whl/cu128"
    )
    return "cpu"


class VehicleDetector:
    """เรียก YOLO.track() ต่อเฟรม แล้วคืน list[Detection] (detect + ByteTrack รวมกัน)"""

    def __init__(
        self,
        model_path: str,
        tracker_config: str,
        imgsz: int,
        conf_threshold: float,
        device: str = "auto",
    ) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise DetectorError(
                "ultralytics library not found\n  Install it with: pip install -r requirements.txt"
            ) from exc

        resolved = resolve_model_path(model_path)
        if resolved != model_path:
            print(f"[model] Using local file: {resolved}")

        try:
            self._model = YOLO(resolved)
        except Exception as exc:
            raise DetectorError(
                f"Failed to load model {resolved!r}: {exc}\n"
                f"  Check that the .pt file exists, or let ultralytics download it"
            ) from exc

        self._tracker_config = tracker_config
        self._imgsz = imgsz
        self._conf_threshold = conf_threshold
        self.device = resolve_device(device)

    def track(self, frame: Any) -> list[Detection]:
        try:
            results = self._model.track(
                frame,
                persist=True,  # จำ track ข้ามเฟรม ถ้าไม่ใส่ id จะรีเซ็ตทุกเฟรม
                classes=VEHICLE_CLASS_IDS,  # car / motorcycle / bus / truck
                conf=self._conf_threshold,
                imgsz=self._imgsz,
                tracker=self._tracker_config,
                device=self.device,
                verbose=False,
            )
        except Exception as exc:
            raise DetectorError(f"Inference failed: {exc}") from exc

        if not results:
            return []
        return detections_from_result(results[0])
