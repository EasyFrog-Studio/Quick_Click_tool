# Quick Click 智能滑鼠連點器

一個 Windows 用的滑鼠連點器：按 F4 開始或停止在滑鼠目前的位置連續點擊左鍵，可以設定點擊間隔，也可以設定點滿幾次後自動停止。

## 使用方式

雙擊 `Quick_Click_tool\Quick_Click.lnk` 開啟程式。如果捷徑打不開，就直接雙擊 `Quick_Click_tool\Quick_Click\Quick_Click.exe`。

| 欄位 | 說明 |
|---|---|
| 點擊間隔（秒） | 兩次點擊之間的秒數，預設 0.05，最小 0.01 |
| 點擊次數 | 留空代表不限次數；填正整數 N，點滿 N 次後自動停止 |

- **F4**：開始或停止。視窗縮小、焦點在其他程式時也有效。
- **緊急停止**：把滑鼠移到螢幕任一角落，連點會立刻停止。
- 每次開始都是新的一輪，計數從 0 算起。中途停止後再開始，也會從 0 重新計算。
- 連點進行中，兩個欄位都無法修改。

狀態列的意思：

| 狀態 | 意思 |
|---|---|
| ● 已暫停 | 目前沒在點擊 |
| ● 連點中 | 正在點擊 |
| ● 已完成 N 次 | 已點滿設定的次數，按 F4 開始下一輪 |
| ● 已強制停止 | 滑鼠移到螢幕角落，觸發了緊急停止 |
| ● 發生錯誤：… | 點擊時發生錯誤，後面接著錯誤原因 |

欄位填了不合法的值時，錯誤訊息會用紅字顯示在該欄位下方，連點不會開始。

### 限制

- 程式以一般權限執行，所以點不到以系統管理員身分開啟的視窗（例如部分遊戲、工作管理員），在這類視窗裡 F4 也收不到。遇到這種情況，請對 `Quick_Click.exe` 按右鍵，選「以系統管理員身分執行」。
- 如果把 `Quick_Click_tool` 資料夾搬到別處，捷徑的圖示可能會變成通用圖示。

## 開發

需要 Windows 和 Python 3.12。

```powershell
cd Quick_Click
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

不打包、直接從原始碼執行：

```powershell
.venv\Scripts\python.exe app.py
```

執行測試：

```powershell
.venv\Scripts\python.exe -m pytest -q
```

測試用假的點擊函式取代真的滑鼠點擊，跑測試時不會點到你的桌面。部分介面測試會建立隱藏的視窗，所以需要有桌面環境。

### 程式結構

| 檔案 | 內容 |
|---|---|
| `clicker_core.py` | 連點核心：檢查輸入、在背景執行緒點擊、計數，以及開始、停止、完成、錯誤等狀態。不依賴任何 GUI |
| `app.py` | CustomTkinter 視窗和 F4 熱鍵，也是程式進入點 |
| `tests/` | `clicker_core` 的測試，以及介面的畫面內容與操作測試 |
| `build.ps1` | 打包腳本 |

F4 熱鍵在另一個執行緒上觸發，它只把請求放進佇列；視窗每 100 毫秒檢查一次佇列，再在介面執行緒處理，所以熱鍵執行緒不會直接操作視窗。

## 打包

```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

腳本會刪掉上次的輸出，用 PyInstaller 重新打包，再重建捷徑。打包失敗時，腳本會停下來並回報錯誤。輸出放在 repo 外面、和 repo 同一層的 `Quick_Click_tool`：

```
Quick_Click_tool/
├─ Quick_Click/          執行檔和執行所需的檔案
│  └─ Quick_Click.exe
└─ Quick_Click.lnk       雙擊這個開啟
```

打包過程的暫存檔放在 `build/`，這個資料夾不進版控。

打包前請先關閉正在執行的 `Quick_Click.exe`，否則舊檔被占用，腳本會刪除失敗。
