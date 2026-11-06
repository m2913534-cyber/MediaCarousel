# MediaCarousel 2.10 · Mac PowerPoint 原生動畫整合

Mac 加入 PowerPoint 原生放映介面，由本機已安裝且已啟用的 Microsoft PowerPoint 桌面版處理 PPT 動畫、音效與內嵌影片。支援 PPT/PPTX/PPS/PPSX；不經圖片或 PDF 轉換，沿用 PowerPoint 可播放的效果。

透過原生 AppleScript 啟動與監看放映；下一步／上一步使用 PowerPoint 原生方向鍵，讓 PowerPoint 判斷動畫步驟與換頁。支援程式內按鈕與鍵盤模式簡報筆，以及頁碼、暫停、黑畫面與結束控制。需要 macOS 自動化和輔助使用授權，拒絕時顯示對應設定路徑；App 包含 Apple Events 用途說明。

腳本在工作執行緒編譯一次並重用，檔案路徑以參數傳入，不插入 shell 或腳本原始碼。按鍵僅送至已確認的 PowerPoint 放映視窗，文字輸入欄位不送按鍵。新啟動、停止及關閉會取消舊的排隊控制；動畫／換頁忙碌不自動重送按鍵。已在播放其他 PowerPoint 放映時拒絕接管；結束不退出整個 PowerPoint、不關閉簡報文件或儲存來源。

Mac 的輸出螢幕與自動換頁沿用 PowerPoint 設定。CUE 保存頁碼，動畫點擊步數保留為未知，不顯示虛構 0 或承諾精確動畫狀態還原。Windows 的 COM 原生播放與動畫 CUE 保留。

驗證包含 Mac 介面的模擬測試：原生按鍵命令、路徑參數、權限診斷、取消、忙碌處理、排隊代次、啟動中斷清理與既有放映保留；另執行 PDF／簡報筆／Windows COM 契約、影片與介面回歸檢查。Mac 原生建置檢查驗證系統 AppleScript 工具及 OS 權限腳本編譯，不會在無人值守的 CI 要求 Office 控制權限。

建置環境沒有安裝桌面版 PowerPoint，沒有進行 Office 動畫、音效及實際簡報筆的端到端實測。需在已安裝且已授權的 Mac PowerPoint 實機確認。
