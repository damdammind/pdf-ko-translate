#!/usr/bin/env bash
# pdf-ko-translate 스킬 설치 (macOS / Linux / Git Bash)
#   bash setup.sh            # 스킬만 복사 (pdf2zh는 처음 번역할 때 자동 설치)
#   bash setup.sh --prepare  # pdf2zh 설치와 패치까지 미리
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

DEST="$HOME/.claude/skills/pdf-ko-translate"
echo "Claude Code 스킬 복사: $DEST"
mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
cp -R "$ROOT/skill/pdf-ko-translate" "$DEST"

if [ "${1:-}" = "--prepare" ]; then
  if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi
  uv run --no-project python -I "$DEST/scripts/ensure_env.py"
fi

echo "완료. Claude Code에서 '이 PDF 영한 번역해줘'라고 요청하세요."
