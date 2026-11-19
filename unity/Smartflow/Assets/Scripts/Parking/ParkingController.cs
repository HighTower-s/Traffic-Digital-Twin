using System.Collections;
using UnityEngine;
using UnityEngine.AI;

public class ParkingController : MonoBehaviour
{
    private NavMeshAgent agent;
    public float parkDuration = 2.0f;

    void Awake()
    {
        agent = GetComponent<NavMeshAgent>();
    }

    // ==========================================
    // ส่วนที่ 1: อนิเมชันขาเข้า (วิ่งมาหน้าซอง -> ตั้งลำ -> ถอยเข้า)
    // ==========================================
    public void StartParkingProcess(Transform entrance, Transform slotArea)
    {
        StartCoroutine(DriveToSlotAndPark(entrance, slotArea));
    }

    private IEnumerator DriveToSlotAndPark(Transform entrance, Transform slot)
    {
        // 1. ขับด้วย NavMesh มาที่หน้าซอง
        if (agent != null)
        {
            agent.enabled = true;
            agent.SetDestination(entrance.position);
            while (agent.pathPending || agent.remainingDistance > 0.1f) { yield return null; }
            agent.enabled = false; // ปิด NavMesh เพื่อเริ่มทำ Lerp ถอยเข้าซอง
        }

        // 2. อนิเมชันถอยเข้าซอง (ตั้งลำ 40% -> ถอยหลัง 60%)
        float setupDuration = parkDuration * 0.75f;
        float reverseDuration = parkDuration * 0.5f;

        // จังหวะ 2.1: ขับเดินหน้าตั้งลำ (เฉียงออกไปข้างหน้า)
        float elapsedTime = 0;
        Vector3 startPos = transform.position;
        Quaternion startRot = transform.rotation;
        Vector3 setupPos = startPos + (transform.forward * 2.0f) + (transform.right * 1.5f);
        Quaternion setupRot = slot.rotation; 

        while (elapsedTime < setupDuration)
        {
            float t = elapsedTime / setupDuration;
            transform.position = Vector3.Lerp(startPos, setupPos, t);
            transform.rotation = Quaternion.Lerp(startRot, setupRot, t);
            elapsedTime += Time.deltaTime;
            yield return null;
        }

        // จังหวะ 2.2: ถอยหลังตรงๆ เข้าซอง
        elapsedTime = 0;
        Vector3 reverseStartPos = transform.position;

        while (elapsedTime < reverseDuration)
        {
            float t = elapsedTime / reverseDuration;
            float smoothT = Mathf.SmoothStep(0, 1, t); // ทำให้ค่อยๆ เบรกตอนจอดสนิท
            transform.position = Vector3.Lerp(reverseStartPos, slot.position, smoothT);
            elapsedTime += Time.deltaTime;
            yield return null;
        }

        // จัดระเบียบตอนจอดให้ตรงเป๊ะ
        transform.position = slot.position;
        transform.rotation = slot.rotation;
    }

    // ==========================================
    // ส่วนที่ 2: อนิเมชันขาออก (ขับออกจากซอง -> วิ่งกลับจุด Spawn -> ทำลายตัวเอง)
    // ==========================================
    public void StartExitingProcess(Transform entrance, Transform exitPoint)
    {
        StartCoroutine(ExitSlotAndDriveAway(entrance, exitPoint));
    }

    private IEnumerator ExitSlotAndDriveAway(Transform entrance, Transform exitPoint)
    {
        // 1. ขับเดินหน้าออกจากซองไปที่จุด Entrance (หน้าซอง)
        float elapsedTime = 0;
        Vector3 startPos = transform.position;
        Quaternion startRot = transform.rotation;

        // ใช้เวลาครึ่งหนึ่งของ parkDuration ในการขับออกจากซอง
        while (elapsedTime < (parkDuration * 0.5f)) 
        {
            float t = elapsedTime / (parkDuration * 0.5f);
            float smoothT = Mathf.SmoothStep(0, 1, t);
            
            transform.position = Vector3.Lerp(startPos, entrance.position, smoothT);
            transform.rotation = Quaternion.Lerp(startRot, entrance.rotation, smoothT);
            
            elapsedTime += Time.deltaTime;
            yield return null;
        }

        // 2. เปิด NavMesh ให้ขับกลับไปที่จุดหมาย (Global Spawn Point)
        if (agent != null)
        {
            agent.enabled = true;
            agent.SetDestination(exitPoint.position);
            
            // รอจนกว่าจะขับไปถึงจุดหมาย (เผื่อระยะไว้ 0.5 หน่วยกันบั๊ก)
            while (agent.pathPending || agent.remainingDistance > 0.5f) 
            { 
                yield return null; 
            }
        }

        // 3. เมื่อถึงทางออกแล้ว ให้ทำลายโมเดลรถทิ้ง
        Destroy(gameObject);
    }
}