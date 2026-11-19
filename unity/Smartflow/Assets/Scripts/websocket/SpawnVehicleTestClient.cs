using System;
using System.Collections.Generic;
using SocketIOClient;
using UnityEngine;

namespace SmartFlow.Network
{
    public class SpawnVehicleTestClient : MonoBehaviour
    {
        [SerializeField] private string _serverUrl = "http://localhost:3000";

        private SocketIOUnity _socket;

        // 🟢 1. สร้างคิวสำหรับเก็บคำสั่งที่จะให้ทำงานบน Main Thread
        private readonly object queueLock = new object();
        private readonly Queue<Action> executeOnMainThread = new Queue<Action>();

        private void Start()
        {
            Connect();
        }

        // 🟢 2. ให้ Unity คอยหยิบคำสั่งในคิวมาทำเรื่อยๆ ทุกเฟรม (ใน Main Thread)
        private void Update()
        {
            lock (queueLock)
            {
                while (executeOnMainThread.Count > 0)
                {
                    executeOnMainThread.Dequeue().Invoke();
                }
            }
        }

        private void Connect()
        {
            var uri = new Uri(_serverUrl);
            _socket = new SocketIOUnity(uri, new SocketIOOptions
            {
                Reconnection = true,
                ReconnectionAttempts = int.MaxValue,
                ReconnectionDelay = 3000,
            });

            _socket.OnConnected += (_, _) =>
            {
                Debug.Log($"[SpawnVehicleTestClient] Connected to {_serverUrl}");
                
                // 🟢 3. นำคำสั่งอัปเดต UI ใส่คิว เพื่อให้ Update() เป็นคนเรียกใช้งาน
                lock (queueLock)
                {
                    executeOnMainThread.Enqueue(() => {
                        if (ScenarioManager.Instance != null)
                            ScenarioManager.Instance.UpdateConnectionStatus(true);
                    });
                }
            };

            _socket.OnDisconnected += (_, reason) =>
            {
                Debug.LogWarning($"[SpawnVehicleTestClient] Disconnected: {reason}");
                
                // 🟢 4. นำคำสั่งอัปเดต UI ใส่คิว
                lock (queueLock)
                {
                    executeOnMainThread.Enqueue(() => {
                        if (ScenarioManager.Instance != null)
                            ScenarioManager.Instance.UpdateConnectionStatus(false);
                    });
                }
            };

            _socket.OnError += (_, error) =>
                Debug.LogError($"[SpawnVehicleTestClient] Error: {error}");

            // สำหรับ OnUnityThread ตัว SocketIOUnity จัดการ Main Thread ให้แล้ว
            _socket.OnUnityThread("spawn_vehicle", response =>
            {
                string json;
                try
                {
                    json = response.GetValue<System.Text.Json.JsonElement>().GetRawText();
                }
                catch (Exception e)
                {
                    Debug.LogError("[SpawnVehicleTestClient] Failed to read raw payload: " + e.Message);
                    return;
                }

                SpawnVehicleEnvelope envelope;
                try
                {
                    envelope = JsonUtility.FromJson<SpawnVehicleEnvelope>(json);
                }
                catch (Exception e)
                {
                    Debug.LogError("[SpawnVehicleTestClient] Failed to parse payload: " + e.Message);
                    return;
                }

                if (envelope?.data == null) return;

                if (ScenarioManager.Instance != null)
                {
                    ScenarioManager.Instance.SpawnVehicleFromNetwork(envelope.data);
                }
            });

            // ==========================================
            // 🟢 เพิ่มส่วนดักฟัง traffic_state ตรงนี้ 🟢
            // ==========================================
            _socket.OnUnityThread("traffic_state", response =>
            {
                string json;
                try
                {
                    json = response.GetValue<System.Text.Json.JsonElement>().GetRawText();
                }
                catch (Exception e)
                {
                    Debug.LogError("[SpawnVehicleTestClient] Failed to read traffic_state raw payload: " + e.Message);
                    return;
                }

                TrafficStatePayload payload;
                try
                {
                    payload = JsonUtility.FromJson<TrafficStatePayload>(json);
                }
                catch (Exception e)
                {
                    Debug.LogError("[SpawnVehicleTestClient] Failed to parse traffic_state payload: " + e.Message);
                    return;
                }

                if (payload != null && ScenarioManager.Instance != null)
                {
                    // คุณสามารถสร้างฟังก์ชัน UpdateTrafficState ใน ScenarioManager เพื่อนำข้อมูลไปใช้งานต่อ
                    ScenarioManager.Instance.UpdateTrafficState(payload);
                    Debug.Log($"[Traffic] สถานะการจราจรภาพรวม: {payload.trafficState}");
                }
            });

            // 🟢 ต้องนำการดักฟังทั้งหมดไว้ก่อนคำสั่ง Connect()
            _socket.Connect();
        }

        private void OnDestroy()
        {
            _socket?.Disconnect();
        }
    }
}
//เนื่องจากเหตุการณ์ OnConnected ถูกเรียกจากหลังบ้าน (Background Thread) ซึ่ง Unity ไม่อนุญาตให้แก้ไข UI (Text) จากตรงนั้น 
// เราจึงใช้ lock (queueLock) เพื่อแพ็กคำสั่งอัปเดตสถานะเป็นกล่องพัสดุไว้ แล้วให้ฟังก์ชัน Update() ที่ทำงานบนระบบหลักของ Unity (Main Thread) 
// มาแกะกล่องและอัปเดตหน้าจอให้ครับ วิธีนี้รับรองว่าไม่มี Error ชนกันแน่นอนครับ
// update code 9/25