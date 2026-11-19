/**
 * ข้อความอธิบายว่าทำไมเปิดเซิร์ฟเวอร์ไม่ได้ (ข้อความเป็นภาษาอังกฤษ — เป็น runtime error
 * ที่อาจไปโผล่ใน log ของ Docker หรือ terminal ที่ไม่รองรับภาษาไทย)
 *
 * แยกออกมาเป็นฟังก์ชันบริสุทธิ์เพื่อเทสได้โดยไม่ต้องเปิด port จริงและไม่ต้อง mock process.exit
 * ของเดิมไม่ได้ดัก error เลย — port ไม่ว่างแล้วได้ stack trace 20 บรรทัดที่ไม่ได้บอกว่าต้องทำอะไรต่อ
 */
export function describeStartupError(error: NodeJS.ErrnoException, port: number): string {
  switch (error.code) {
    case 'EADDRINUSE':
      return (
        `[backend] Port ${port} is already in use — cannot start server\n` +
        `  Another backend may still be running. Check: curl http://localhost:${port}/health\n` +
        `  Stop it (Ctrl+C in that terminal), or use another port via PORT=3001 in backend/.env`
      );
    case 'EACCES':
      return (
        `[backend] Permission denied for port ${port}\n` +
        `  Ports below 1024 require admin privileges — set a higher PORT in backend/.env`
      );
    default:
      return `[backend] Failed to start server on port ${port}: ${error.message}`;
  }
}
