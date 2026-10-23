MediaCarousel 2.9 — Mac 桌面版

選擇版本
Apple Silicon：適用 M 系列晶片，包含 M3 Max。
Intel：適用 Intel 處理器的 Mac。
兩版均已在各自原生 macOS 建置環境通過啟動、影片解碼與 PDF 繪製檢查。

安裝與啟動
1. 完整解壓縮 ZIP，取得 MediaCarousel.app。
2. 先開啟 MediaCarousel.app；可將 App 拖入「應用程式」保存。
3. 不需另外安裝 Python。將照片、影片或 PDF 拖入左側列表播放。
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
2.9 的 PowerPoint 原生動畫／音效自動化整合限 Windows 桌面版；Mac 可先將簡報另存 PDF 或影片後加入播放。

本版優化播放期間的音訊與介面負擔，保留原始影片解析度、幀率與既有顯示品質。
右側直立 FADER，只列出含音軌的播放影片；靜音與音量即時生效，保持播放位置。多畫面各格獨立操作，並可存入 CUE。

播放與輸出參數已移至中央預覽下方、主音量旁的「播放及輸出 ▾」。點開可調整輪播、轉場、滿版比例、畫布及輸出螢幕；按收起、Esc 或點外側關閉。

播放結束後可選擇停留最後一幀或消失，設定在中央主音量旁的「播放及輸出 ▾」。多畫面消失會露出下層影像。
本版使用既有備用播放器預載下一支影片的有效首幀，最多保留兩支、同時只準備一支；多畫面在片尾前兩秒準備。預載時音量為零、畫面隱藏，未改變影片畫質。
