#!/bin/bash
# MediaCarousel 2.11 — Mac 一鍵啟動（原始碼版）
# 第一次會自動建立執行環境（約 2–5 分鐘，需要網路）；之後雙擊即開。
# 參數：--repair 重建執行環境
set -u
root="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$root" || exit 1
mkdir -p "$root/logs"
log="$root/logs/launch-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$log") 2>&1
# 只保留最近 10 份啟動記錄
ls -1t "$root"/logs/launch-*.log 2>/dev/null | tail -n +11 | while IFS= read -r old; do rm -f -- "$old"; done

fail() {
  printf '\n✖ %s\n' "$1"
  printf '  記錄檔：%s\n' "$log"
  read -r -p '按 Return 關閉視窗。' _ || true
  exit 1
}

echo "MediaCarousel 2.11 啟動中…（$(date '+%Y-%m-%d %H:%M:%S')）"
[[ "$(uname -s)" == "Darwin" ]] || fail '此腳本只適用 macOS；Windows 請使用 Start-Windows.bat。'

# 解除下載隔離標記，避免 macOS 阻擋腳本與套件（只作用在本資料夾）
/usr/bin/xattr -dr com.apple.quarantine "$root" 2>/dev/null || true

supported='import sys; raise SystemExit(0 if (3,11) <= sys.version_info[:2] <= (3,13) else 1)'
media_python=''
for candidate in python3.13 python3.12 python3.11 \
  /Library/Frameworks/Python.framework/Versions/3.13/bin/python3 \
  /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \
  /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
  /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 /opt/homebrew/bin/python3.11 \
  /usr/local/bin/python3.13 /usr/local/bin/python3.12 /usr/local/bin/python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c "$supported" 2>/dev/null; then
    media_python="$(command -v "$candidate")"
    break
  fi
done
if [[ -z "$media_python" ]]; then
  echo '找不到 Python 3.11–3.13（macOS 內建的 Python 3.9 不支援）。'
  echo '將開啟 python.org 下載頁，安裝 3.12 後再雙擊本腳本一次。'
  /usr/bin/open 'https://www.python.org/downloads/macos/' 2>/dev/null || true
  fail '尚未安裝支援的 Python。'
fi
py_version="$("$media_python" -c 'import sys,platform; print(sys.version.split()[0], platform.machine())')"
echo "使用 Python：$media_python（$py_version）"

venv_py="$root/.venv/bin/python"
stamp_file="$root/.venv/.mediacarousel-stamp"
want_stamp="$(/usr/bin/shasum -a 256 "$root/requirements.txt" | cut -d' ' -f1) $py_version"

if [[ "${1:-}" == "--repair" ]]; then
  shift
  echo '依要求重建執行環境…'
  rm -rf "$root/.venv"
fi
# Python 升級或搬移資料夾後，舊環境會失效：自動重建
if [[ -d "$root/.venv" ]] && ! "$venv_py" -c 'import sys' >/dev/null 2>&1; then
  echo '執行環境已失效，自動重建…'
  rm -rf "$root/.venv"
fi
if [[ ! -x "$venv_py" ]]; then
  echo '建立執行環境（.venv）…'
  "$media_python" -m venv "$root/.venv" || fail '無法建立執行環境。'
fi

have_stamp="$(cat "$stamp_file" 2>/dev/null || true)"
if [[ "$have_stamp" != "$want_stamp" ]] || ! "$venv_py" -c 'import PySide6, numpy' >/dev/null 2>&1; then
  echo '安裝／更新元件（PySide6、numpy），第一次約需數分鐘…'
  "$venv_py" -m pip install --disable-pip-version-check --upgrade pip >/dev/null 2>&1 || true
  "$venv_py" -m pip install --disable-pip-version-check -r "$root/requirements.txt" \
    || fail '元件安裝失敗：請確認網路連線後再試；仍失敗可執行「Start-Mac.command --repair」。'
  printf '%s' "$want_stamp" > "$stamp_file"
fi

echo '開啟 MediaCarousel…（請保留這個終端機視窗，關閉它會一併結束程式）'
"$venv_py" "$root/app.py" "$@"
code=$?
if [[ $code -ne 0 ]]; then
  fail "MediaCarousel 異常結束（代碼 $code），錯誤訊息已寫入記錄檔。"
fi
exit 0
