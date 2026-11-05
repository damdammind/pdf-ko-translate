---
name: pdf-ko-translate
description: 영어 PDF를 원본 레이아웃·줄바꿈을 유지한 채 Claude 품질로 한국어 번역 (API 키 불필요, pdf2zh 캐시 주입 방식). "PDF 번역", "영한 번역", "pdf2zh로 번역", 영어 PDF를 한국어로 바꿔 달라는 요청에 사용.
---

# PDF 영→한 번역 (pdf2zh 레이아웃 + Claude 번역)

pdf2zh는 레이아웃 배치만 맡고, 번역문은 Claude가 직접 쓴다. pdf2zh는 번역 결과를
`~/.cache/pdf2zh/cache.v1.db`(`_translationcache`)에 저장해 두고 재사용하므로, 그 캐시에
Claude 번역을 넣고 다시 실행하면 원본 레이아웃에 Claude 번역이 들어간다.

스크립트: `~/.claude/skills/pdf-ko-translate/scripts/` (이하 `$K`)
실행: `uv run --no-project [--with pymupdf] python -I $K/<script>.py ...`

## 0. 사전 확인
- 설치 확인: `pdf2zh --version`이 1.9.11이어야 하고, 줄바꿈 패치가 들어 있어야 번역문의 `\n`이
  줄바꿈으로 처리된다. 확인: `uv run --no-project python -I $K/apply_patch.py --check`
  (패치 안 됨이면 사용자에게 알리고 `apply_patch.py`를 실행. pdf2zh가 없으면 이 프로젝트의 setup 스크립트를 안내)
- 번역 서비스는 `-s bing`을 쓴다(Google은 막히는 네트워크가 많음). Bing 결과는 버려지고 Claude 번역으로 바뀐다.
  출력 폴더는 미리 만들어 둔다(없으면 저장 단계에서 죽음).
- pdf2zh는 **작업 폴더 안에서** 실행한다(scratchpad 경로는 이 환경에서 실패함). 한글 파일명은 영문 이름으로 복사해서 쓴다.

## 1. 원문 조각 뽑기
```bash
cp "<원본>.pdf" src.pdf; mkdir -p out
MARK=$(uv run --no-project python -I -c "import sqlite3,os;print(sqlite3.connect(os.path.expanduser('~/.cache/pdf2zh/cache.v1.db')).execute('select coalesce(max(id),0) from _translationcache').fetchone()[0])")
timeout 600 pdf2zh src.pdf -s bing -lo ko -o out --ignore-cache   # 먼저 -p 1 로 1페이지 스모크 테스트
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
pdf2zh src.pdf -s bing -lo ko -o out          # 캐시를 쓰므로 수 초
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
