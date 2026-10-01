import { validateTrafficState } from './validateTrafficState';

const validPayload = {
  schema: 'traffic-state/0.1-draft',
  timestamp: '2026-09-01T09:15:55.123Z',
  cameraId: 'cam-chalongkrung-01',
  windowStartSec: 20.0,
  windowEndSec: 30.0,
  zones: {
    in: { occupancy: 2.83, vehicleFlowRate: 30.0, motorcycleFlowRate: 12.0 },
    out: { occupancy: 1.65, vehicleFlowRate: 36.0, motorcycleFlowRate: 6.0 },
  },
  trafficState: 'normal',
};

describe('validateTrafficState', () => {
  it('accepts a valid traffic-state payload', () => {
    expect(validateTrafficState(validPayload)).toEqual({ valid: true });
  });

  it('accepts every traffic state in the enum', () => {
    for (const trafficState of ['normal', 'high_density', 'slow_moving', 'standstill']) {
      expect(validateTrafficState({ ...validPayload, trafficState })).toEqual({ valid: true });
    }
  });

  it('accepts a single-zone payload (one-way road)', () => {
    const payload = {
      ...validPayload,
      zones: { out: { occupancy: 8.0, vehicleFlowRate: 0.5, motorcycleFlowRate: 24.0 } },
    };
    expect(validateTrafficState(payload)).toEqual({ valid: true });
  });

  it('accepts zero occupancy and zero flow (empty road)', () => {
    const payload = {
      ...validPayload,
      zones: { out: { occupancy: 0, vehicleFlowRate: 0, motorcycleFlowRate: 0 } },
    };
    expect(validateTrafficState(payload)).toEqual({ valid: true });
  });

  // motorcycleFlowRate เพิ่มมาใน contract 1.4.0 — worker รุ่นก่อนหน้าไม่ส่งมา
  it('accepts a zone without motorcycleFlowRate', () => {
    const payload = { ...validPayload, zones: { out: { occupancy: 1.2, vehicleFlowRate: 18.0 } } };
    expect(validateTrafficState(payload)).toEqual({ valid: true });
  });

  // zones.*.trafficState เพิ่มมาใน contract 1.5.0 — ถนน 2 ฝั่งติดไม่พร้อมกัน
  it('accepts a per-zone trafficState that differs from the overall verdict', () => {
    const payload = {
      ...validPayload,
      zones: {
        in: { occupancy: 0.0, vehicleFlowRate: 0.0, trafficState: 'normal' },
        out: { occupancy: 9.0, vehicleFlowRate: 0.0, trafficState: 'standstill' },
      },
      trafficState: 'standstill',
    };
    expect(validateTrafficState(payload)).toEqual({ valid: true });
  });

  it('accepts a zone without trafficState (worker older than 1.5.0)', () => {
    const payload = { ...validPayload, zones: { out: { occupancy: 1.2, vehicleFlowRate: 18.0 } } };
    expect(validateTrafficState(payload)).toEqual({ valid: true });
  });

  it('rejects an unknown per-zone trafficState', () => {
    const payload = {
      ...validPayload,
      zones: { out: { occupancy: 1, vehicleFlowRate: 6, trafficState: 'exploded' } },
    };
    expect(validateTrafficState(payload)).toEqual({
      valid: false,
      reason: expect.stringContaining('zones.out.trafficState'),
    });
  });

  it('rejects a non-object body', () => {
    expect(validateTrafficState(null).valid).toBe(false);
  });

  it('rejects a missing timestamp', () => {
    const { timestamp: _timestamp, ...rest } = validPayload;
    expect(validateTrafficState(rest)).toEqual({
      valid: false,
      reason: expect.stringContaining('timestamp'),
    });
  });

  it('rejects an empty cameraId', () => {
    expect(validateTrafficState({ ...validPayload, cameraId: '  ' })).toEqual({
      valid: false,
      reason: expect.stringContaining('cameraId'),
    });
  });

  it('rejects an unknown trafficState', () => {
    expect(validateTrafficState({ ...validPayload, trafficState: 'exploded' })).toEqual({
      valid: false,
      reason: expect.stringContaining('trafficState'),
    });
  });

  it('rejects a negative windowStartSec', () => {
    expect(validateTrafficState({ ...validPayload, windowStartSec: -1 })).toEqual({
      valid: false,
      reason: expect.stringContaining('windowStartSec'),
    });
  });

  it('rejects a window that ends before it starts', () => {
    const payload = { ...validPayload, windowStartSec: 30, windowEndSec: 20 };
    expect(validateTrafficState(payload)).toEqual({
      valid: false,
      reason: expect.stringContaining('windowEndSec'),
    });
  });

  it('rejects a zero-length window', () => {
    const payload = { ...validPayload, windowStartSec: 20, windowEndSec: 20 };
    expect(validateTrafficState(payload).valid).toBe(false);
  });

  it('rejects missing zones', () => {
    const { zones: _zones, ...rest } = validPayload;
    expect(validateTrafficState(rest)).toEqual({
      valid: false,
      reason: expect.stringContaining('zones'),
    });
  });

  it('rejects an empty zones object', () => {
    expect(validateTrafficState({ ...validPayload, zones: {} })).toEqual({
      valid: false,
      reason: expect.stringContaining('zones'),
    });
  });

  it('rejects zones given as an array', () => {
    expect(validateTrafficState({ ...validPayload, zones: [] }).valid).toBe(false);
  });

  it('rejects a negative occupancy', () => {
    const payload = { ...validPayload, zones: { out: { occupancy: -1, vehicleFlowRate: 10 } } };
    expect(validateTrafficState(payload)).toEqual({
      valid: false,
      reason: expect.stringContaining('occupancy'),
    });
  });

  it('rejects a missing vehicleFlowRate', () => {
    const payload = { ...validPayload, zones: { out: { occupancy: 1, motorcycleFlowRate: 6 } } };
    expect(validateTrafficState(payload)).toEqual({
      valid: false,
      reason: expect.stringContaining('vehicleFlowRate'),
    });
  });

  it('rejects a non-numeric vehicleFlowRate', () => {
    const payload = { ...validPayload, zones: { out: { occupancy: 1, vehicleFlowRate: 'fast' } } };
    expect(validateTrafficState(payload)).toEqual({
      valid: false,
      reason: expect.stringContaining('vehicleFlowRate'),
    });
  });

  it('rejects a negative motorcycleFlowRate when present', () => {
    const payload = {
      ...validPayload,
      zones: { out: { occupancy: 1, vehicleFlowRate: 10, motorcycleFlowRate: -1 } },
    };
    expect(validateTrafficState(payload)).toEqual({
      valid: false,
      reason: expect.stringContaining('motorcycleFlowRate'),
    });
  });

  it('names the offending zone in the reason', () => {
    const payload = {
      ...validPayload,
      zones: {
        in: { occupancy: 1, vehicleFlowRate: 1 },
        out: { occupancy: 1, vehicleFlowRate: -5 },
      },
    };
    const result = validateTrafficState(payload);
    expect(result).toEqual({ valid: false, reason: expect.stringContaining('zones.out') });
  });
});
