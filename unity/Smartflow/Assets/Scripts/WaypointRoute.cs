using System.Collections.Generic;
using UnityEngine;

public class WaypointRoute : MonoBehaviour
{
    [Tooltip("ใส่จุด Waypoints เรียงตามลำดับ")]
    public List<Transform> waypoints = new List<Transform>();

    // วาดเส้นสีเขียวให้เห็นในหน้าต่าง Scene
    void OnDrawGizmos()
    {
        if (waypoints == null || waypoints.Count < 2) return;
        
        Gizmos.color = Color.green;
        for (int i = 0; i < waypoints.Count - 1; i++)
        {
            if (waypoints[i] != null && waypoints[i+1] != null)
            {
                Gizmos.DrawLine(waypoints[i].position, waypoints[i+1].position);
            }
        }
    }
}