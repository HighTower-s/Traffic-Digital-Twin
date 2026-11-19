import { validateSpawnEvent } from './validateSpawnEvent';

const validEvent = {
  schema: 'spawn-event/0.2-draft',
  timestamp: '2026-08-10T15:42:47.671Z',
  cameraId: 'cam-chalongkrung-01',
  videoTimeSec: 2.398891,
  frameCount: 72,
  trackId: 'car-0025',
  type: 'car',
  direction: 'out',
  confidence: 0.757,
};

describe('validateSpawnEvent', () => {
  it('accepts a valid spawn-event', () => {
    expect(validateSpawnEvent(validEvent)).toEqual({ valid: true });
  });

  it('accepts every vehicle type in the enum, including bus', () => {
    for (const type of ['car', 'truck', 'motorcycle', 'bus']) {
      expect(validateSpawnEvent({ ...validEvent, type })).toEqual({ valid: true });
    }
  });

  it('accepts an event without optional videoTimeSec/frameCount', () => {
    const { videoTimeSec: _videoTimeSec, frameCount: _frameCount, ...minimal } = validEvent;
    expect(validateSpawnEvent(minimal)).toEqual({ valid: true });
  });

  it('rejects a non-object body', () => {
    const result = validateSpawnEvent(null);
    expect(result.valid).toBe(false);
  });

  it('rejects a missing timestamp', () => {
    const { timestamp: _timestamp, ...rest } = validEvent;
    const result = validateSpawnEvent(rest);
    expect(result).toEqual({ valid: false, reason: expect.stringContaining('timestamp') });
  });

  it('rejects a non-ISO8601 timestamp', () => {
    const result = validateSpawnEvent({ ...validEvent, timestamp: 'not-a-date' });
    expect(result).toEqual({ valid: false, reason: expect.stringContaining('timestamp') });
  });

  it('rejects an empty cameraId', () => {
    const result = validateSpawnEvent({ ...validEvent, cameraId: '' });
    expect(result).toEqual({ valid: false, reason: expect.stringContaining('cameraId') });
  });

  it('rejects an empty trackId', () => {
    const result = validateSpawnEvent({ ...validEvent, trackId: '  ' });
    expect(result).toEqual({ valid: false, reason: expect.stringContaining('trackId') });
  });

  it('rejects an unknown vehicle type', () => {
    const result = validateSpawnEvent({ ...validEvent, type: 'airplane' });
    expect(result).toEqual({ valid: false, reason: expect.stringContaining('type') });
  });

  it('rejects an unknown direction', () => {
    const result = validateSpawnEvent({ ...validEvent, direction: 'sideways' });
    expect(result).toEqual({ valid: false, reason: expect.stringContaining('direction') });
  });

  it('rejects confidence above 1.0', () => {
    const result = validateSpawnEvent({ ...validEvent, confidence: 1.5 });
    expect(result).toEqual({ valid: false, reason: expect.stringContaining('confidence') });
  });

  it('rejects confidence below 0.0', () => {
    const result = validateSpawnEvent({ ...validEvent, confidence: -0.1 });
    expect(result).toEqual({ valid: false, reason: expect.stringContaining('confidence') });
  });

  it('rejects a non-numeric confidence', () => {
    const result = validateSpawnEvent({ ...validEvent, confidence: 'high' });
    expect(result).toEqual({ valid: false, reason: expect.stringContaining('confidence') });
  });

  it('rejects a negative videoTimeSec', () => {
    const result = validateSpawnEvent({ ...validEvent, videoTimeSec: -1 });
    expect(result).toEqual({ valid: false, reason: expect.stringContaining('videoTimeSec') });
  });

  it('rejects a non-finite frameCount', () => {
    const result = validateSpawnEvent({ ...validEvent, frameCount: Infinity });
    expect(result).toEqual({ valid: false, reason: expect.stringContaining('frameCount') });
  });
});
