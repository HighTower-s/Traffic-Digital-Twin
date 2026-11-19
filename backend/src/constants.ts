export const VEHICLE_TYPES = ['car', 'truck', 'motorcycle', 'bus'] as const;
export type VehicleType = (typeof VEHICLE_TYPES)[number];

export const DIRECTIONS = ['in', 'out'] as const;
export type Direction = (typeof DIRECTIONS)[number];

// สถานะจราจรที่ AI Worker ตัดสินมาแล้ว — ต้องตรงกับ STATE_* ใน ai-worker/src/constants.py
export const TRAFFIC_STATES = ['normal', 'high_density', 'slow_moving', 'standstill'] as const;
export type TrafficState = (typeof TRAFFIC_STATES)[number];

export const LOG_TRUNCATE = 500;

// ช่อง Socket.io ที่ถูกบันทึกลง backend/data/output/<ช่อง>.jsonl
// อยู่ตรงนี้เพราะทั้งตอนสตาร์ตเซิร์ฟเวอร์และตอน reset session ต้องใช้รายการเดียวกัน
export const CAPTURED_CHANNELS = ['spawn', 'spawn_vehicle', 'traffic_state'] as const;
