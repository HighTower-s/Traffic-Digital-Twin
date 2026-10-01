import { Request, Response } from 'express';
import { Server as SocketServer } from 'socket.io';
import { capture } from '../capture/payloadCapture';
import { Direction, LOG_TRUNCATE, VehicleType } from '../constants';
import { vehicleCounters } from '../counters/vehicleCounters';
import { toUnitySpawnPayload } from '../sockets/unityPayload';
import { SpawnEvent, validateSpawnEvent } from '../validation/validateSpawnEvent';

export function createIngestHandler(io: SocketServer) {
  return (req: Request, res: Response): void => {
    const result = validateSpawnEvent(req.body);

    if (!result.valid) {
      const raw = JSON.stringify(req.body).slice(0, LOG_TRUNCATE);
      console.warn(`[ingest] REJECTED — ${result.reason} | payload: ${raw}`);
      res.status(400).json({ error: result.reason });
      return;
    }

    const event = req.body as SpawnEvent;
    vehicleCounters.record(event.type as VehicleType, event.direction as Direction, event.cameraId);

    const unityEnvelope = toUnitySpawnPayload(event);
    io.emit('spawn', event);
    io.emit('spawn_vehicle', unityEnvelope);

    // บันทึกหลัง emit — การเขียนไฟล์ต้องไม่หน่วง broadcast
    capture('spawn', event);
    capture('spawn_vehicle', unityEnvelope);

    res.status(200).json({ ok: true });
  };
}
