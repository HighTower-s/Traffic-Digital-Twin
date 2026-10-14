import { describeStartupError } from './startupError';

function errorWithCode(code: string, message = 'boom'): NodeJS.ErrnoException {
  const error: NodeJS.ErrnoException = new Error(message);
  error.code = code;
  return error;
}

describe('describeStartupError', () => {
  it('อธิบาย EADDRINUSE พร้อมวิธีแก้ ไม่ใช่แค่บอกว่าพัง', () => {
    const message = describeStartupError(errorWithCode('EADDRINUSE'), 3000);

    expect(message).toContain('Port 3000');
    expect(message).toContain('/health');
    expect(message).toContain('PORT=3001');
  });

  it('ใช้เลข port ที่ส่งเข้ามาจริง ไม่ hardcode 3000', () => {
    expect(describeStartupError(errorWithCode('EADDRINUSE'), 4500)).toContain('Port 4500');
  });

  it('อธิบาย EACCES ว่าเป็นเรื่องสิทธิ์ ไม่ใช่ port ซ้ำ', () => {
    const message = describeStartupError(errorWithCode('EACCES'), 80);

    expect(message).toContain('Permission denied');
    expect(message).not.toContain('already in use');
  });

  it('error ที่ไม่รู้จักต้องไม่ถูกกลืน — ข้อความเดิมต้องยังอยู่', () => {
    const message = describeStartupError(errorWithCode('ENOTFOUND', 'dns is down'), 3000);

    expect(message).toContain('dns is down');
  });

  it('error ที่ไม่มี code ก็ยังอธิบายได้', () => {
    const message = describeStartupError(new Error('something odd'), 3000);

    expect(message).toContain('something odd');
  });
});
