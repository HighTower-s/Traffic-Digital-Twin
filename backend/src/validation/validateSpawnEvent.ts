import { DIRECTIONS, Direction, VEHICLE_TYPES, VehicleType } from '../constants';

export interface SpawnEvent {
  schema?: string;
  timestamp: string;
  cameraId: string;
  videoTimeSec?: number;
  frameCount?: number;
  trackId: string;
  type: VehicleType;
  direction: Direction;
  confidence: number;
}

type ValidationResult = { valid: true } | { valid: false; reason: string };

function isValidIso8601(value: string): boolean {
  return !isNaN(Date.parse(value));
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && isFinite(value);
}

export function validateSpawnEvent(body: unknown): ValidationResult {
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

  if (typeof payload['trackId'] !== 'string' || payload['trackId'].trim() === '') {
    return { valid: false, reason: 'trackId is missing or empty string' };
  }

  if (!VEHICLE_TYPES.includes(payload['type'] as VehicleType)) {
    return {
      valid: false,
      reason: `type "${String(payload['type'])}" is not one of [${VEHICLE_TYPES.join(', ')}]`,
    };
  }

  if (!DIRECTIONS.includes(payload['direction'] as Direction)) {
    return {
      valid: false,
      reason: `direction "${String(payload['direction'])}" is not one of [${DIRECTIONS.join(', ')}]`,
    };
  }

  const confidence = payload['confidence'];
  if (!isFiniteNumber(confidence) || confidence < 0 || confidence > 1) {
    return { valid: false, reason: 'confidence must be a number between 0.0 and 1.0' };
  }

  const videoTimeSec = payload['videoTimeSec'];
  if (videoTimeSec !== undefined && (!isFiniteNumber(videoTimeSec) || videoTimeSec < 0)) {
    return { valid: false, reason: 'videoTimeSec must be a finite non-negative number' };
  }

  const frameCount = payload['frameCount'];
  if (frameCount !== undefined && (!isFiniteNumber(frameCount) || frameCount < 0)) {
    return { valid: false, reason: 'frameCount must be a finite non-negative number' };
  }

  return { valid: true };
}
