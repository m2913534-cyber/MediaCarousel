# MediaCarousel 2.11 · 一鍵啟動與現場穩定性

以 2.10（commit 4572dbd）為基礎，功能與專案檔格式不變，舊的 `.mcarousel` 直接沿用。

## 啟動腳本（Mac／Windows）
- Mac：`Start-Mac.command`；Windows：`Start-Windows.bat`（呼叫 `launcher/launch-windows.ps1`）。
- 自動尋找 Python 3.11–3.13（原本只接受 3.11／3.12）。Windows 不再必須安裝 `py` 啟動器，也會略過 Microsoft Store 的空殼 python.exe，並確認是 64 位元。
- 找不到 Python 時自動開啟 python.org 下載頁。
- `requirements.txt` 或 Python 版本改變時自動更新元件；沒變就直接開，不再每次跑 `venv`。
- Python 升級或資料夾搬移造成環境失效時自動重建；也可加 `--repair` 手動重建。
- 每次啟動寫入 `logs/` 記錄檔（保留最近幾份），程式異常結束時顯示錯誤末段與記錄檔位置。
- 自動解除下載隔離／封鎖標記（只處理本資料夾）。Windows 啟動後主控台自動縮到工作列。

## 現場操作
- 單畫面播放中「移除」或「上移／下移」其他項目，不再中斷輸出；正在播放的項目跟著新位置走，下一個仍依新順序播放。
  移除正在播放的項目、轉場進行中、多畫面模式或 PowerPoint 放映時，仍維持原本的安全行為（先停止）。
- 在數值、文字欄位輸入時，空白鍵與左右方向鍵不再觸發播放／暫停或換片；下拉選單有焦點時空白鍵開啟選單。F11 不受影響。
- 上次場景檔讀取失敗時，改為備份成 `last-session-unreadable-日期.mcarousel` 並繼續自動保存（2.10 會整段停止自動保存）。

## 省電
- 主畫面計時器：影片與轉場 60 Hz、圖片／PDF 20 Hz、閒置與 PowerPoint 放映 10 Hz；開始播放或轉場時立即回到 60 Hz。
- 多畫面合成器：有畫面在播放時 60 Hz，閒置 10 Hz。

## 驗證範圍
- 全部 Python 模組語法編譯通過；`test_model.py` 6 項通過。
- 清單移除／排序的播放位置對應以獨立邏輯測試驗證 9 種情境。
- Mac 啟動腳本在模擬環境實跑：首次建立、元件已就緒直接開啟、requirements 變更重裝、`--repair`、程式異常結束回報。
- 未驗證：建置環境沒有 PySide6、無法開 GUI，也沒有 Windows／PowerShell；計時器調整、快捷鍵保護與 Windows 啟動腳本需在實機確認。
