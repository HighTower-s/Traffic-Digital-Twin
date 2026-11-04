using UnityEngine;
using System.Collections;
using System.Collections.Generic;
// เอา using System.Diagnostics; ออกเพื่อป้องกันความสับสนกับ Debug ของ Unity

public class ParkingManager : MonoBehaviour
{
    public Dictionary<string, ParkingSlot> slots = new Dictionary<string, ParkingSlot>();
    
    public GameObject carPrefab;
    public Transform globalSpawnPoint;

    void Start()
    {
        ParkingSlot[] allSlots = FindObjectsOfType<ParkingSlot>();
        foreach (var slot in allSlots)
        {
            slots.Add(slot.slotId, slot);
        }
        // แจ้งเตือนตอนเริ่มเกมว่าเจอช่องจอดกี่ช่อง
        Debug.Log($"[Start] เจอช่องจอดทั้งหมด {slots.Count} ช่องใน Scene");
    }

    void Update()
    {
        // ... (โค้ดส่วน 1. ทดสอบเข้า-ออกแบบทีละคัน คงไว้เหมือนเดิม) ...

        // ---------------- 2. ทดสอบแบบเรียงคิวตามกันมา ----------------
        if (Input.GetKeyDown(KeyCode.S))
        {
            // จำลอง JSON String (ในงานจริงอาจจะอ่านมาจากไฟล์ .json หรือ Web API)
            string jsonMockup = @"{
              ""demo_sequence"": [
                { ""slot_id"": ""A-01"", ""vehicle_type"": ""car"", ""is_occupied"": true, ""delay_seconds"": 0 },
                { ""slot_id"": ""A-02"", ""vehicle_type"": ""car"", ""is_occupied"": true, ""delay_seconds"": 15 },
                { ""slot_id"": ""A-03"", ""vehicle_type"": ""car"", ""is_occupied"": true, ""delay_seconds"": 8 },
                { ""slot_id"": ""A-04"", ""vehicle_type"": ""car"", ""is_occupied"": true, ""delay_seconds"": 35 },
                { ""slot_id"": ""A-05"", ""vehicle_type"": ""car"", ""is_occupied"": true, ""delay_seconds"": 45 }
              ]
            }";

            // แปลง JSON สู่คลาส Wrapper
            ParkingSequenceWrapper data = JsonUtility.FromJson<ParkingSequenceWrapper>(jsonMockup);
            
            // เรียก Coroutine พร้อมส่งข้อมูลชุดนี้เข้าไป
            StartCoroutine(SpawnSequenceMockup(data));
        }
    }

    // ปรับ Coroutine ให้วนลูปอ่าน delay_seconds จากแต่ละคัน
    private IEnumerator SpawnSequenceMockup(ParkingSequenceWrapper sequenceData)
    {
        foreach (DemoParkingEvent item in sequenceData.demo_sequence)
        {
            // หน่วงเวลาก่อนปล่อยคิวตาม delay_seconds ใน JSON
            if (item.delay_seconds > 0)
            {
                yield return new WaitForSeconds(item.delay_seconds);
            }

            Debug.Log($"[Mockup] ปล่อยรถประเภท {item.vehicle_type} ไปช่อง {item.slot_id}");
            
            // สร้าง ParkingEvent แบบเดิมเพื่อส่งเข้า OnDataReceived
            ParkingEvent pEvent = new ParkingEvent 
            { 
                slot_id = item.slot_id, 
                vehicle_type = item.vehicle_type, 
                is_occupied = item.is_occupied 
            };
            
            OnDataReceived(pEvent);
        }
    }

    public void OnDataReceived(ParkingEvent data)
    {
        if (slots.TryGetValue(data.slot_id, out ParkingSlot targetSlot))
        {
            if (data.is_occupied && targetSlot.currentVehicle == null)
            {
                // ขาเข้า: สั่งรถให้วิ่งไปจอด (เหมือนเดิม)
                GameObject newVehicle = Instantiate(carPrefab, globalSpawnPoint.position, globalSpawnPoint.rotation);
                targetSlot.currentVehicle = newVehicle;

                ParkingController parkingCtrl = newVehicle.GetComponent<ParkingController>();
                if (parkingCtrl != null)
                {
                    parkingCtrl.StartParkingProcess(targetSlot.entrancePoint, targetSlot.transform);
                }
            }
            else if (!data.is_occupied && targetSlot.currentVehicle != null)
            {
                // ขาออก: สั่งรถให้ขับออกไปที่ globalSpawnPoint
                ParkingController parkingCtrl = targetSlot.currentVehicle.GetComponent<ParkingController>();
                if (parkingCtrl != null)
                {
                    // สั่งให้รถเล่นอนิเมชันขับออก
                    parkingCtrl.StartExitingProcess(targetSlot.entrancePoint, globalSpawnPoint);
                }
                else
                {
                    Destroy(targetSlot.currentVehicle); // ป้องกันบั๊กกรณีหาสคริปต์ไม่เจอ
                }

                // สำคัญมาก! ต้องเคลียร์ค่า currentVehicle เป็น null ทันที
                // เพื่อให้ช่องจอดว่างในระบบเผื่อมีรถคันใหม่เสียบเข้ามาจอดต่อ
                targetSlot.currentVehicle = null;
            }
        }
    }
}