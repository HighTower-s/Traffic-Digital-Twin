using UnityEngine;

public class SimpleFly : MonoBehaviour
{
    [Header("Movement Settings")]
    public float flySpeed = 10f; // ความเร็วในการบิน

    [Header("Look Settings")]
    public float lookSensitivity = 2f; // ความไวของเมาส์

    // ตัวแปรเก็บค่าองศาการหมุนของกล้อง
    private float rotationX = 0f;
    private float rotationY = 0f;

    void Start()
    {
        // ซ่อนลูกศรเมาส์และล็อกไว้กึ่งกลางจอ
        Cursor.lockState = CursorLockMode.Locked;
        Cursor.visible = false;

        // ดึงองศาปัจจุบันของกล้องมาตั้งเป็นค่าเริ่มต้น
        Vector3 rot = transform.localRotation.eulerAngles;
        rotationY = rot.y;
        rotationX = rot.x;
    }

    void Update()
    {
        if (Input.GetMouseButton(1))
        {
            // ซ่อนและล็อกเมาส์ให้อยู่ตรงกลางจอชั่วคราว เพื่อให้หมุนกล้องได้ลื่นไหลไม่ติดขอบจอ
            Cursor.lockState = CursorLockMode.Locked;
            Cursor.visible = false;
            // --- 1. ระบบหันกล้องด้วยเมาส์ (Mouse Look) ---
        float mouseX = Input.GetAxis("Mouse X") * lookSensitivity;
        float mouseY = Input.GetAxis("Mouse Y") * lookSensitivity;

        rotationY += mouseX;
        rotationX -= mouseY; // ลบค่า Y เพื่อให้การดึงเมาส์ลง = ก้มหน้า (ทิศทางธรรมชาติ)

        // ล็อกมุมก้ม-เงย ไว้ที่ -90 ถึง 90 องศา (ป้องกันกล้องหมุนตีลังกากลับหลัง)
        rotationX = Mathf.Clamp(rotationX, -90f, 90f);

        // สั่งหมุนกล้อง
        transform.localRotation = Quaternion.Euler(rotationX, rotationY, 0f);
        }
        else
        {
            // เมื่อปล่อยคลิกขวา ให้แสดงเมาส์และปลดล็อกทันทีเพื่อนำไปชี้ UI ได้
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
        }
        
        
        // --- 2. ระบบเคลื่อนที่ (Movement) ---
        float x = Input.GetAxis("Horizontal");
        float z = Input.GetAxis("Vertical");
        float y = 0f;
        
        if (Input.GetKey(KeyCode.Space)) 
        {
            y = 1f; // บินขึ้น
        }
        else if (Input.GetKey(KeyCode.LeftShift)) 
        {
            y = -1f; // บินลง
        }

        Vector3 moveDirection = new Vector3(x, y, z);

        // ขยับตัวไปตามทิศทางที่กล้องกำลังหันอยู่
        transform.Translate(moveDirection * flySpeed * Time.deltaTime);

        // --- 3. ระบบปลดล็อกเมาส์ ---
        // กดปุ่ม ESC เพื่อปลดล็อกลูกศรเมาส์ให้กลับมาคลิกอะไรต่างๆ บนจอได้
        if (Input.GetKeyDown(KeyCode.Escape))
        {
            Cursor.lockState = CursorLockMode.None;
            Cursor.visible = true;
        }
        
        // คลิ๊กซ้ายที่จอเพื่อล็อกเมาส์กลับไปบินต่อ
        if (Input.GetMouseButtonDown(1))
        {
            Cursor.lockState = CursorLockMode.Locked;
            Cursor.visible = false;
        }
    }
}