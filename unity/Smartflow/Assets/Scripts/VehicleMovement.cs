using System.Collections.Generic;
using UnityEngine;

public class VehicleMovement : MonoBehaviour
{
    [HideInInspector] public float targetSpeed; 
    [HideInInspector] public float laneOffset; // รับค่าเลนจาก Manager
    [HideInInspector] public List<Transform> waypoints; // จุดทั้งหมดที่ต้องวิ่งผ่าน
// ... ตัวแปรต่างๆ ...
    public int currentWaypointIndex = 0;

    // 🟢 สร้างฟังก์ชันนี้เพิ่ม เพื่อล้างค่าให้รถเหมือนเพิ่งออกจากโรงงาน 🟢
    public void ResetVehicle()
    {
        currentWaypointIndex = 0;
        currentSpeed = targetSpeed;
    }
    private float currentSpeed;

    [Header("Traffic AI Settings")]
    public float safeDistance = 5f; 
    public float acceleration = 2f;
    public float turnSpeed = 5f; // ความไวในการเลี้ยวพวงมาลัย
    public float stopDistance = 1.5f; // ระยะที่ถือว่าขับมาถึงจุด Waypoint แล้ว
    public LayerMask obstacleLayer;
    void Start()
    {
        currentSpeed = targetSpeed;
    }

    void Update()
    {
        // 1. ตรวจสอบว่าวิ่งครบทุกจุดหรือยัง (ถ้าครบแล้วให้ลบรถทิ้ง)
       // 1. ตรวจสอบว่าวิ่งครบทุกจุดหรือยัง
        if (waypoints == null || currentWaypointIndex >= waypoints.Count)
        {
            // 🟢 เปลี่ยนจาก Destroy เป็นส่งคืน Pool 🟢
            ScenarioManager.Instance.ReturnVehicleToPool(gameObject);
            return;
        }

        // 2. คำนวณจุดหมาย (ตำแหน่ง Waypoint + ระยะขยับซ้าย/ขวาของเลน)
        Transform targetWaypoint = waypoints[currentWaypointIndex];
        Vector3 targetPosition = targetWaypoint.position + (targetWaypoint.right * laneOffset);
        
        // ล็อกแกน Y ไว้ไม่ให้รถแหงนหน้าขึ้นลงตาม Waypoint ที่อาจจะวางลอยฟ้า
        targetPosition.y = transform.position.y; 

        // 3. ค่อยๆ หมุนรถหันหน้าไปหา Waypoint
        Vector3 directionToTarget = (targetPosition - transform.position).normalized;
        if (directionToTarget != Vector3.zero)
        {
            Quaternion targetRotation = Quaternion.LookRotation(directionToTarget);
            transform.rotation = Quaternion.Slerp(transform.rotation, targetRotation, Time.deltaTime * turnSpeed);
        }

        // 4. ระบบ Raycast เบรกกันชน (เหมือนเดิม)
        Vector3 rayOrigin = transform.position + (Vector3.up * 0.5f) + (transform.forward * 1.5f);
        if (Physics.Raycast(rayOrigin, transform.forward, out RaycastHit hit, safeDistance, obstacleLayer))
        {
            currentSpeed = Mathf.Lerp(currentSpeed, 0f, Time.deltaTime * acceleration * 2f);
        }
        else
        {
            currentSpeed = Mathf.Lerp(currentSpeed, targetSpeed, Time.deltaTime * acceleration);
        }

        // 5. วิ่งไปข้างหน้า (แปลงหน่วยเป็น km/h แล้ว)
        float speedInMetersPerSecond = currentSpeed / 3.6f;
        transform.Translate(Vector3.forward * speedInMetersPerSecond * Time.deltaTime);

        // 6. ตรวจสอบว่าวิ่งมาถึงจุดนี้หรือยัง ถ้าถึงแล้วให้เปลี่ยนไปเป้าหมายถัดไป
        float distanceToTarget = Vector3.Distance(new Vector3(transform.position.x, 0, transform.position.z), 
                                                  new Vector3(targetPosition.x, 0, targetPosition.z));
        if (distanceToTarget <= stopDistance)
        {
            currentWaypointIndex++;
        }
    }
}