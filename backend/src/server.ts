import { createServer } from 'http';
import { Server as SocketServer } from 'socket.io';
import { createApp } from './app';
import { resetCaptureFiles } from './capture/payloadCapture';
import { PORT } from './config/env';
import { CAPTURED_CHANNELS } from './constants';
import { createApiRouter } from './routes/api';
import { registerUnityHandler } from './sockets/unityHandler';
import { describeStartupError } from './startupError';

const app = createApp();
const httpServer = createServer(app);
const io = new SocketServer(httpServer, {
  cors: { origin: '*' },
});

app.use(createApiRouter(io));
registerUnityHandler(io);

httpServer.on('error', (error: NodeJS.ErrnoException) => {
  console.error(describeStartupError(error, PORT));
  process.exit(1);
});

httpServer.listen(PORT, () => {
  // ล้างไฟล์ capture หลัง listen สำเร็จเท่านั้น — ถ้าล้างก่อน การสตาร์ตที่ล้มเหลว
  // (เช่น port ไม่ว่าง) จะลบ payload ของรอบก่อนทิ้งทั้งที่ไม่ได้เปิดเซิร์ฟเวอร์ด้วยซ้ำ
  resetCaptureFiles(CAPTURED_CHANNELS);
  console.log(`Backend running on http://localhost:${PORT}`);
});
