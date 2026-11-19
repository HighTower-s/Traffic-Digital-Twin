"""ส่ง spawn event เข้า backend ผ่าน HTTP POST — ไม่บล็อกการนับถ้า backend ล่ม

หลักการเดียวกับ SpawnEventWriter: การนับต้องไม่มีวันหยุดเพราะปัญหาที่ปลายทาง
ส่งไม่สำเร็จ (timeout, connection refused, HTTP 400/500) = log แล้วไปต่อ ไม่ raise
"""

from __future__ import annotations

from typing import Any

import httpx

POST_TIMEOUT_SEC = 3.0


class BackendPoster:
    """POST payload เข้า backend — spawn event และสถานะจราจรไปคนละ endpoint"""

    def __init__(
        self,
        backend_url: str,
        timeout: float = POST_TIMEOUT_SEC,
        client: httpx.Client | None = None,
    ) -> None:
        """client: ใส่เองเพื่อเทส (เช่น httpx.MockTransport) — ปกติปล่อยว่างให้สร้างจริง"""
        base = backend_url.rstrip("/")
        self._url = f"{base}/api/ingest"
        self._state_url = f"{base}/api/traffic-state"
        self._reset_url = f"{base}/api/session/reset"
        self._client = client or httpx.Client(timeout=timeout)
        self.sent = 0
        self.failed = 0

    def post(self, payload: dict[str, Any]) -> bool:
        """ส่ง spawn event — คืน True ถ้า backend ตอบ 200"""
        return self._post_to(self._url, payload)

    def post_traffic_state(self, payload: dict[str, Any]) -> bool:
        """ส่งสถานะจราจร (สรุปต่อช่วงเวลา) ไปคนละ endpoint กับ spawn event"""
        return self._post_to(self._state_url, payload)

    def reset_session(self) -> bool:
        """บอก backend ให้ล้างไฟล์ capture + ตัวนับ ก่อนเริ่มส่งรอบใหม่

        ไม่งั้นรอบนี้จะต่อท้ายรอบก่อน — คลิป 100 คันกลายเป็นไฟล์ 200 บรรทัด
        ไม่นับรวมใน self.sent/self.failed เพราะไม่ใช่ payload ของข้อมูลจราจร
        """
        try:
            response = self._client.post(self._reset_url, json={})
        except httpx.HTTPError as exc:
            print(f"[poster] Cannot reset backend session ({self._reset_url}): {exc}", flush=True)
            return False

        if response.status_code != 200:
            print(
                f"[poster] Backend refused session reset ({response.status_code}): "
                f"{response.text[:200]}",
                flush=True,
            )
            return False
        return True

    def _post_to(self, url: str, payload: dict[str, Any]) -> bool:
        """error ใด ๆ log แล้วคืน False — ปลายทางมีปัญหาต้องไม่ทำให้ทั้ง pipeline หยุด"""
        try:
            response = self._client.post(url, json=payload)
        except httpx.HTTPError as exc:
            self.failed += 1
            print(f"[poster] Cannot reach backend ({url}): {exc}", flush=True)
            return False

        if response.status_code != 200:
            self.failed += 1
            print(
                f"[poster] Backend rejected ({response.status_code}): {response.text[:200]}",
                flush=True,
            )
            return False

        self.sent += 1
        return True

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> BackendPoster:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
