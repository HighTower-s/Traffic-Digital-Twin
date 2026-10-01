import { createServer } from 'http';
import { Server as SocketServer } from 'socket.io';
import { createApp } from './app';
import { resetCaptureFiles } from './capture/payloadCapture';
import { PORT } from './config/env';
import { createApiRouter } from './routes/api';
import { registerUnityHandler } from './sockets/unityHandler';

const CAPTURED_CHANNELS = ['spawn', 'spawn_vehicle', 'traffic_state'] as const;

const app = createApp();
const httpServer = createServer(app);
const io = new SocketServer(httpServer, {
  cors: { origin: '*' },
});

app.use(createApiRouter(io));
registerUnityHandler(io);
resetCaptureFiles(CAPTURED_CHANNELS);

httpServer.listen(PORT, () => {
  console.log(`Backend running on http://localhost:${PORT}`);
});
