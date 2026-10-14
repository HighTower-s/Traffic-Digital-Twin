import { Router } from 'express';
import { Server as SocketServer } from 'socket.io';
import { createIngestHandler } from '../controllers/ingestController';
import { resetSessionHandler } from '../controllers/sessionController';
import { getStatsHandler, resetStatsHandler } from '../controllers/statsController';
import { createTrafficStateHandler } from '../controllers/trafficStateController';
import healthRouter from './health';

export function createApiRouter(io: SocketServer): Router {
  const router = Router();

  router.use(healthRouter);
  router.post('/api/ingest', createIngestHandler(io));
  router.post('/api/traffic-state', createTrafficStateHandler(io));
  router.get('/api/stats', getStatsHandler);
  router.post('/api/stats/reset', resetStatsHandler);
  router.post('/api/session/reset', resetSessionHandler);

  return router;
}
