# ライブチケット管理 & カード管理 Windows セットアップスクリプト
# 使い方: powershell -ExecutionPolicy Bypass -File "kodama-setup.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Step  { param($n,$t,$msg) Write-Host "`n[$n/$t] $msg" -ForegroundColor Cyan }
function Write-Ok    { param($msg) Write-Host "  v $msg" -ForegroundColor Green }
function Write-Info  { param($msg) Write-Host "  -> $msg" -ForegroundColor Yellow }
function Write-Fail  { param($msg) Write-Host "  x $msg" -ForegroundColor Red }

Write-Host '================================================' -ForegroundColor Cyan
Write-Host '  ライブチケット管理 & カード管理 セットアップ' -ForegroundColor Cyan
Write-Host '================================================' -ForegroundColor Cyan

$TOTAL = 3

# ---- Step 1: Node.js の確認 ----
Write-Step 1 $TOTAL 'Node.js の確認'
try {
    $nodeVersion = & node --version 2>&1
    if ($LASTEXITCODE -ne 0) { throw "node not found" }
    # バージョン番号を取得して 18 以上か確認
    $major = [int]($nodeVersion -replace 'v(\d+)\..*','$1')
    if ($major -lt 18) {
        Write-Fail "Node.js $nodeVersion が見つかりましたが、バージョン 18 以上が必要です。"
        Write-Info "https://nodejs.org/ から最新版をインストールしてください。"
        exit 1
    }
    Write-Ok "Node.js $nodeVersion が見つかりました"
} catch {
    Write-Fail 'Node.js が見つかりません。'
    Write-Info '以下の URL から Node.js 18 以上をインストールしてください:'
    Write-Info '  https://nodejs.org/'
    exit 1
}

# ---- Step 2: ライブチケット管理セットアップ ----
Write-Step 2 $TOTAL 'ライブチケット管理のセットアップ'
Write-Info "setup.js を実行します..."
try {
    Push-Location $ScriptDir
    & node setup.js
    if ($LASTEXITCODE -ne 0) { throw "setup.js が失敗しました (exit code $LASTEXITCODE)" }
    Write-Ok 'ライブチケット管理のセットアップ完了'
} catch {
    Write-Fail "ライブチケット管理のセットアップに失敗しました: $_"
    exit 1
} finally {
    Pop-Location
}

# ---- Step 3: カード管理セットアップ ----
Write-Step 3 $TOTAL 'カード管理のセットアップ'
$CardDir = Join-Path $ScriptDir 'card-manager'
if (-not (Test-Path $CardDir)) {
    Write-Fail "card-manager ディレクトリが見つかりません: $CardDir"
    exit 1
}
Write-Info "card-manager/setup.js を実行します..."
try {
    Push-Location $CardDir
    & node setup.js
    if ($LASTEXITCODE -ne 0) { throw "card-manager/setup.js が失敗しました (exit code $LASTEXITCODE)" }
    Write-Ok 'カード管理のセットアップ完了'
} catch {
    Write-Fail "カード管理のセットアップに失敗しました: $_"
    exit 1
} finally {
    Pop-Location
}

# ---- 完了 ----
Write-Host ''
Write-Host '================================================' -ForegroundColor Green
Write-Host '  全セットアップ完了！' -ForegroundColor Green
Write-Host '================================================' -ForegroundColor Green
Write-Host ''
Write-Host '次のステップ:'
Write-Host '  1. index.html をブラウザで開く（ライブチケット管理）'
Write-Host '  2. card-manager/index.html をブラウザで開く（カード管理）'
Write-Host '  3. 初回アクセス時に Google のスコープ許可が求められます'
Write-Host '     「許可」をクリックしてください'
Write-Host ''
