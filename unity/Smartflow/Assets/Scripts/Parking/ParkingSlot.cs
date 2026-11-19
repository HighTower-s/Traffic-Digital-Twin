using UnityEngine;

public class ParkingSlot : MonoBehaviour
{
    public string slotId;
    public Transform entrancePoint; // จุดหน้าซอง
    
    [HideInInspector]
    public GameObject currentVehicle; // เก็บอ้างอิงรถที่จอดอยู่
}