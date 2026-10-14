import { Request, Response } from 'express';
import { CAPTURED_CHANNELS } from '../constants';
import { vehicleCounters } from '../counters/vehicleCounters';
import { resetSessionHandler } from './sessionController';

// mock ไว้เพื่อไม่ให้เทสไปแตะไฟล์จริงใน backend/data/output/
jest.mock('../capture/payloadCapture', () => ({
  resetCaptureFiles: jest.fn(),
}));
import { resetCaptureFiles } from '../capture/payloadCapture';

type CapturedResponse = { body: unknown; json: (payload: unknown) => CapturedResponse };

function fakeResponse(): CapturedResponse {
  const res: CapturedResponse = {
    body: undefined,
    json(payload: unknown) {
      res.body = payload;
      return res;
    },
  };
  return res;
}

describe('resetSessionHandler', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    vehicleCounters.reset();
  });

  it('ล้างตัวนับให้เป็นศูนย์', () => {
    vehicleCounters.record('car', 'in', 'cam-chalongkrung-01');
    vehicleCounters.record('bus', 'out', 'cam-chalongkrung-01');
    expect(vehicleCounters.getStats().totals.all).toBe(2);

    resetSessionHandler({} as Request, fakeResponse() as unknown as Response);

    expect(vehicleCounters.getStats().totals.all).toBe(0);
  });

  it('ล้างไฟล์ capture ครบทุกช่องที่บันทึกไว้', () => {
    resetSessionHandler({} as Request, fakeResponse() as unknown as Response);

    expect(resetCaptureFiles).toHaveBeenCalledWith(CAPTURED_CHANNELS);
  });

  it('ตอบกลับว่าล้างอะไรไปบ้าง — ai-worker ใช้ status 200 ตัดสินว่าสำเร็จ', () => {
    const res = fakeResponse();

    resetSessionHandler({} as Request, res as unknown as Response);

    expect(res.body).toEqual({
      ok: true,
      cleared: ['spawn', 'spawn_vehicle', 'traffic_state', 'stats'],
    });
  });
});
