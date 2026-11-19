using UnityEngine;
using UnityEngine.SceneManagement;

public class SceneLoader : MonoBehaviour
{
    // ฟังก์ชันนี้จะรับชื่อ Scene (string) มาจากปุ่มที่เรากด
    public void LoadSceneByName(string sceneName)
    {
        SceneManager.LoadScene(sceneName);
    }

    // (แถม) หากต้องการเปลี่ยน Scene ด้วยตัวเลข Index ใน Build Settings
    public void LoadSceneByIndex(int sceneIndex)
    {
        SceneManager.LoadScene(sceneIndex);
    }
}