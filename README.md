# pdf-ko-translate

영어 PDF를 **원본 레이아웃과 줄바꿈을 그대로 둔 채**, 기계 번역이 아닌 **Claude 품질의 한국어**로 번역하는 Claude Code 스킬입니다. 번역 API 키가 필요 없습니다.

- 레이아웃 배치: [pdf2zh (PDFMathTranslate)](https://github.com/Byaidu/PDFMathTranslate) 1.9.11
- 번역: Claude Code가 문맥을 보며 직접 번역
- 결과: `*_한국어.pdf`(한국어만), `*_영한대역.pdf`(원문/번역 나란히)

## 동작 방식

1. pdf2zh를 Bing 번역으로 한 번 실행해 PDF를 문단 조각으로 나누고, 조각들을 pdf2zh 번역 캐시(`~/.cache/pdf2zh/cache.v1.db`)에 저장합니다.
2. `export_segments.py`가 그 조각들을 꺼내고, 원본 PDF에서 **강제 줄바꿈 위치**(목록 항목, 명령어 줄 등)를 찾아 표시합니다.
3. Claude가 조각을 번역하고, 원본의 강제 줄바꿈 자리에 `\n`을 넣습니다.
4. `apply_translations.py`가 캐시의 Bing 번역을 Claude 번역으로 바꿉니다.
5. pdf2zh를 다시 실행하면 캐시에 있는 번역을 그대로 쓰므로, 원본 레이아웃에 Claude 번역이 들어갑니다.
6. `render_pages.py`로 모든 페이지를 이미지로 확인하고, 문제가 있는 조각만 고쳐 다시 만듭니다.

pdf2zh 원본은 번역문의 줄바꿈을 무시합니다. 그래서 `apply_patch.py`로 `
`이 있으면 그 자리에서 줄을 바꾸고, 원래 문단 높이에 맞게 줄 간격을 벌리도록 고칩니다([patch/converter.diff](patch/converter.diff) 참고).

## 설치

필요한 것: [Claude Code](https://claude.com/claude-code)(데스크톱 앱 Code 탭 또는 CLI)와 인터넷 연결뿐입니다. GitHub CLI는 필요 없습니다.

**가장 쉬운 방법: Claude Code에 부탁하기**

> https://github.com/damdammind/pdf-ko-translate 를 받아서 skill/pdf-ko-translate 폴더를 내 Claude Code 스킬 폴더(~/.claude/skills)에 설치해줘

비공개 저장소라면 처음 받을 때 Git 로그인 창(브라우저)이 한 번 뜹니다.

**직접 하려면**

```bash
git clone https://github.com/damdammind/pdf-ko-translate.git
```

```powershell
# Windows
powershell -ExecutionPolicy Bypass -File pdf-ko-translate/setup.ps1
```

```bash
# macOS / Linux
bash pdf-ko-translate/setup.sh
```

설치는 스킬 폴더를 `~/.claude/skills/pdf-ko-translate`에 복사하는 것이 전부입니다.

**나머지는 자동입니다.** 처음 번역을 요청하면 스킬이 `ensure_env.py`로 환경을 확인하고, 없는 것만 설치합니다.
1. `uv`(파이썬 도구 관리자)가 없으면 설치
2. `pdf2zh==1.9.11`을 Python 3.12로, `requirements-lock.txt`의 의존성 버전 그대로 설치(처음 한 번, 몇 분)
3. 줄바꿈 패치 적용(`converter.py.orig`로 원본 백업)

미리 해 두려면 `setup.ps1 -Prepare` 또는 `setup.sh --prepare`로 실행합니다.

## 사용

Claude Code에서 PDF가 있는 폴더를 열고 이렇게 요청합니다.

> 이 PDF를 영한 번역해줘: `문서.pdf`

Claude가 환경 확인 → 1페이지 테스트 → 조각 추출 → 번역 → 반영 → 전체 페이지 확인까지 진행합니다.

## 패치 관리

`S=~/.claude/skills/pdf-ko-translate/scripts` 라고 할 때:

```bash
uv run --no-project python -I $S/ensure_env.py --check   # 준비 상태 확인만
uv run --no-project python -I $S/apply_patch.py --check  # 패치 여부 확인
uv run --no-project python -I $S/apply_patch.py --revert # 원본으로 되돌리기
```

pdf2zh를 다시 설치하거나 업데이트하면 패치가 사라지지만, 다음 번역 때 스킬이 다시 넣습니다. 이 패치는 1.9.11 전용이라 다른 버전이면 1.9.11을 다시 설치합니다.

## 알려진 한계

- 원본 링크의 밑줄(파란 선)은 원래 위치에 그대로 남습니다.
- 이미지 안에 있는 글자는 번역되지 않습니다.
- 원본에서 한 줄짜리 문단은 pdf2zh가 줄을 바꾸지 않으므로, 번역문을 원문 폭에 맞게 간결하게 써야 합니다.
- pdf2zh 1단계에서 Bing 번역 서비스에 접속합니다. Bing이 막힌 네트워크에서는 `-s` 옵션으로 다른 서비스를 지정해야 합니다.

## 라이선스

pdf2zh(AGPL-3.0)를 수정하는 패치를 포함하므로 이 프로젝트도 [AGPL-3.0](LICENSE)을 따릅니다. pdf2zh 소스 코드 자체는 포함하지 않으며, 설치할 때 PyPI에서 받습니다.
