# pdf-ko-translate 설치 (Windows PowerShell)
#   powershell -ExecutionPolicy Bypass -File setup.ps1
# 1) uv 확인/설치  2) pdf2zh 1.9.11을 고정된 의존성으로 설치  3) 줄바꿈 패치  4) Claude Code 스킬 복사
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv 설치 중..."
    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

Write-Host "pdf2zh 1.9.11 설치 중 (의존성 버전 고정)..."
uv tool install "pdf2zh==1.9.11" --python 3.12 -c "$Root\requirements-lock.txt" --force
if ($LASTEXITCODE -ne 0) { throw "pdf2zh 설치 실패" }

Write-Host "줄바꿈 패치 적용..."
uv run --no-project python -I "$Root\patch\apply_patch.py"
if ($LASTEXITCODE -ne 0) { throw "패치 실패" }

$Dest = Join-Path $env:USERPROFILE ".claude\skills\pdf-ko-translate"
Write-Host "Claude Code 스킬 복사: $Dest"
New-Item -ItemType Directory -Force (Split-Path $Dest) | Out-Null
if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
Copy-Item "$Root\skill\pdf-ko-translate" $Dest -Recurse

Write-Host ""
Write-Host "완료. Claude Code에서 '이 PDF 영한 번역해줘'라고 요청하면 pdf-ko-translate 스킬이 쓰입니다."
