#!/bin/bash
set -eu
package_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
app_path="$package_dir/MediaCarousel.app"
fail() {
  printf '\n%s\n' "$1"
  printf '請參閱同一資料夾的 README-Mac-zh-TW.txt。\n'
  read -r -p '按 Enter 關閉。' answer || true
  exit 1
}
[[ "$(uname -s)" == "Darwin" ]] || fail '此工具僅適用 macOS。'
[[ -d "$app_path" ]] || fail '找不到同一資料夾的 MediaCarousel.app，請先完整解壓縮。'
/usr/bin/xattr -dr com.apple.quarantine "$app_path" || fail '無法移除 MediaCarousel 的下載隔離標記，請檢查此 App 的讀寫權限。'
/usr/bin/open "$app_path" || fail 'MediaCarousel 無法開啟，請確認下載的版本符合這台 Mac 的晶片。'
