import { SpawnEvent } from '../validation/validateSpawnEvent';

export interface UnitySpawnData {
  trackId: string;
  type: string;
  direction: string;
  cameraId: string;
  timestamp: string;
}

export interface UnitySpawnEnvelope {
  event: 'spawn_vehicle';
  data: UnitySpawnData;
}

export function toUnitySpawnPayload(event: SpawnEvent): UnitySpawnEnvelope {
  return {
    event: 'spawn_vehicle',
    data: {
      trackId: event.trackId,
      type: event.type,
      direction: event.direction,
      cameraId: event.cameraId,
      timestamp: event.timestamp,
    },
  };
}
