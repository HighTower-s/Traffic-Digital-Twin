using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using TMPro;
using Random = UnityEngine.Random;

public class ScenarioManager : MonoBehaviour
{
    public static ScenarioManager Instance;

    [System.Serializable]
    public class ScenarioConfig
    {
        public string scenarioName;
        // ไม่ได้ใช้ minSpeed/maxSpeed ตรงนี้แล้ว
        [Header("Lane Settings")]
        public float[] laneOffsets = { 0f };
    }

    [Header("UI References")]
    public TMP_Text avgSpeedText;
    public TMP_Text inboundCountText;
    public TMP_Text outboundCountText;
    public TMP_Text trafficStatusText; 
    public TMP_Text environmentDataText; 
    public TMP_Text connectionStatusText; 
    public TMP_Text timestampText;

    // ===============================================
    // 🟢 1. แยกตัวแปรจำกัดความเร็วสำหรับ Inbound และ Outbound 🟢
    // ===============================================
    [Header("Inbound Speed Settings")]
    public float inboundMinSpeed = 40f;
    public float inboundMaxSpeed = 80f;

    [Header("Outbound Speed Settings")]
    public float outboundMinSpeed = 40f;
    public float outboundMaxSpeed = 80f;

    public float[] globalLaneOffsets = { -3.5f, 0f, 3.5f };

    // ตัวแปรนับแยกประเภทรถ (ขาเข้า)
    private int inboundCarCount = 0;
    private int inboundMotoCount = 0;
    private int inboundTruckCount = 0;
    private int inboundBusCount = 0;

    // ตัวแปรนับแยกประเภทรถ (ขาออก)
    private int outboundCarCount = 0;
    private int outboundMotoCount = 0;
    private int outboundTruckCount = 0;
    private int outboundBusCount = 0;

    // ตัวแปรสำหรับเก็บข้อมูลจราจรจาก Server
    private string currentInboundState = "normal";
    private string currentOutboundState = "normal";

    [Header("Vehicle Prefabs & Spawn")]
    public GameObject[] motorcyclePrefabs;
    public GameObject[] carPrefabs;
    public GameObject[] truckPrefabs;
    public GameObject[] busPrefabs;

    [Header("Route Setup")]
    public WaypointRoute inboundRoute;
    public WaypointRoute outboundRoute;

    [Header("Scenario Configurations")]
    public ScenarioConfig[] scenarios;

    // ระบบคิว
    private Queue<SmartFlow.Network.SpawnVehicleData> networkSpawnQueue = new Queue<SmartFlow.Network.SpawnVehicleData>();
    public float networkSpawnDelay = 0.5f;

    // ระบบ Object Pool
    private Dictionary<GameObject, Queue<GameObject>> vehiclePools = new Dictionary<GameObject, Queue<GameObject>>();
    private List<GameObject> activeVehicles = new List<GameObject>();

    void Awake()
    {
        Instance = this;
    }

    void Start()
    {
        UpdateDashboardUI();
        StartCoroutine(ProcessNetworkSpawnQueue());
    }

    public int GetInboundTotal() => inboundCarCount + inboundMotoCount + inboundTruckCount + inboundBusCount;
    public int GetOutboundTotal() => outboundCarCount + outboundMotoCount + outboundTruckCount + outboundBusCount;
    
    public void UpdateConnectionStatus(bool isConnected)
    {
        if (connectionStatusText != null)
        {
            if (isConnected)
                connectionStatusText.text = "LIVE CONNECTION STATUS: <color=#06D6A0> ACTIVE</color>";
            else
                connectionStatusText.text = "LIVE CONNECTION STATUS: <color=#FF4C4C> DISCONNECTED</color>";
        }
    }

    public void SpawnVehicleFromNetwork(SmartFlow.Network.SpawnVehicleData netData)
    {
        networkSpawnQueue.Enqueue(netData);

        if (timestampText != null && !string.IsNullOrEmpty(netData.timestamp))
        {
            if (DateTime.TryParse(netData.timestamp, out DateTime parsedDate))
            {
                string readableTime = parsedDate.ToLocalTime().ToString("dd/MM/yyyy HH:mm:ss");
                timestampText.text = $"LIVE FEED: {readableTime}";
            }
            else
            {
                timestampText.text = $"LIVE FEED: {netData.timestamp}";
            }
        }
    }

