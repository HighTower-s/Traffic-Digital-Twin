using UnityEngine;
using TMPro;

public class MouseHoverInfo : MonoBehaviour
{
    [Header("UI References")]
    public RectTransform tooltipPanel; // ลาก UI Panel มาใส่
    public TMP_Text tooltipText;       // ลาก UI Text มาใส่

    void Update()
    {
        // 1. ถ้าซ่อนเมาส์อยู่ (โหมดบิน) ไม่ต้องแสดง Tooltip
        if (Cursor.lockState == CursorLockMode.Locked) 
        {
            tooltipPanel.gameObject.SetActive(false);
            return;
        }

        // 2. ยิงเรย์แคสต์จากตำแหน่งเมาส์บนจอ พุ่งเข้าไปในโลก 3 มิติ
        Ray ray = Camera.main.ScreenPointToRay(Input.mousePosition);
        RaycastHit hit;

        if (Physics.Raycast(ray, out hit, 1000f))
        {
            // 3. เช็กว่าสิ่งที่ชน มีสคริปต์ RoadInfo แปะอยู่หรือไม่
            RoadInfo road = hit.collider.GetComponent<RoadInfo>();
            
            if (road != null)
            {
                // เปิดการแสดงผล Tooltip
                tooltipPanel.gameObject.SetActive(true);
                
                // ให้กรอบ UI ลอยตามตำแหน่งเมาส์ (ขยับเยื้องขวาล่างนิดหน่อยเพื่อไม่ให้บังลูกศร)
                tooltipPanel.position = Input.mousePosition + new Vector3(20, -20, 0); 

                // ดึงข้อมูลจำนวนรถจาก ScenarioManager
                int vehicleCount = road.isInbound ? ScenarioManager.Instance.GetInboundTotal() : ScenarioManager.Instance.GetOutboundTotal();
                string directionStr = road.isInbound ? "<color=#06D6A0>INBOUND</color>" : "<color=#FFD166>OUTBOUND</color>";

                // อัปเดตข้อความ
                tooltipText.text = $"<b>{road.roadName}</b>\nDIRECTION: {directionStr}\nTOTAL VEHICLES: {vehicleCount}";
            }
            else
            {
                // ถ้าชี้โดนอย่างอื่น (เช่น ตึก รถ) ให้ซ่อน Tooltip
                tooltipPanel.gameObject.SetActive(false);
            }
        }
        else
        {
            // ถ้าชี้โดนความว่างเปล่า ให้ซ่อน Tooltip
            tooltipPanel.gameObject.SetActive(false);
        }
    }
}