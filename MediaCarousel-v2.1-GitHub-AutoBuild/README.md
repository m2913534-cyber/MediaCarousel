# MediaCarousel 2.0 — GitHub 自動打包

這個專案包包含程式與自動打包設定，尚未包含執行檔。GitHub 工作流程成功後，才能下載 Windows／Mac 執行包。使用端不需安裝 Python。

## 第一次設定（建議使用電腦）

1. 登入 https://github.com ，右上角「＋」→ New repository，名稱可填 `MediaCarousel`，建立儲存庫。不要上傳私人影片或密碼。公開庫內容人人可看；私人庫 Actions 使用量依帳戶配額計算。
2. 解壓縮本包。進入解壓縮資料夾，把裡面的程式檔案上傳到儲存庫根目錄（Add file → Upload files），再 Commit changes。不要只上傳 ZIP，也不要把所有檔案包在另一層 MediaCarousel 資料夾。
3. 網頁上傳可能漏掉隱藏的 `.github` 資料夾。請檢查儲存庫是否有 `.github/workflows/build-desktop.yml`。若沒有，點 Add file → Create new file，檔名輸入 `.github/workflows/build-desktop.yml`，把本包 `GitHub-workflow-copy.txt` 的全部內容貼入，再 Commit changes。若以 Git 上傳整個目錄，這一步可省略。
4. 點儲存庫上方 Actions。若顯示啟用提示，啟用此儲存庫的 Actions。選「Build desktop apps」→ Run workflow → Run workflow。正常的 main/master 上傳也會自動觸發。
5. 等三項建置各自完成。點該次執行紀錄，下方 Artifacts 可下載三個版本。需要登入 GitHub 並具備儲存庫讀取權限。

## 下載後開啟

| 電腦 | 下載項目 | 開啟方式 |
|---|---|---|
| Windows 64 位元 | MediaCarousel-Windows-x64 | 解壓縮 GitHub 下載包，再解壓縮裡面的執行包，打開 MediaCarousel 資料夾內的 MediaCarousel.exe。整個資料夾都要保留。 |
| Mac M1／M2／M3／M4 等 Apple 晶片 | MediaCarousel-Mac-Apple-Silicon | 解壓縮兩層包，將 MediaCarousel.app 放入「應用程式」，再開啟。M3 Max 使用此版。 |
| Mac Intel | MediaCarousel-Mac-Intel | 解壓縮兩層包，將 MediaCarousel.app 放入「應用程式」，再開啟。 |

這些包未使用 Windows 商業簽章，也未做 Apple Developer ID 簽章／公證，首次開啟可能受到系統攔截。在 Mac 確認為自己的儲存庫產物後，可依「系統設定 → 隱私權與安全性」的提示允許開啟，不需關閉系統整體保護。攝影機及螢幕擷取須授予相應權限。

## 測試範圍與失敗處理

工作流程會執行資料模型測試，打包後在該作業系統啟動成品，確認視窗與影片解碼器可初始化。這不等於驗證所有影片播放、12 路效能、音訊或實體擷取卡；請先用自己的媒體與設備測試再上正式活動。

若某個建置顯示紅色叉號，點進失敗步驟，複製錯誤訊息給我。我會修正對應設定。不要只下載原始碼（Code → Download ZIP）；執行檔在 Actions → 執行紀錄 → Artifacts。

沒有自動發佈公開 Release。Artifacts 設定保留 30 天；到期可重新執行工作流程。
