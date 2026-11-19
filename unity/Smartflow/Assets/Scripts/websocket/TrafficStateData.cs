using System;

namespace SmartFlow.Network // ใส่ Namespace ให้ตรงกับโปรเจกต์ของคุณ
{
    // คลาสหลักสำหรับรับข้อมูล "traffic_state"
    [Serializable]
    public class TrafficStatePayload 
    {
        public string timestamp;
        public string cameraId;
        public float windowStartSec;
        public float windowEndSec;
        public TrafficStateZones zones;
        public string trafficState; 
    }

    // คลาสย่อยสำหรับโซน/เลน
    [Serializable]
    public class TrafficStateZones 
    {
        // ใช้ @ นำหน้าเพื่อหลบ Keyword ของ C# ตามที่คุณได้รับแจ้งมา
// เปลี่ยนจาก int เป็นคลาส ZoneDetail
        public ZoneDetail @in;   
        public ZoneDetail @out;
        
        // หมายเหตุ: ถ้าในไฟล์ traffic_state.jsonl มีตัวแปรอื่นใน zones อีก 
        // ให้เอามาพิมพ์เพิ่มตรงนี้ได้เลยครับ
    }
    // 🟢 แก้ไขคลาสย่อยให้ตัวแปรตรงกับ JSON ที่ส่งมาจริง
    [Serializable]
    public class ZoneDetail
    {
        public string trafficState;       // สถานะรายเลน (ได้มาจาก zone_states)
        public float occupancy;           // ความหนาแน่น
        public float vehicleFlowRate;     // อัตราการไหลของรถใหญ่
        public float motorcycleFlowRate;  // อัตราการไหลของมอเตอร์ไซค์
    }
}