    // =========================================================================
    // 🟢 2. ปรับปรุงการคำนวณความเร็วแยกเลนจากข้อมูล @in และ @out 🟢
    // =========================================================================
    public void UpdateTrafficState(SmartFlow.Network.TrafficStatePayload payload)
    {
        if (payload == null) return;
        
        if (payload.zones != null)
        {
            currentInboundState = payload.zones.@in.trafficState != null ? payload.zones.@in.trafficState.ToLower() : "normal";
            currentOutboundState = payload.zones.@out.trafficState != null ? payload.zones.@out.trafficState.ToLower() : "normal";

            // --- กำหนดค่า Min/Max (เหมือนเดิม) ---
            if (currentInboundState == "standstill" || currentInboundState == "high_density") 
            { inboundMinSpeed = 10f; inboundMaxSpeed = 20f; } 
            else if (currentInboundState == "slow_moving") 
            { inboundMinSpeed = 25f; inboundMaxSpeed = 40f; } 
            else 
            { inboundMinSpeed = 40f; inboundMaxSpeed = 70f; }

            if (currentOutboundState == "standstill" || currentOutboundState == "high_density") 
            { outboundMinSpeed = 10f; outboundMaxSpeed = 20f; } 
            else if (currentOutboundState == "slow_moving") 
            { outboundMinSpeed = 25f; outboundMaxSpeed = 40f; } 
            else 
            { outboundMinSpeed = 40f; outboundMaxSpeed = 70f; }
        }

        UpdateDashboardUI();
        
        // =======================================================
        // 🟢 สั่งรันคลื่นจราจร (Wave) เปลี่ยนความเร็วรถเก่าแบบไล่ระดับ
        // =======================================================
        if (inboundRoute != null)
            StartCoroutine(ApplySpeedGradientWave(inboundRoute, inboundMinSpeed, inboundMaxSpeed));
            
        if (outboundRoute != null)
            StartCoroutine(ApplySpeedGradientWave(outboundRoute, outboundMinSpeed, outboundMaxSpeed));
        
        Debug.Log($"[Traffic Speed Updated] Inbound: {inboundMinSpeed}-{inboundMaxSpeed} km/h | Outbound: {outboundMinSpeed}-{outboundMaxSpeed} km/h");
    }
    private System.Collections.IEnumerator ApplySpeedGradientWave(WaypointRoute route, float minSpeed, float maxSpeed)
    {
        List<VehicleMovement> vehiclesInLane = new List<VehicleMovement>();
        
        foreach (GameObject vehicle in activeVehicles)
        {
            if (!vehicle.activeInHierarchy) continue;
            
            VehicleMovement vScript = vehicle.GetComponent<VehicleMovement>();
            // เช็กว่ารถคันนี้กำลังวิ่งบนเส้นทาง (waypoints) ที่ส่งเข้ามาหรือไม่
            if (vScript != null && vScript.waypoints == route.waypoints)
            {
                vehiclesInLane.Add(vScript);
            }
        }

        // เรียงลำดับรถจาก Waypoint ไกลสุด (ปลายทาง) ย้อนกลับมาหาต้นทาง
        vehiclesInLane.Sort((a, b) => b.currentWaypointIndex.CompareTo(a.currentWaypointIndex));

        // ทยอยอัปเดตความเร็วทีละคันแบบไล่ระดับเวลา
        foreach (VehicleMovement vScript in vehiclesInLane)
        {
            vScript.targetSpeed = UnityEngine.Random.Range(minSpeed, maxSpeed);
            
            // หน่วงเวลา 0.15 วินาทีก่อนส่งสัญญาณเบรก/เร่งให้รถคันถัดไปที่อยู่ด้านหลัง
            yield return new UnityEngine.WaitForSeconds(0.15f); 
        }
    }

