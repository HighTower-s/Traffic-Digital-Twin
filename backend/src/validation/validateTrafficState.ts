import { TRAFFIC_STATES, TrafficState } from '../constants';

export interface TrafficStateZone {
  occupancy: number;
  /** car + truck + bus ต่อนาที — ค่าเดียวที่ AI Worker ใช้ตัดสิน trafficState */
  vehicleFlowRate: number;
  /** มอเตอร์ไซค์ต่อนาที — แยกออกมาเพราะมุดผ่านรถติดได้ ไม่สะท้อนว่าถนนไหลจริง
   *  optional เพื่อรองรับ payload จาก worker รุ่นก่อน 1.4.0 */
  motorcycleFlowRate?: number;
  /** คำตัดสินของฝั่งถนนนี้โดยเฉพาะ — ถนน 2 ฝั่งติดไม่พร้อมกัน ค่ารวมระดับบนสุด
   *  จึงกลบครึ่งหนึ่งของข้อมูล optional เพื่อรองรับ worker รุ่นก่อน 1.5.0 */
  trafficState?: TrafficState;
}

export interface TrafficStatePayload {
  schema?: string;
  timestamp: string;
  cameraId: string;
  windowStartSec: number;
  windowEndSec: number;
  zones: Record<string, TrafficStateZone>;
  trafficState: TrafficState;
}

type ValidationResult = { valid: true } | { valid: false; reason: string };

function isValidIso8601(value: string): boolean {
  return !isNaN(Date.parse(value));
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && isFinite(value);
}

export function validateTrafficState(body: unknown): ValidationResult {
  if (typeof body !== 'object' || body === null) {
    return { valid: false, reason: 'Payload must be a JSON object' };
  }

  const payload = body as Record<string, unknown>;

  if (typeof payload['timestamp'] !== 'string' || !isValidIso8601(payload['timestamp'])) {
    return { valid: false, reason: 'timestamp is missing or not a valid ISO 8601 string' };
  }

  if (typeof payload['cameraId'] !== 'string' || payload['cameraId'].trim() === '') {
    return { valid: false, reason: 'cameraId is missing or empty string' };
  }

  const start = payload['windowStartSec'];
  if (!isFiniteNumber(start) || start < 0) {
    return { valid: false, reason: 'windowStartSec must be a finite non-negative number' };
  }

  const end = payload['windowEndSec'];
  if (!isFiniteNumber(end) || end < 0) {
    return { valid: false, reason: 'windowEndSec must be a finite non-negative number' };
  }

  // หน้าต่างที่ปลายมาก่อนต้น แปลว่าข้อมูลเพี้ยน — ยอมรับไปจะทำให้อัตราการไหลติดลบ
  if (end <= start) {
    return { valid: false, reason: `windowEndSec (${end}) must be greater than windowStartSec (${start})` };
  }

  if (!TRAFFIC_STATES.includes(payload['trafficState'] as TrafficState)) {
    return {
      valid: false,
      reason: `trafficState "${String(payload['trafficState'])}" is not one of [${TRAFFIC_STATES.join(', ')}]`,
    };
  }

  const zones = payload['zones'];
  if (typeof zones !== 'object' || zones === null || Array.isArray(zones)) {
    return { valid: false, reason: 'zones is missing or not an object' };
  }

  const zoneEntries = Object.entries(zones as Record<string, unknown>);
  if (zoneEntries.length === 0) {
    return { valid: false, reason: 'zones must contain at least one zone' };
  }

  for (const [name, rawZone] of zoneEntries) {
    if (typeof rawZone !== 'object' || rawZone === null) {
      return { valid: false, reason: `zones.${name} is not an object` };
    }
    const zone = rawZone as Record<string, unknown>;

    const occupancy = zone['occupancy'];
    if (!isFiniteNumber(occupancy) || occupancy < 0) {
      return { valid: false, reason: `zones.${name}.occupancy must be a finite non-negative number` };
    }

    const vehicleFlowRate = zone['vehicleFlowRate'];
    if (!isFiniteNumber(vehicleFlowRate) || vehicleFlowRate < 0) {
      return {
        valid: false,
        reason: `zones.${name}.vehicleFlowRate must be a finite non-negative number`,
      };
    }

    // ไม่บังคับ — แต่ถ้าส่งมาแล้วเพี้ยน ปฏิเสธดีกว่าปล่อยตัวเลขมั่วไปถึง Unity
    const motorcycleFlowRate = zone['motorcycleFlowRate'];
    if (
      motorcycleFlowRate !== undefined &&
      (!isFiniteNumber(motorcycleFlowRate) || motorcycleFlowRate < 0)
    ) {
      return {
        valid: false,
        reason: `zones.${name}.motorcycleFlowRate must be a finite non-negative number when present`,
      };
    }

    // ไม่บังคับ — แต่ถ้าส่งมาแล้วไม่ใช่สถานะที่รู้จัก ปฏิเสธดีกว่าปล่อยให้ Unity เดาเอง
    const zoneState = zone['trafficState'];
    if (zoneState !== undefined && !TRAFFIC_STATES.includes(zoneState as TrafficState)) {
      return {
        valid: false,
        reason: `zones.${name}.trafficState "${String(zoneState)}" is not one of [${TRAFFIC_STATES.join(', ')}]`,
      };
    }
  }

  return { valid: true };
}
