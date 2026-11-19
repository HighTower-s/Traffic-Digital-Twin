using System;
using UnityEngine;
using UnityEngine.UIElements;

[RequireComponent(typeof(UIDocument))]
public class TopStatusHeader : MonoBehaviour
{
    public static TopStatusHeader Instance;

    [Header("Header Layout Settings")]
    public float headerHeight = 46f;
    public Color backgroundColor = new Color(0.02f, 0.04f, 0.08f, 0.75f); // ดำน้ำเงินใส
    public Color cyanAccentColor = new Color(0f, 0.9f, 1f, 0.8f);         // สี Cyan เรืองแสง (#00E5FF)

    [Header("Data Display Inputs")]
    public string systemTitle = "SMARTFLOW DIGITAL TWIN";
    public int pingMs = 14;
    public float temperature = 32.5f;
    public float pm25Value = 48.3f;

    // UI Elements
    private VisualElement headerContainer;
    private Label connectionStatusText;
    private Label timestampText;
    private Label enviDataText;

    void Awake()
    {
        Instance = this;
    }

    void OnEnable()
    {
        UIDocument uiDoc = GetComponent<UIDocument>();
        if (uiDoc == null) return;

        VisualElement root = uiDoc.rootVisualElement;

        // 🟢 1. สร้าง แถบ Header หลัก (Container)
        headerContainer = new VisualElement();
        headerContainer.name = "top-status-header";

        // Layout & Style
        headerContainer.style.position = Position.Absolute;
        headerContainer.style.top = 0;
        headerContainer.style.left = 0;
        headerContainer.style.right = 0;
        headerContainer.style.height = headerHeight;
        headerContainer.style.flexDirection = FlexDirection.Row;
        headerContainer.style.justifyContent = Justify.SpaceBetween;
        headerContainer.style.alignItems = Align.Center;
        headerContainer.style.paddingLeft = 24;
        headerContainer.style.paddingRight = 24;
        headerContainer.style.backgroundColor = backgroundColor;

        // เส้นขอบล่างสี Cyan เรืองแสงสไตล์ Sci-Fi
        headerContainer.style.borderBottomWidth = 1.5f;
        headerContainer.style.borderBottomColor = cyanAccentColor;

        // 🟢 2. Left: connectionStatusText (สถานะการเชื่อมต่อ)
        connectionStatusText = new Label();
        connectionStatusText.style.fontSize = 12;
        connectionStatusText.style.unityFontStyleAndWeight = FontStyle.Bold;
        connectionStatusText.style.color = new Color(0.02f, 0.84f, 0.63f); // สีเขียวเรืองแสง

        // 🟢 3. Center: timestampText (ชื่อระบบ + เวลา Real-time)
        timestampText = new Label();
        timestampText.style.fontSize = 14;
        timestampText.style.unityFontStyleAndWeight = FontStyle.Bold;
        timestampText.style.color = Color.white;
        timestampText.style.letterSpacing = 1.2f;

        // 🟢 4. Right: EnviDataText (ข้อมูลสภาพแวดล้อม PM 2.5 / อุณหภูมิ)
        enviDataText = new Label();
        enviDataText.style.fontSize = 12;
        enviDataText.style.color = new Color(0.85f, 0.9f, 0.95f);

        // ประกอบ Element เข้า Header
        headerContainer.Add(connectionStatusText);
        headerContainer.Add(timestampText);
        headerContainer.Add(enviDataText);

        root.Add(headerContainer);

        // อัปเดตข้อมูลแสดงผลครั้งแรก
        UpdateHeaderUI();
    }

    void Update()
    {
        // อัปเดตเวลาและข้อมูลบน Header ทุกเฟรม
        UpdateHeaderUI();
    }

    public void UpdateHeaderUI()
    {
        if (connectionStatusText == null) return;

        // 1. connectionStatusText
        connectionStatusText.text = $"🟢 LIVE CONNECTED  |  {pingMs}ms ping";

        // 2. timestampText
        string currentTime = DateTime.Now.ToString("yyyy.MM.dd  |  HH:mm:ss");
        timestampText.text = $"{systemTitle}  •  {currentTime}";

        // 3. EnviDataText
        string pmStatus = GetPM25Status(pm25Value);
        enviDataText.text = $"🌡️ {temperature:F1}°C   |   🍃 PM 2.5: {pm25Value:F1} µg/m³ ({pmStatus})";
    }

    private string GetPM25Status(float pm)
    {
        if (pm <= 25f) return "GOOD";
        if (pm <= 50f) return "MODERATE";
        return "UNHEALTHY";
    }

    // ฟังก์ชันภายนอกสำหรับเรียกอัปเดตข้อมูลสด
    public void SetNetworkPing(int ms) => pingMs = ms;
    public void SetEnvironmentalData(float temp, float pm25)
    {
        temperature = temp;
        pm25Value = pm25;
    }
}