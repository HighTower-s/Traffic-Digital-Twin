using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UIElements;

[RequireComponent(typeof(UIDocument))]
public class TrafficGraphUIToolkit : MonoBehaviour
{
    public static TrafficGraphUIToolkit Instance;

    // 🟢 ประกาศตัวแปร Layout ที่ขาดหายไป
    [Header("Panel Layout Settings")]
    public float panelWidth = 320f;
    public float panelHeight = 180f;
    public float positionLeft = 20f;
    public float positionBottom = 20f;
    public Color panelBackgroundColor = new Color(0f, 0f, 0f, 0.6f);

    [Header("Graph Line Styling")]
    public Color normalColor = new Color(0.02f, 0.84f, 0.63f); // สีเขียว
    public Color slowColor = new Color(1.0f, 0.82f, 0.4f);     // สีเหลือง
    public Color heavyColor = new Color(1.0f, 0.3f, 0.3f);    // สีแดง
    public float lineWidth = 3.5f;
    public float nodeRadius = 5f;

    private UIDocument uiDocument;
    private VisualElement graphContainer;

    void Awake()
    {
        Instance = this;
    }

    void OnEnable()
    {
        uiDocument = GetComponent<UIDocument>();
        if (uiDocument == null) return;

        VisualElement root = uiDocument.rootVisualElement;

        // 1. สร้าง VisualElement ขึ้นมาใหม่ผ่าน C#
        graphContainer = new VisualElement();
        graphContainer.name = "traffic-graph-panel";

        // 2. กำหนด Style ขนาด ตำแหน่ง และสี
        graphContainer.style.width = panelWidth;
        graphContainer.style.height = panelHeight;
        graphContainer.style.position = Position.Absolute;
        graphContainer.style.left = positionLeft;
        graphContainer.style.bottom = positionBottom;
        graphContainer.style.backgroundColor = panelBackgroundColor;
        
        graphContainer.style.borderTopLeftRadius = 8;
        graphContainer.style.borderTopRightRadius = 8;
        graphContainer.style.borderBottomLeftRadius = 8;
        graphContainer.style.borderBottomRightRadius = 8;

        root.Add(graphContainer);

        // 3. ผูกฟังก์ชันวาด Vector Graphics
        graphContainer.generateVisualContent += DrawVectorGraph;
        graphContainer.MarkDirtyRepaint();
    }

    void OnDisable()
    {
        if (graphContainer != null)
        {
            graphContainer.generateVisualContent -= DrawVectorGraph;
        }
    }

    public void RefreshGraph()
    {
        graphContainer?.MarkDirtyRepaint();
    }

    private void DrawVectorGraph(MeshGenerationContext mgc)
    {
        if (TrafficHistoryTracker.Instance == null) return;

        List<TrafficHistoryTracker.TrafficDataPoint> history = TrafficHistoryTracker.Instance.GetHistoryList();
        if (history == null || history.Count == 0) return;

        Painter2D painter = mgc.painter2D;
        Rect rect = graphContainer.contentRect;

        float width = rect.width;
        float height = rect.height;

        float paddingX = 15f;
        float paddingY = 20f;
        float usableWidth = width - (paddingX * 2f);
        float usableHeight = height - (paddingY * 2f);

        float GetY(int statusValue)
        {
            float normalized = (statusValue - 1f) / 2f;
            return paddingY + usableHeight * (1f - normalized);
        }

        int maxPoints = 7;
        float stepX = usableWidth / (maxPoints - 1);

        List<Vector2> points = new List<Vector2>();
        for (int i = 0; i < history.Count; i++)
        {
            float x = paddingX + (i * stepX);
            float y = GetY(history[i].statusValue);
            points.Add(new Vector2(x, y));
        }

        int latestStatus = history[history.Count - 1].statusValue;
        Color currentColor = GetColorByStatus(latestStatus);

        // วาดเส้นกราฟ
        painter.lineWidth = lineWidth;
        painter.lineCap = LineCap.Round;
        painter.lineJoin = LineJoin.Round;
        painter.strokeColor = currentColor;

        painter.BeginPath();
        painter.MoveTo(points[0]);
        for (int i = 1; i < points.Count; i++)
        {
            painter.LineTo(points[i]);
        }
        painter.Stroke();

        // วาดจุด Node
        for (int i = 0; i < points.Count; i++)
        {
            painter.BeginPath();
            painter.fillColor = currentColor;
            painter.Arc(points[i], nodeRadius, 0f, 360f);
            painter.Fill();
        }
    }

    private Color GetColorByStatus(int statusValue)
    {
        switch (statusValue)
        {
            case 3: return heavyColor;
            case 2: return slowColor;
            default: return normalColor;
        }
    }
}