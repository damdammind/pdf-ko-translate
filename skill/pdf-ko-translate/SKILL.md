---
name: pdf-ko-translate
description: 영어 PDF를 원본 레이아웃·줄바꿈을 유지한 채 Claude가 직접 한국어로 번역 (외부 번역 서비스·API 키 불필요, pdf2zh 레이아웃 + 캐시 주입 방식). "PDF 번역", "영한 번역", "pdf2zh로 번역", 영어 PDF를 한국어로 바꿔 달라는 요청에 사용.
---

# PDF 영→한 번역 (pdf2zh 레이아웃 + Claude 번역)

pdf2zh는 레이아웃 배치만 맡고, 번역문은 처음부터 Claude가 직접 쓴다. 외부 번역 서비스(Bing, Google 등)는
전혀 쓰지 않는다. pdf2zh는 `$K/pdf2zh_claude.py`로만 실행하는데, 이 래퍼는 번역 엔진을 "원문을 그대로
돌려주는" 가짜 엔진(`claude`)으로 바꿔서 pdf2zh가 PDF를 조각으로 나누고 캐시
(`~/.cache/pdf2zh/cache.v1.db`, translate_engine='claude')에 자리를 만들게 한다. 그 자리에 Claude 번역을
넣고 다시 실행하면 원본 레이아웃에 Claude 번역이 들어간다. 문서 텍스트는 Claude 말고 어디에도 보내지 않는다.

스크립트: 이 SKILL.md가 있는 폴더의 `scripts/` (보통 `~/.claude/skills/pdf-ko-translate/scripts/`, 이하 `$K`)
실행: `uv run --no-project [--with pymupdf] python -I $K/<script>.py ...`

