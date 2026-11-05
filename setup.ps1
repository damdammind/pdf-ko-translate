# pdf-ko-translate 스킬 설치 (Windows PowerShell)
#   powershell -ExecutionPolicy Bypass -File setup.ps1
# 스킬 폴더를 ~/.claude/skills 에 복사한다. pdf2zh 설치와 패치는 처음 번역할 때
# 스킬이 자동으로 한다. 미리 해 두려면 -Prepare 를 붙인다.
param([switch]$Prepare)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path

$Dest = Join-Path $env:USERPROFILE ".claude\skills\pdf-ko-translate"
Write-Host "Claude Code 스킬 복사: $Dest"
New-Item -ItemType Directory -Force (Split-Path $Dest) | Out-Null
if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force }
Copy-Item "$Root\skill\pdf-ko-translate" $Dest -Recurse

if ($Prepare) {
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
        $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    }
    uv run --no-project python -I "$Dest\scripts\ensure_env.py"
}

Write-Host "완료. Claude Code에서 '이 PDF 영한 번역해줘'라고 요청하세요."
