#!/usr/bin/env bash
# pdf-ko-translate 설치 (macOS / Linux / Git Bash)
#   bash setup.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv 설치 중..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "pdf2zh 1.9.11 설치 중 (의존성 버전 고정)..."
# requirements-lock.txt 는 Windows에서 만든 목록이라, 다른 OS에서 맞지 않는 항목은 uv가 무시한다.
uv tool install "pdf2zh==1.9.11" --python 3.12 -c "$ROOT/requirements-lock.txt" --force

echo "줄바꿈 패치 적용..."
uv run --no-project python -I "$ROOT/patch/apply_patch.py"

DEST="$HOME/.claude/skills/pdf-ko-translate"
echo "Claude Code 스킬 복사: $DEST"
mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
cp -R "$ROOT/skill/pdf-ko-translate" "$DEST"

echo
echo "완료. Claude Code에서 '이 PDF 영한 번역해줘'라고 요청하면 pdf-ko-translate 스킬이 쓰입니다."
