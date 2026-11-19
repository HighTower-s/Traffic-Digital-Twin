using System;

namespace SmartFlow.Network
{
    [Serializable]
    public class SpawnVehicleEnvelope
    {
        public string @event;
        public SpawnVehicleData data;
    }

    [Serializable]
    public class SpawnVehicleData
    {
        public string trackId;
        public string type;
        public string direction;
        public string cameraId;
        public string timestamp;
    }
}
