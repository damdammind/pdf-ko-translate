# pdf-ko-translate

영어 PDF를 **원본 레이아웃과 줄바꿈을 그대로 둔 채**, 기계 번역이 아닌 **Claude가 직접 쓴 한국어**로 번역하는 Claude Code 스킬입니다. 외부 번역 서비스나 API 키가 필요 없습니다.

- 레이아웃 배치: [pdf2zh (PDFMathTranslate)](https://github.com/Byaidu/PDFMathTranslate) 1.9.11
- 번역: Claude Code가 문맥을 보며 직접 번역
- 결과: `*_한국어.pdf`(한국어만), `*_영한대역.pdf`(원문/번역 나란히)

## 동작 방식

번역은 처음부터 끝까지 Claude가 합니다. Bing·Google 같은 외부 번역 서비스는 쓰지 않고, 문서 텍스트도 Claude 말고는 어디에도 보내지 않습니다. pdf2zh는 PDF를 나누고 다시 조립하는 레이아웃 도구로만 씁니다.

1. `pdf2zh_claude.py`가 pdf2zh를 실행합니다. 이때 번역 엔진을 "원문을 그대로 돌려주는" 가짜 엔진(`claude`)으로 바꿔 두어서, pdf2zh는 외부에 접속하지 않고 PDF를 문단 조각으로 나눠 번역 캐시(`~/.cache/pdf2zh/cache.v1.db`)에 자리만 만듭니다.
2. `export_segments.py`가 그 조각들을 꺼내고, 원본 PDF에서 강제 줄바꿈 위치(목록 항목, 명령어 줄 등)를 찾아 표시합니다.
3. Claude가 모든 조각을 문맥을 보며 번역하고, 원본의 강제 줄바꿈 자리에 `
`을 넣습니다.
4. `apply_translations.py`가 Claude 번역을 캐시의 자리에 넣습니다.
5. `pdf2zh_claude.py`를 다시 실행하면 pdf2zh가 캐시의 Claude 번역을 원본 레이아웃에 배치합니다.
6. `render_pages.py`로 모든 페이지를 이미지로 확인하고, 줄 넘침·빈칸 같은 배치 문제가 있는 조각만 고쳐 다시 만듭니다.

pdf2zh 원본은 번역문의 줄바꿈을 무시합니다. 그래서 `apply_patch.py`로 `
`이 있으면 그 자리에서 줄을 바꾸고, 원래 문단 높이에 맞게 줄 간격을 벌리도록 고칩니다([patch/converter.diff](patch/converter.diff) 참고).
또 pdf2zh는 한국어 행간을 글자 크기의 1.2배로 고정해 원문보다 줄이 빽빽해지므로, 원문 문단의 실제 줄 간격을 재서 번역문에도 같은 간격을 씁니다(번역문이 원문보다 길어 넘치면 그때만 줄임). 예전 패치가 깔린 PC는 다음 사용 때 `ensure_env.py`가 빠진 부분만 자동으로 추가합니다.

## 설치

필요한 것: [Claude Code](https://claude.com/claude-code)(데스크톱 앱 Code 탭 또는 CLI)와 인터넷 연결뿐입니다. GitHub CLI는 필요 없습니다.

**가장 쉬운 방법: Claude Code에 부탁하기**

> https://github.com/damdammind/pdf-ko-translate 를 받아서 skill/pdf-ko-translate 폴더를 내 Claude Code 스킬 폴더(~/.claude/skills)에 설치해줘

공개 저장소라 GitHub 로그인도 필요 없습니다.

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

## 라이선스

pdf2zh(AGPL-3.0)를 수정하는 패치를 포함하므로 이 프로젝트도 [AGPL-3.0](LICENSE)을 따릅니다. pdf2zh 소스 코드 자체는 포함하지 않으며, 설치할 때 PyPI에서 받습니다.