## 0. 환경 자동 준비 (매번 가장 먼저)
1. `uv`가 있는지 확인(`uv --version`). 없으면 사용자에게 "uv(파이썬 도구 관리자)를 설치합니다"라고 한 줄 알리고 설치:
   - Windows: `powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - 설치 후 현재 셸에서 안 잡히면 `~/.local/bin`을 PATH 앞에 붙여 실행.
2. `uv run --no-project python -I $K/ensure_env.py` 실행. 하는 일:
   - pdf2zh 1.9.11이 없거나 버전이 다르면 `$K/requirements-lock.txt`로 의존성 버전을 고정해 설치(처음 한 번, 수 분 걸림. 사용자에게 미리 알림)
   - 패치(`$K/apply_patch.py`)가 없거나 예전 버전이면 빠진 부분만 적용 → 번역문의 `\n`이 강제 줄바꿈이 되고, 행간이 원문과 같아진다
   - "준비 완료"가 나오면 다음 단계로. (pdf2zh가 PATH에 없어도 된다. `pdf2zh_claude.py`가 설치 위치를 찾아 실행한다.)
   - 실패하면 출력 메시지를 사용자에게 그대로 보여 주고 멈춘다.

## 0-1. 실행 시 주의
- `pdf2zh`를 직접 부르지 말고 항상 `uv run --no-project python -I $K/pdf2zh_claude.py ...`로 실행한다
  (`-s` 옵션은 주지 않는다). 직접 `pdf2zh -s bing` 등을 부르면 문서가 외부 번역 서비스로 나간다.
  출력 폴더는 미리 만들어 둔다(없으면 저장 단계에서 죽음).
- pdf2zh는 **작업 폴더 안에서** 실행한다(scratchpad 경로는 이 환경에서 실패함). 한글 파일명은 영문 이름으로 복사해서 쓴다.

## 1. 원문 조각 뽑기
```bash
cp "<원본>.pdf" src.pdf; mkdir -p out
MARK=$(uv run --no-project python -I -c "import sqlite3,os;print(sqlite3.connect(os.path.expanduser('~/.cache/pdf2zh/cache.v1.db')).execute('select coalesce(max(id),0) from _translationcache').fetchone()[0])")
timeout 600 uv run --no-project python -I $K/pdf2zh_claude.py src.pdf -lo ko -o out --ignore-cache   # 네트워크 없음, 수십 초
uv run --no-project --with pymupdf python -I $K/export_segments.py src.pdf $MARK segments.json
```
`--ignore-cache`로 돌리면 이번 문서의 조각이 모두 `MARK`보다 큰 id로 새로 저장된다.

## 2. 번역 (`ko.json` = `{"<id>": "번역문"}`)
segments.json의 `src`(원문)와 `lines`(원본 강제 줄바꿈 위치를 `\n`으로 표시)를 보고 문맥 단위로 번역한다.
- **줄바꿈**: `hard_breaks`가 있는 조각(목록, 명령어 줄 등)은 번역문에도 같은 자리에 `\n`을 넣는다.
  긴 URL이 단어 중간에서 잘리면 URL 앞에 `\n`을 넣어도 된다.
- **자리표시자** `{v0}`, `{v1}` …(화살표·수식 등)은 개수와 번호를 그대로 유지.
- **잘린 조각**("white-c" / "ollar jobs ")은 앞 조각에 문장 전체를 넣고 나머지 조각은 `" "`(공백 하나).
  조각이 시각적으로 어떤 순서인지 헷갈리면 렌더링해서 확인.
- **한 줄짜리 원문**은 pdf2zh가 줄을 바꾸지 않으므로, 원문 폭을 넘지 않게 간결하게 쓴다(넘치면 오른쪽 밖으로 삐져나감).
- 아이콘과 겹치는 UI·댓글 영역, 이미 한국어인 UI 텍스트는 `null`(원문 유지).
- URL, 명령어(`npx ...`), 코드는 원문 그대로. 사용자가 붙여넣을 프롬프트 예시는 한국어로 옮겨도 된다.
- 신조어는 처음 나올 때 원어 병기: "슬롭 수류탄(slop grenade)".

## 3. 반영 → 재생성 → 확인
```bash
uv run --no-project python -I $K/apply_translations.py segments.json ko.json
uv run --no-project python -I $K/pdf2zh_claude.py src.pdf -lo ko -o out   # 캐시의 Claude 번역으로 생성
uv run --no-project --with pymupdf python -I $K/render_pages.py out/src-mono.pdf out/png all
```
PNG를 **모든 페이지** 열어 확인: 빈칸(조각 순서), 오른쪽 넘침, 겹침, 미번역. 고칠 것만 담은
작은 json을 만들어 apply → 재생성을 반복한다.

## 4. 마무리
- 결과: `<이름>_한국어.pdf`(mono), `<이름>_영한대역.pdf`(dual)로 작업 폴더에 저장.
- 임시 파일(src.pdf, segments.json, ko*.json, out/) 정리. 캐시는 그대로 둬도 된다.
- 알려진 한계: 원본의 링크 밑줄(파란 선)은 원래 위치에 남는다. 이미지 안의 글자는 번역되지 않는다.

## 패치 내용 (pdf2zh 1.9.11 converter.py, 레이아웃 루프)
`$K/apply_patch.py`가 자동으로 넣는다(`--check` 확인, `--revert` 되돌리기).
1. `ptr = 0` 다음 줄에 `nbrk = 0` 추가.
2. `ch = new[ptr]` 바로 다음: `ch == "\n"`이면 `cstk`가 있을 때 TEXT op로 flush하고 `cstk=""`,
   `x = x0; lidx += 1; nbrk += 1; ptr += 1; continue`.
3. `line_height = default_line_height` 다음:
   `if nbrk and lidx: line_height = max(default_line_height, min((height - size) / (lidx * size), 2.5))`
   (강제 줄바꿈이 있으면 원래 문단 높이에 맞게 행간을 벌림).
4. (행간) 줄바꿈 감지 지점(`pstk[-1].brk = True`)에서 원문 줄 간격 `xt.y0 - child.y0`을 문단의 `pitch`로 기록(최솟값).
5. 넘침 축소 루프 직전: 번역문이 2줄 이상이고 `pitch`가 있으면 `line_height = max(line_height, min(pitch / size, 2.5))`,
   넘침 판단은 `(lidx * line_height + 1) * size - 0.5 > height`(마지막 줄은 글자 높이만). 기본 한국어 행간 1.2가 원문보다 빽빽해지는 문제 해결.
