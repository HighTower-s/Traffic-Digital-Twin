"""เทสเฉพาะส่วนที่ไม่ต้องมี ultralytics/torch จริง (detections_from_arrays)"""

from src.detector import detections_from_arrays


def test_converts_arrays_to_detections():
    detections = detections_from_arrays(
        boxes=[[10.0, 20.0, 30.0, 40.0]],
        track_ids=[7],
        class_ids=[2],
        confidences=[0.91],
    )
    assert len(detections) == 1
    d = detections[0]
    assert d.track_id == 7
    assert d.class_id == 2
    assert d.conf == 0.91
    assert d.box == (10.0, 20.0, 30.0, 40.0)


def test_returns_empty_list_when_track_ids_is_none():
    detections = detections_from_arrays(
        boxes=[[10.0, 20.0, 30.0, 40.0]],
        track_ids=None,
        class_ids=[2],
        confidences=[0.91],
    )
    assert detections == []


def test_handles_multiple_detections_in_order():
    detections = detections_from_arrays(
        boxes=[[0.0, 0.0, 1.0, 1.0], [2.0, 2.0, 3.0, 3.0]],
        track_ids=[1, 2],
        class_ids=[2, 7],
        confidences=[0.5, 0.6],
    )
    assert [d.track_id for d in detections] == [1, 2]
    assert [d.class_id for d in detections] == [2, 7]
