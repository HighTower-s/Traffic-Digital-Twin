using UnityEngine;
using System.Collections;
public class VehicleSpawner : MonoBehaviour
{
    [Header("Prefabs")]
    public GameObject motorcyclePrefab;
    public GameObject carPrefab;

    [Header("Spawn Settings")]
    public Transform spawnPoint;
    public float spawnDelay = 2f; // ระยะเวลาหน่วงระหว่างการสร้างรถแต่ละคัน

    // จำลองข้อมูล JSON ที่รับมา (ในงานจริงอาจจะรับมาจาก API หรืออ่านจากไฟล์)
    private string mockJsonData = "{\"motorcycleCount\": 8, \"carCount\": 10}";

    void Start()
    {
        // 1. แปลง JSON เป็น Object
        VehicleData data = JsonUtility.FromJson<VehicleData>(mockJsonData);

        // 2. เริ่มต้นกระบวนการ Spawn
        StartCoroutine(SpawnVehiclesRoutine(data));
    }

    IEnumerator SpawnVehiclesRoutine(VehicleData data)
    {
        // Spawn มอเตอร์ไซค์
        for (int i = 0; i < data.motorcycleCount; i++)
        {
            Instantiate(motorcyclePrefab, spawnPoint.position, spawnPoint.rotation);
            yield return new WaitForSeconds(spawnDelay); // รอ 2 วินาทีก่อนสร้างคันถัดไป
        }

        // Spawn รถยนต์
        for (int i = 0; i < data.carCount; i++)
        {
            Instantiate(carPrefab, spawnPoint.position, spawnPoint.rotation);
            yield return new WaitForSeconds(spawnDelay);
        }

        Debug.Log("Spawn รถเสร็จสิ้น!");
    }
}
