using UnityEngine;

[System.Serializable]
public class ParkingSequenceWrapper
{
    public DemoParkingEvent[] demo_sequence;
}

[System.Serializable]
public class DemoParkingEvent
{
    public string slot_id;
    public string vehicle_type;
    public bool is_occupied;
    public float delay_seconds;
}