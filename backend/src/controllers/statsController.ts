import { Request, Response } from 'express';
import { vehicleCounters } from '../counters/vehicleCounters';

export function getStatsHandler(_req: Request, res: Response): void {
  res.json(vehicleCounters.getStats());
}

export function resetStatsHandler(_req: Request, res: Response): void {
  vehicleCounters.reset();
  res.json({ ok: true });
}