    private void UpdateDashboardUI()
    {
        
        // 1. อัปเดตตัวเลข Inbound
        if (inboundCountText != null) 
        {
            int totalIn = inboundCarCount + inboundMotoCount + inboundTruckCount + inboundBusCount;
            inboundCountText.text = $"INBOUND: {totalIn}\n<size=70%>Car:{inboundCarCount} Moto:{inboundMotoCount} Truck:{inboundTruckCount} Bus:{inboundBusCount}</size>";
        }
        
        // 2. อัปเดตตัวเลข Outbound
        if (outboundCountText != null) 
        {
            int totalOut = outboundCarCount + outboundMotoCount + outboundTruckCount + outboundBusCount;
            outboundCountText.text = $"OUTBOUND: {totalOut}\n<size=70%>Car:{outboundCarCount} Moto:{outboundMotoCount} Truck:{outboundTruckCount} Bus:{outboundBusCount}</size>";
        }

        // 3. 🟢 ประเมินสถานะแยกฝั่ง IN-OUT ตามคำตัดสินจาก Server โดยตรง
        if (trafficStatusText != null)
        {
            // สร้างฟังก์ชันช่วยแปลงข้อความสถานะเป็นสี จะได้ไม่ต้องเขียน if-else ซ้ำสองรอบ
            string GetColoredStatus(string state)
            {
                if (state == "standstill" || state == "high_density") 
                    return "<color=#FF4C4C>HIGH DENSITY</color>"; // สีแดง
                else if (state == "slow_moving") 
                    return "<color=#FFD166>SLOW MOVING</color>"; // สีเหลือง
                else 
                    return "<color=#06D6A0>NORMAL</color>"; // สีเขียว
            }

            // แปลงสถานะที่เซิร์ฟเวอร์ส่งมาให้กลายเป็นข้อความพร้อมโค้ดสี
            string inStatus = GetColoredStatus(currentInboundState);
            string outStatus = GetColoredStatus(currentOutboundState);

            // แสดงผลใน Text เดียวแบบขึ้นบรรทัดใหม่
            trafficStatusText.text = $"TRAFFIC STATUS\nIN: {inStatus}\nOUT: {outStatus}";
        }

        // 4. อัปเดตข้อมูลสิ่งแวดล้อม
        if (environmentDataText != null)
        {
            environmentDataText.text = "PM 2.5: <color=#FFD166>45 µg/m³</color> | WIND: 12 km/h";
        }
    }

