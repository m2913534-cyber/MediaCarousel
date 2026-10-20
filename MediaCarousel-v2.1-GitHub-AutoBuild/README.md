# MediaCarousel — Windows / Mac 桌面版

## 正式版本下載

**[下載最新正式版](https://github.com/m2913534-cyber/MediaCarousel/releases/latest)**

每個正式版本提供：

| 平台 | Release 附件 | 使用方式 |
| --- | --- | --- |
| Windows x64 | `MediaCarousel-Windows-x64.zip` | 解壓一次，開啟 `MediaCarousel/MediaCarousel.exe`；請保留整個資料夾 |
| Mac Apple Silicon（含 M3 Max） | `MediaCarousel-Mac-Apple-Silicon.zip` | 解壓一次，將 `MediaCarousel.app` 拖進「應用程式」後開啟 |
| Mac Intel | `MediaCarousel-Mac-Intel.zip` | 解壓一次，將 `MediaCarousel.app` 拖進「應用程式」後開啟 |

正式 Release 另附 `SHA256SUMS.txt`，用來檢查下載檔案是否完整。Windows PowerShell 可用 `Get-FileHash .\\MediaCarousel-Windows-x64.zip -Algorithm SHA256`；Mac 終端機可用 `shasum -a 256 MediaCarousel-Mac-Apple-Silicon.zip`（Intel 請替換檔名），將結果與清單比對。

**注意：** 尚未使用 Windows 商業程式碼簽章，Mac 也尚未進行 Apple Developer ID 簽章與公證。Mac 首次開啟若遭阻擋，請先確認檔案來源，再到「系統設定 → 隱私權與安全性」允許開啟；不要關閉系統整體安全保護。擷取裝置、攝影機、螢幕錄製等權限仍需自行授權。

## 維護者：建立正式版本

1. 先將更新合併到 `main`，確認一般建置流程三平台成功。
2. 建立指向已審核 commit 的新版本標籤（例如 `v2.1.0`）並推送：`git tag v2.1.0 && git push origin v2.1.0`。標籤請勿重複使用。
3. `Build desktop apps` 會針對該標籤重新建置三平台，執行 `ci_verify.py`，產生完整 ZIP；全部成功後才建立 GitHub Release。
4. Release 附件會有三個 ZIP、`SHA256SUMS.txt`，以及 GitHub 自動產生的版本更新紀錄。請在正式對外公告前檢查版本說明，補充人工測試結果與已知限制。
5. 若發佈失敗，查看 Actions 錯誤並修復；不要把失敗的標籤當成正式可下載版本。

平常推送 `main` 或手動執行工作流程仍只建立暫存 Artifacts，保留 30 天。**只有推送 `v*` 版本標籤會觸發 Release**。正式下載請使用 Releases 頁面，不要分享 Artifacts 暫時網址。

## 測試界線

CI 執行建置及 `ci_verify.py` 的自動檢查，並驗證 ZIP 可解壓。這**不代表**已在實際 Windows、Mac M3 Max、Intel Mac 裝置完成安裝、開啟、影片解碼、12 畫面效能、音訊輸出或擷取卡驗證。正式活動前仍須以實際設備、素材及輸出裝置進行測試。

這項發佈流程只改變包裝與下載方式，不承諾修改或修復播放器功能。
