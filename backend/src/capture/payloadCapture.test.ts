import { capture, isCaptureEnabled } from './payloadCapture';

describe('isCaptureEnabled', () => {
  const original = process.env['CAPTURE_PAYLOADS'];

  afterEach(() => {
    if (original === undefined) delete process.env['CAPTURE_PAYLOADS'];
    else process.env['CAPTURE_PAYLOADS'] = original;
  });

  it('เปิดเป็นค่าเริ่มต้น — เป็น dev tool ที่ควรเห็นไฟล์ทันทีโดยไม่ต้องตั้งค่า', () => {
    delete process.env['CAPTURE_PAYLOADS'];
    expect(isCaptureEnabled()).toBe(true);
  });

  it('ปิดได้ด้วย CAPTURE_PAYLOADS=false', () => {
    process.env['CAPTURE_PAYLOADS'] = 'false';
    expect(isCaptureEnabled()).toBe(false);
  });

  it('ค่าอื่นที่ไม่ใช่ "false" ถือว่าเปิด', () => {
    process.env['CAPTURE_PAYLOADS'] = 'true';
    expect(isCaptureEnabled()).toBe(true);
  });
});

describe('capture', () => {
  const original = process.env['CAPTURE_PAYLOADS'];

  afterEach(() => {
    if (original === undefined) delete process.env['CAPTURE_PAYLOADS'];
    else process.env['CAPTURE_PAYLOADS'] = original;
    jest.restoreAllMocks();
  });

  it('ไม่ทำอะไรเลยเมื่อปิดอยู่', () => {
    process.env['CAPTURE_PAYLOADS'] = 'false';
    expect(() => capture('spawn', { a: 1 })).not.toThrow();
  });

  it('payload ที่ serialize ไม่ได้ต้องไม่ทำให้ throw — broadcast ห้ามหยุดเพราะบันทึกไฟล์พลาด', () => {
    process.env['CAPTURE_PAYLOADS'] = 'true';
    jest.spyOn(console, 'warn').mockImplementation(() => {});

    const circular: Record<string, unknown> = { name: 'loop' };
    circular['self'] = circular;

    expect(() => capture('spawn', circular)).not.toThrow();
  });
});
