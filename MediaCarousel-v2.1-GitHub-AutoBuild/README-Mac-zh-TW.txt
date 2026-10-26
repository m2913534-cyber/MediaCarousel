MediaCarousel 2.10 — Mac 桌面版

選擇版本
Apple Silicon：適用 M 系列晶片，包含 M3 Max。
Intel：適用 Intel 處理器的 Mac。
兩版均已在各自原生 macOS 建置環境通過啟動、影片解碼與 PDF 繪製檢查。

安裝與啟動
1. 完整解壓縮 ZIP，取得 MediaCarousel.app。
2. 先開啟 MediaCarousel.app；可將 App 拖入「應用程式」保存。
3. 不需另外安裝 Python。將照片、影片、PDF 或 PPT 加入左側列表播放；PPT 原生動畫需另有 Mac 桌面版 PowerPoint。
4. 「拖曳縮放」提供四邊獨立寬高與四角自由拉伸；CUE 保存位置與寬高。

首次啟動修正
此版未做 Apple 開發者公證。若你確認下載來源為本專案，而 macOS 因下載隔離標記阻擋 App，沿用本專案的終端機修正方式：

在「終端機」輸入下列文字，最後留一個空格，先不要按 Enter：
xattr -dr com.apple.quarantine 
再把實際的 MediaCarousel.app 從 Finder 拖入終端機，按 Enter。確認沒有錯誤後重新開啟 App。

若 App 已放入「應用程式」，可使用：
xattr -dr com.apple.quarantine "/Applications/MediaCarousel.app"

另附 Start-MediaCarousel.command：保持它與 MediaCarousel.app 在同一資料夾即可使用；若腳本也無法直接開啟，可在終端機輸入 bash 後留空格，將該 .command 拖入終端機執行。它只移除包內 MediaCarousel.app 的隔離標記並開啟，不修改其他程式、不關閉整台 Mac 的 Gatekeeper，也不會修復損壞檔案或晶片架構不相容。

功能範圍
Mac 版支援圖片、影片、PDF、播放列表、多畫面、場景 CUE、畫布尺寸與自由寬高調整。
2.10 新增 Mac PowerPoint 原生放映整合。支援 .ppt、.pptx、.pps、.ppsx，由已安裝且已啟用的 Mac 桌面版 PowerPoint 播放其支援的動畫、音效與內嵌影片；不轉為靜態圖片。

本版優化播放期間的音訊與介面負擔，保留原始影片解析度、幀率與既有顯示品質。
右側直立 FADER，只列出含音軌的播放影片；靜音與音量即時生效，保持播放位置。多畫面各格獨立操作，並可存入 CUE。

播放與輸出參數已移至中央預覽下方、主音量旁的「播放及輸出 ▾」。點開可調整輪播、轉場、滿版比例、畫布及輸出螢幕；按收起、Esc 或點外側關閉。

播放結束後可選擇停留最後一幀或消失，設定在中央主音量旁的「播放及輸出 ▾」。多畫面消失會露出下層影像。
本版使用既有備用播放器預載下一支影片的有效首幀，最多保留兩支、同時只準備一支；多畫面在片尾前兩秒準備。預載時音量為零、畫面隱藏，未改變影片畫質。

Mac PPT 首次設定
1. 安裝並啟用 Microsoft PowerPoint Mac 桌面版；網頁版不能作為原生引擎。
2. 在 MediaCarousel 左側加入 PPT，雙擊播放。macOS 詢問自動化控制時選擇允許。
3. 系統設定 → 隱私權與安全性 → 自動化：允許 MediaCarousel 控制 Microsoft PowerPoint 與 System Events。
4. 同一設定頁的「輔助使用」：允許 MediaCarousel。若首次拒絕，可重新開啟程式後再播放。
5. 程式「簡報」選單也有首次設定說明。若 PowerPoint 已在放映其他簡報，請先自行結束，再從 MediaCarousel 啟動。

操作與範圍
下一步／右方向鍵／Page Down 會使用 PowerPoint 的原生按鍵，依 PPT 設定觸發下一個動畫或換頁。上一個步驟用左方向鍵／Page Up。PowerPoint 在前景時，USB／藍牙鍵盤模式簡報筆可直接操作。
支援頁碼跳轉、黑畫面、暫停／恢復與結束。結束時只退出本程式啟動的放映，不關閉簡報文件、不退出整個 PowerPoint，也不自動儲存或覆寫原始 PPT。
PPT 使用獨立的 PowerPoint 視窗。投影螢幕與自動換頁時間請在 PowerPoint 自己的投影片放映設定；不套用 MediaCarousel 的多畫面格子、非等比拉伸或影片 FADER。
Mac CUE 保存並還原投影片頁碼；動畫點擊步數不能精確讀取，因此不顯示虛構步數，也不承諾還原某一個動畫中途狀態。
若焦點在 PowerPoint 筆記或文字輸入欄位，程式不送按鍵，請先點一下放映畫面。

測試範圍
已執行程式與控制流程測試；原生 Mac 安裝包檢查會驗證 AppleScript 系統工具與權限腳本編譯。建置環境未安裝桌面版 PowerPoint，尚未實際播放 Office 動畫／音效；請使用你的 Mac PowerPoint 與實際簡報驗證。以該版本 PowerPoint 本身可播放的內容為準。
