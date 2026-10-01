import { Request, Response } from 'express';
import { Server as SocketServer } from 'socket.io';
import { capture } from '../capture/payloadCapture';
import { LOG_TRUNCATE } from '../constants';
import { TrafficStatePayload, validateTrafficState } from '../validation/validateTrafficState';

export function createTrafficStateHandler(io: SocketServer) {
  return (req: Request, res: Response): void => {
    const result = validateTrafficState(req.body);

    if (!result.valid) {
      const raw = JSON.stringify(req.body).slice(0, LOG_TRUNCATE);
      console.warn(`[traffic-state] REJECTED — ${result.reason} | payload: ${raw}`);
      res.status(400).json({ error: result.reason });
      return;
    }

    const payload = req.body as TrafficStatePayload;

    // ไม่แปลง payload — ส่งต่อตามที่ AI Worker ตัดสินมา (ดู docs/data-contract.md)
    io.emit('traffic_state', payload);

    // บันทึกหลัง emit — การเขียนไฟล์ต้องไม่หน่วง broadcast
    capture('traffic_state', payload);

    res.status(200).json({ ok: true });
  };
}
