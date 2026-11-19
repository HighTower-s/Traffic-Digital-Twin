import { toUnitySpawnPayload } from './unityPayload';
import { SpawnEvent } from '../validation/validateSpawnEvent';

const fullEvent: SpawnEvent = {
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

describe('toUnitySpawnPayload', () => {
  it('wraps the payload in a spawn_vehicle envelope', () => {
    const result = toUnitySpawnPayload(fullEvent);
    expect(result.event).toBe('spawn_vehicle');
  });

  it('keeps exactly the 5 fields Unity needs', () => {
    const result = toUnitySpawnPayload(fullEvent);
    expect(result.data).toEqual({
      trackId: 'car-0025',
      type: 'car',
      direction: 'out',
      cameraId: 'cam-chalongkrung-01',
      timestamp: '2026-08-10T15:42:47.671Z',
    });
  });

  it('drops schema, videoTimeSec, frameCount, and confidence', () => {
    const result = toUnitySpawnPayload(fullEvent);
    expect(result.data).not.toHaveProperty('schema');
    expect(result.data).not.toHaveProperty('videoTimeSec');
    expect(result.data).not.toHaveProperty('frameCount');
    expect(result.data).not.toHaveProperty('confidence');
  });

  it('works for an event without the optional videoTimeSec/frameCount fields', () => {
    const { videoTimeSec: _videoTimeSec, frameCount: _frameCount, ...minimal } = fullEvent;
    const result = toUnitySpawnPayload(minimal as SpawnEvent);
    expect(result.data.trackId).toBe('car-0025');
  });

  it('produces the exact envelope shape end to end', () => {
    const result = toUnitySpawnPayload(fullEvent);
    expect(result).toEqual({
      event: 'spawn_vehicle',
      data: {
        trackId: 'car-0025',
        type: 'car',
        direction: 'out',
        cameraId: 'cam-chalongkrung-01',
        timestamp: '2026-08-10T15:42:47.671Z',
      },
    });
  });
});
