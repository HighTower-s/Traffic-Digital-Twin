import { Request, Response } from 'express';
import { resetCaptureFiles } from '../capture/payloadCapture';
import { CAPTURED_CHANNELS } from '../constants';
import { vehicleCounters } from '../counters/vehicleCounters';

/**
 * เริ่มรอบเดโมใหม่ — ล้างทั้งไฟล์ capture และตัวนับให้ว่างพร้อมกัน
 *
 * ของเดิมล้างเฉพาะตอนเซิร์ฟเวอร์สตาร์ต ทำให้ replay รอบที่ 2 ต่อท้ายรอบแรก:
 * คลิป 100 คันกลายเป็นไฟล์ 200 บรรทัดและ dashboard ขึ้น 200 โดยดูไม่ออกจากตัวไฟล์
 * (trackId ซ้ำเฉย ๆ) ai-worker เรียก endpoint นี้ก่อนเริ่มส่งทุกครั้งที่ใช้ --backend
 *
 * ล้าง 2 อย่างพร้อมกันเสมอ — ถ้าล้างแค่อย่างเดียวไฟล์กับ dashboard จะไม่ตรงกัน
 * ซึ่งแย่กว่าตอนที่ทั้งคู่ผิดเหมือน ๆ กัน
 */
export function resetSessionHandler(_req: Request, res: Response): void {
  resetCaptureFiles(CAPTURED_CHANNELS);
  vehicleCounters.reset();
  res.json({ ok: true, cleared: [...CAPTURED_CHANNELS, 'stats'] });
}
