using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class TrafficHistoryTracker : MonoBehaviour
{
    public static TrafficHistoryTracker Instance;

    [System.Serializable]
    public struct TrafficDataPoint
    {
        public int statusValue; // 1 = NORMAL, 2 = SLOW MOVING, 3 = HEAVY
        public string statusName;
        public string timestamp;

        public TrafficDataPoint(int value, string name, string time)
        {
            statusValue = value;
            statusName = name;
            timestamp = time;
        }
    }

    [Header("Sampling Settings")]
    public float sampleInterval = 20f; // สุ่มเก็บข้อมูลทุก 20 วินาที
    public int maxDataPoints = 7;      // เก็บ 7 จุด (-120s ถึง NOW)

    // คิวเก็บข้อมูลแบบ Sliding Window
    private List<TrafficDataPoint> historyQueue = new List<TrafficDataPoint>();

    void Awake()
    {
        Instance = this;
    }

        void Start()
    {
        // 🟢 สั่งบันทึกข้อมูลจุดแรกทันทีที่กด Play (ไม่ต้องรอ 20 วินาทีแรก)
        RecordDataPoint(); 

        // เริ่มลูปนับเวลา 20 วินาทีสำหรับจุดถัดๆ ไป
        StartCoroutine(SampleTrafficStateRoutine());
    }

    private IEnumerator SampleTrafficStateRoutine()
    {
        while (true)
        {
            RecordDataPoint();
            yield return new WaitForSeconds(sampleInterval);
        }
    }

    private void RecordDataPoint()
    {
        if (ScenarioManager.Instance == null) return;

        // 1. อ่านสถานะการจราจรจาก ScenarioManager
        string currentState = ScenarioManager.Instance.GetDominantTrafficState();
        int value = MapStateToValue(currentState);
        string timeStr = DateTime.Now.ToString("HH:mm:ss");

        // 2. สร้างก้อนข้อมูลจุดใหม่
        TrafficDataPoint newPoint = new TrafficDataPoint(value, currentState.ToUpper(), timeStr);

        // 3. เพิ่มเข้าคิวประวัติ
        historyQueue.Add(newPoint);

        // 4. ถ้าเกิน 7 จุด ให้ลบจุดเก่าสุด (จุดแรก) ออกแบบ FIFO
        if (historyQueue.Count > maxDataPoints)
        {
            historyQueue.RemoveAt(0);
        }

        // 5. แจ้งระบบ UI ให้วาดกราฟใหม่
        OnHistoryUpdated();
    }

    private int MapStateToValue(string state)
    {
        switch (state.ToLower())
        {
            case "standstill":
            case "high_density":
            case "heavy":
                return 3; // HEAVY (แกน Y สูงสุด)

            case "slow_moving":
            case "congested":
                return 2; // SLOW MOVING (แกน Y ปานกลาง)

            default:
                return 1; // NORMAL (แกน Y ล่างสุด)
        }
    }

    // ฟังก์ชันสำหรับให้สคริปต์วาด UI Graph ดึงข้อมูลไปใช้
    public List<TrafficDataPoint> GetHistoryList()
    {
        return historyQueue;
    }

    private void OnHistoryUpdated()
{
    Debug.Log($"[TrafficHistoryTracker] Data updated! Total points: {historyQueue.Count}");

    // 🟢 สั่งให้ UI Toolkit สลับคิววาดเส้นกราฟใหม่
    if (TrafficGraphUIToolkit.Instance != null)
    {
        TrafficGraphUIToolkit.Instance.RefreshGraph();
    }
}
}