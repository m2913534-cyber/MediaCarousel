# MediaCarousel 2.11 — Windows 啟動程式（由 Start-Windows.bat 呼叫）
# 第一次會自動建立執行環境（約 2–5 分鐘，需要網路）；之後雙擊即開。
# 相容 Windows PowerShell 5.1：外部程式的 stderr 不視為錯誤，一律以結束代碼判斷成敗。
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
try { $host.UI.RawUI.WindowTitle = 'MediaCarousel 2.11' } catch { }
$repair = $args -contains '--repair'
$passArgs = @($args | Where-Object { $_ -ne '--repair' })

$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = Join-Path $logDir "launch-$stamp.log"
Get-ChildItem -LiteralPath $logDir -File -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -like 'launch-*.log' -or $_.Name -like 'app-*.log' } |
  Sort-Object LastWriteTime -Descending | Select-Object -Skip 20 |
  Remove-Item -Force -ErrorAction SilentlyContinue

function Say([string]$text) {
  Write-Host $text
  Add-Content -LiteralPath $log -Value $text -Encoding UTF8
}
function Fail([string]$text) {
  Say ''
  Say "✖ $text"
  Say "  記錄檔：$log"
  exit 1
}
function Invoke-Quiet([string]$exe, [string[]]$arguments) {
  # 執行外部程式並回傳結束代碼；輸出丟棄
  try { & $exe @arguments *> $null } catch { return 999 }
  return $LASTEXITCODE
}

Say "MediaCarousel 2.11 啟動中…（$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')）"

# 解除從網路下載的封鎖標記（只處理程式本身，略過 .venv 與 logs）
$own = @(Get-ChildItem -LiteralPath $root -File -ErrorAction SilentlyContinue)
Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -notin '.venv', 'logs', '.git' } |
  ForEach-Object { $own += @(Get-ChildItem -LiteralPath $_.FullName -Recurse -File -ErrorAction SilentlyContinue) }
$own | Unblock-File -ErrorAction SilentlyContinue

# 找 64 位元 Python 3.11–3.13（PySide6 只提供 64 位元 Windows 版）
# 注意：-c 程式碼內不可含雙引號（PowerShell 5.1 會吃掉），所以用單引號 ''P''
$check = 'import sys,struct; raise SystemExit(0 if (3,11)<=sys.version_info[:2]<=(3,13) and struct.calcsize(''P'')==8 else 1)'
$candidates = New-Object System.Collections.ArrayList
if (Get-Command py -ErrorAction SilentlyContinue) {
  foreach ($v in '3.13', '3.12', '3.11') { [void]$candidates.Add(@('py', "-$v")) }
}
foreach ($name in 'python', 'python3') {
  $cmd = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
  # 略過 Microsoft Store 的空殼 python.exe（只會跳出商店）
  if ($cmd -and $cmd.Source -notlike '*\WindowsApps\*') { [void]$candidates.Add(@($cmd.Source)) }
}
foreach ($v in '313', '312', '311') {
  foreach ($base in (Join-Path $env:LOCALAPPDATA 'Programs\Python'), $env:ProgramFiles) {
    if (-not $base) { continue }
    $exe = Join-Path $base "Python$v\python.exe"
    if (Test-Path -LiteralPath $exe) { [void]$candidates.Add(@($exe)) }
  }
}
$python = $null
foreach ($c in $candidates) {
  $exe = $c[0]
  $extra = @()
  if ($c.Count -gt 1) { $extra = @($c[1..($c.Count - 1)]) }
  if ((Invoke-Quiet $exe ($extra + @('-c', $check))) -eq 0) {
    $python = (& $exe @extra -c 'import sys; print(sys.executable)' 2>$null | Select-Object -First 1)
    if ($python) { $python = $python.Trim(); break }
  }
}
if (-not $python) {
  Say '找不到 64 位元 Python 3.11–3.13。'
  Say '將開啟 python.org 下載頁：安裝 3.12（安裝時勾選 Add python.exe to PATH），再雙擊 Start-Windows.bat。'
  try { Start-Process 'https://www.python.org/downloads/windows/' } catch { }
  Fail '尚未安裝支援的 Python。'
}
$pyVersion = (& $python -c 'import sys,platform; print(sys.version.split()[0], platform.machine())' 2>$null | Select-Object -First 1).Trim()
Say "使用 Python：$python（$pyVersion）"

