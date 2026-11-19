import { Server as SocketServer } from 'socket.io';

export function registerUnityHandler(io: SocketServer): void {
  io.on('connection', (socket) => {
    console.log(`[ws] client connected: ${socket.id}`);
    socket.on('disconnect', () => {
      console.log(`[ws] client disconnected: ${socket.id}`);
    });
  });
}
