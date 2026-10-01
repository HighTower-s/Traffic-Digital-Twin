import fs from 'node:fs';
import path from 'node:path';

/**
 * บันทึก payload ทุกก้อนที่ broadcast ออกไปลงไฟล์ .jsonl
 *
 * **ทำไมต้องอยู่ที่ backend ไม่ใช่ ai-worker:** ช่อง `spawn_vehicle` ถูก "ห่อและตัดฟิลด์"
 * ที่นี่ (ดู sockets/unityPayload.ts) ai-worker จึงไม่รู้ว่า Unity ได้รับหน้าตาแบบไหน
 * ไฟล์พวกนี้คือหลักฐานเดียวของสิ่งที่ Unity เห็นจริง
 *
 * เขียนแบบ append ทีละบรรทัด ไม่ค้างใน memory — กด Ctrl-C แล้วข้อมูลที่ได้มาต้องไม่หาย
 * (รูปแบบเดียวกับ ai-worker/data/output_results/*.jsonl)
 */

const OUTPUT_DIR = path.join(process.cwd(), 'data', 'output');

/** ปิดได้ด้วย CAPTURE_PAYLOADS=false — เปิดเป็นค่าเริ่มต้นเพราะเป็น dev tool ที่ควรเห็นผลทันที */
export function isCaptureEnabled(): boolean {
  return process.env['CAPTURE_PAYLOADS'] !== 'false';
}

/**
 * เขียน 1 payload = 1 บรรทัด
 *
 * ใช้ appendFile (async, เปิด-ปิดไฟล์ทุกครั้ง) ไม่ใช่ WriteStream ค้างไว้ เพราะ
 * stream ที่ cache ไว้จะชี้ไปยังไฟล์เดิมต่อไปแม้ไฟล์ถูกลบ/ย้าย — เขียนหายเงียบ ๆ
 * (เจอจริงตอนลบไฟล์ขณะเซิร์ฟเวอร์รัน: 95 บรรทัดหายโดยไม่มี error)
 * ปริมาณจริงแค่ไม่กี่บรรทัดต่อวินาที ค่าใช้จ่ายการเปิดไฟล์จึงไม่มีนัยสำคัญ
 *
 * ห้าม throw ไม่ว่ากรณีใด — การบันทึกล้มเหลวต้องไม่ทำให้ broadcast หยุด
 */
export function capture(channel: string, payload: unknown): void {
  if (!isCaptureEnabled()) return;

  let line: string;
  try {
    line = JSON.stringify(payload) + '\n';
  } catch (err) {
    console.warn(
      `[capture] แปลง payload ของช่อง "${channel}" เป็น JSON ไม่ได้: ${(err as Error).message}`
    );
    return;
  }

  const file = path.join(OUTPUT_DIR, `${channel}.jsonl`);
  fs.mkdir(OUTPUT_DIR, { recursive: true }, (mkdirErr) => {
    if (mkdirErr) {
      console.warn(`[capture] สร้างโฟลเดอร์ ${OUTPUT_DIR} ไม่ได้: ${mkdirErr.message}`);
      return;
    }
    fs.appendFile(file, line, (err) => {
      // ล้มเงียบไม่ได้ — ถ้าเขียนไม่ได้ต้องรู้ว่าไฟล์ที่เห็นไม่ครบ
      if (err) console.warn(`[capture] เขียน ${file} ไม่ได้: ${err.message}`);
    });
  });
}

/** ล้างไฟล์เดิมทิ้งตอนเซิร์ฟเวอร์เริ่ม — ไม่งั้นผลของหลายรอบจะปนกันจนอ่านไม่รู้เรื่อง */
export function resetCaptureFiles(channels: readonly string[]): void {
  if (!isCaptureEnabled()) return;

  try {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
    for (const channel of channels) {
      fs.writeFileSync(path.join(OUTPUT_DIR, `${channel}.jsonl`), '');
    }
  } catch (err) {
    console.warn(`[capture] ล้างไฟล์เดิมไม่สำเร็จ: ${(err as Error).message}`);
  }
}