$venv = Join-Path $root '.venv'
$venvPy = Join-Path $venv 'Scripts\python.exe'
$venvPyw = Join-Path $venv 'Scripts\pythonw.exe'
$stampFile = Join-Path $venv '.mediacarousel-stamp'
$reqHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $root 'requirements.txt')).Hash.ToLower()
$wantStamp = "$reqHash $pyVersion"

if ($repair -and (Test-Path -LiteralPath $venv)) {
  Say '依要求重建執行環境…'
  Remove-Item -LiteralPath $venv -Recurse -Force
}
if ((Test-Path -LiteralPath $venv) -and ((Invoke-Quiet $venvPy @('-c', 'import sys')) -ne 0)) {
  Say '執行環境已失效（Python 升級或資料夾搬移），自動重建…'
  Remove-Item -LiteralPath $venv -Recurse -Force
}
if (-not (Test-Path -LiteralPath $venvPy)) {
  Say '建立執行環境（.venv）…'
  & $python -m venv $venv 2>&1 | ForEach-Object { Say "$_" }
  if (-not (Test-Path -LiteralPath $venvPy)) { Fail '無法建立執行環境。' }
}

$haveStamp = ''
if (Test-Path -LiteralPath $stampFile) { $haveStamp = (Get-Content -LiteralPath $stampFile -Raw).Trim() }
$importsOk = ((Invoke-Quiet $venvPy @('-c', 'import PySide6, numpy')) -eq 0)
if ($haveStamp -ne $wantStamp -or -not $importsOk) {
  Say '安裝／更新元件（PySide6、numpy、pywin32），第一次約需數分鐘…'
  [void](Invoke-Quiet $venvPy @('-m', 'pip', 'install', '--disable-pip-version-check', '--upgrade', 'pip'))
  & $venvPy -m pip install --disable-pip-version-check -r (Join-Path $root 'requirements.txt') 2>&1 |
    ForEach-Object { Say "$_" }
  if ($LASTEXITCODE -ne 0) { Fail '元件安裝失敗：請確認網路連線後再試；仍失敗請執行「Start-Windows.bat --repair」。' }
  Set-Content -LiteralPath $stampFile -Value $wantStamp -Encoding ASCII -NoNewline
}

Say '開啟 MediaCarousel…（這個視窗會自動縮到工作列，請勿關閉）'
$errLog = Join-Path $logDir "app-$stamp.err.log"
$runner = $venvPy
if (Test-Path -LiteralPath $venvPyw) { $runner = $venvPyw }
$appArgs = @('"' + (Join-Path $root 'app.py') + '"') + @($passArgs | ForEach-Object { '"' + $_ + '"' })
$proc = Start-Process -FilePath $runner -ArgumentList $appArgs -WorkingDirectory $root `
  -RedirectStandardError $errLog -PassThru

$consoleReady = $false
try {
  Add-Type -Name Win -Namespace MC -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindow(System.IntPtr h, int n); [DllImport("kernel32.dll")] public static extern System.IntPtr GetConsoleWindow();'
  [void][MC.Win]::ShowWindow([MC.Win]::GetConsoleWindow(), 6)
  $consoleReady = $true
} catch { }
$proc.WaitForExit()
if ($proc.ExitCode -ne 0) {
  if ($consoleReady) { [void][MC.Win]::ShowWindow([MC.Win]::GetConsoleWindow(), 9) }
  if (Test-Path -LiteralPath $errLog) { Get-Content -LiteralPath $errLog -Tail 30 | ForEach-Object { Say "$_" } }
  Fail "MediaCarousel 異常結束（代碼 $($proc.ExitCode)），完整錯誤見 $errLog"
}
if ((Test-Path -LiteralPath $errLog) -and ((Get-Item -LiteralPath $errLog).Length -eq 0)) {
  Remove-Item -LiteralPath $errLog -Force
}
exit 0