    private IEnumerator ProcessNetworkSpawnQueue()
    {
        while (true)
        {
            if (networkSpawnQueue.Count > 0)
            {
                var netData = networkSpawnQueue.Dequeue();

                string dir = netData.direction.ToLower();
                string vType = netData.type.ToLower();

                WaypointRoute selectedRoute = null;

                if (dir == "in" || dir == "inbound") selectedRoute = inboundRoute;
                else if (dir == "out" || dir == "outbound") selectedRoute = outboundRoute;
                else
                {
                    Debug.LogWarning($"⚠️ ข้อมูล Direction ไม่ถูกต้อง: {netData.direction}");
                    continue;
                }

                if (selectedRoute == null || selectedRoute.waypoints.Count == 0) continue;

                GameObject[] selectedPrefabArray = null;

                if (vType == "motorcycle" || vType == "moto")
                {
                    selectedPrefabArray = motorcyclePrefabs;
                    if (selectedRoute == inboundRoute) inboundMotoCount++; else outboundMotoCount++;
                }
                else if (vType == "truck")
                {
                    selectedPrefabArray = truckPrefabs;
                    if (selectedRoute == inboundRoute) inboundTruckCount++; else outboundTruckCount++;
                }
                else if (vType == "bus")
                {
                    selectedPrefabArray = busPrefabs;
                    if (selectedRoute == inboundRoute) inboundBusCount++; else outboundBusCount++;
                }
                else
                {
                    selectedPrefabArray = carPrefabs;
                    if (selectedRoute == inboundRoute) inboundCarCount++; else outboundCarCount++;
                }

                UpdateDashboardUI();

                if (selectedPrefabArray == null || selectedPrefabArray.Length == 0)
                {
                    Debug.LogWarning($"⚠️ ไม่มี Prefab สำหรับรถประเภท: {vType} กรุณาใส่ Prefab ใน Inspector");
                    continue; 
                }
                
                GameObject prefabToSpawn = selectedPrefabArray[Random.Range(0, selectedPrefabArray.Length)];
                float randomLaneOffset = globalLaneOffsets[Random.Range(0, globalLaneOffsets.Length)];
                Transform startPoint = selectedRoute.waypoints[0];
                Vector3 finalSpawnPosition = startPoint.position + (startPoint.right * randomLaneOffset);

                // =========================================================================
                // 🟢 4. ระบบเช็กพื้นที่ว่างก่อนเสก (Spawn Clearance Check) ป้องกันรถทับกัน
                // =========================================================================
                bool isSpawnAreaClear = false;
                while (!isSpawnAreaClear)
                {
                    // เช็กรัศมี 4 เมตร ว่ามีวัตถุอะไรขวางจุดเกิดหรือไม่ (ปรับตัวเลข 4f ได้ตามความยาวรถ)
                    Collider[] hitColliders = Physics.OverlapSphere(finalSpawnPosition, 4f);
                    bool foundVehicle = false;

                    foreach (var hit in hitColliders)
                    {
                        // ถ้าวัตถุนั้นมีสคริปต์ VehicleMovement แปะอยู่ แปลว่าเป็นรถคันอื่น
                        if (hit.transform.root.GetComponent<VehicleMovement>() != null)
                        {
                            foundVehicle = true;
                            break; // เจอคันเดียวก็ถือว่าไม่ว่างแล้ว
                        }
                    }

                    if (foundVehicle)
                    {
                        // ถ้ามีรถขวางอยู่ ให้รอ 0.5 วินาที แล้วกลับไปเช็กพื้นที่ใหม่
                        yield return new WaitForSeconds(0.5f);
                    }
                    else
                    {
                        // พื้นที่โล่งแล้ว ทะลุลูปไปเสกรถได้เลย
                        isSpawnAreaClear = true;
                    }
                }
                // =========================================================================

                // เบิกรถจาก Pool (จะทำงานก็ต่อเมื่อ isSpawnAreaClear เป็น true แล้วเท่านั้น)
                GameObject newVehicle = GetVehicleFromPool(prefabToSpawn);
                newVehicle.transform.position = finalSpawnPosition;
                newVehicle.transform.rotation = startPoint.rotation;

                VehicleMovement vehicleScript = newVehicle.GetComponent<VehicleMovement>();
                
                // =================================================================
                // 🟢 3. จ่ายความเร็วให้รถตามเส้นทางที่รถคันนั้นกำลังวิ่ง 🟢
                // =================================================================
                float assignedTargetSpeed = 40f;
                if (selectedRoute == inboundRoute)
                {
                    assignedTargetSpeed = Random.Range(inboundMinSpeed, inboundMaxSpeed);
                }
                else
                {
                    assignedTargetSpeed = Random.Range(outboundMinSpeed, outboundMaxSpeed);
                }

                vehicleScript.targetSpeed = assignedTargetSpeed;
                vehicleScript.laneOffset = randomLaneOffset;
                vehicleScript.waypoints = selectedRoute.waypoints;

                vehicleScript.ResetVehicle();

                Debug.Log($"🚗 Spawn รถสำเร็จ: {netData.type} ฝั่ง {netData.direction} (Speed: {assignedTargetSpeed:F1} km/h)");

                yield return new WaitForSeconds(networkSpawnDelay);
            }
            else
            {
                yield return null;
            }
        }
    }

    public GameObject GetVehicleFromPool(GameObject prefab)
    {
        if (!vehiclePools.ContainsKey(prefab))
        {
            vehiclePools[prefab] = new Queue<GameObject>();
        }

        GameObject vehicle;
        if (vehiclePools[prefab].Count > 0)
        {
            vehicle = vehiclePools[prefab].Dequeue();
            vehicle.SetActive(true);
        }
        else
        {
            vehicle = Instantiate(prefab);
            vehicle.AddComponent<PoolMember>().originalPrefab = prefab;
        }

        activeVehicles.Add(vehicle);
        return vehicle;
    }

    public void ReturnVehicleToPool(GameObject vehicle)
    {
        if (!vehicle.activeInHierarchy) return;

        vehicle.SetActive(false);
        activeVehicles.Remove(vehicle);

        GameObject originalPrefab = vehicle.GetComponent<PoolMember>().originalPrefab;
        vehiclePools[originalPrefab].Enqueue(vehicle);
    }
    // 🟢 ส่งคืนสถานะที่มีความหนาแน่นสูงสุดระหว่าง Inbound และ Outbound
    public string GetDominantTrafficState()
    {
        if (currentInboundState == "standstill" || currentInboundState == "high_density" ||
            currentOutboundState == "standstill" || currentOutboundState == "high_density")
        {
            return "high_density";
        }
        
        if (currentInboundState == "slow_moving" || currentOutboundState == "slow_moving")
        {
            return "slow_moving";
        }

        return "normal";
    }
    
}

public class PoolMember : MonoBehaviour
{
    public GameObject originalPrefab;
}