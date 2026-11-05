"""외부 번역 서비스 없이 pdf2zh를 실행한다 (번역은 Claude가 캐시에 넣는다).

usage: uv run --no-project python -I pdf2zh_claude.py <pdf2zh 인자...>
  예) pdf2zh_claude.py src.pdf -lo ko -o out --ignore-cache   # 1단계: 조각 나누기
      pdf2zh_claude.py src.pdf -lo ko -o out                  # 3단계: Claude 번역으로 PDF 생성

- pdf2zh의 번역 엔진 하나(Bing 클래스)를 빌려 이름을 "claude"로 바꾸고, 번역 함수를
  "원문을 그대로 돌려주기"로 바꾼다. 그래서 어떤 번역 서비스에도 접속하지 않고,
  문서 텍스트가 밖으로 나가지 않는다.
- 캐시에는 translate_engine='claude'로 저장되어 실제 Bing 캐시와 섞이지 않는다.
- 캐시에 Claude 번역이 있으면 그것을 쓰고, 없는 조각은 원문 그대로 들어간다.
- `-s` 옵션은 주지 않는다(자동으로 claude).

pdf2zh가 설치된 uv tool 환경의 파이썬으로 스스로를 다시 실행한다.
"""
import glob
import os
import subprocess
import sys

ENGINE = "claude"


def tool_python():
    sys.dont_write_bytecode = True
    import importlib.util

    here = os.path.dirname(os.path.abspath(__file__))
    spec = importlib.util.spec_from_file_location("apply_patch", os.path.join(here, "apply_patch.py"))
    ap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ap)
    conv = ap.find_converter()
    if not conv:
        sys.exit("pdf2zh를 찾지 못했습니다. 먼저 ensure_env.py를 실행하세요.")
    site = os.path.dirname(os.path.dirname(conv))
    root = site
    while root and not os.path.exists(os.path.join(root, "pyvenv.cfg")):
        parent = os.path.dirname(root)
        if parent == root:
            break
        root = parent
    for cand in ("Scripts/python.exe", "bin/python", "bin/python3"):
        p = os.path.join(root, cand)
        if os.path.exists(p):
            return p
    hits = glob.glob(os.path.join(root, "**", "python*"), recursive=True)
    if hits:
        return hits[0]
    sys.exit(f"pdf2zh 환경의 파이썬을 찾지 못했습니다: {root}")


def run_inside():
    from pdf2zh import translator as T

    T.BingTranslator.name = ENGINE
    T.BingTranslator.do_translate = lambda self, text: text
    T.BingTranslator.find_sid = lambda self: (_ for _ in ()).throw(RuntimeError("network disabled"))

    from pdf2zh.pdf2zh import main

    args = [a for a in sys.argv[1:]]
    if "-s" in args or "--service" in args:
        sys.exit("-s/--service 는 지정하지 마세요 (항상 claude 엔진을 씁니다).")
    sys.exit(main(args + ["-s", ENGINE]))


if __name__ == "__main__":
    try:
        import pdf2zh  # noqa: F401  (pdf2zh 환경 안에서 실행 중)
    except ImportError:
        py = tool_python()
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        sys.exit(subprocess.call([py, "-I", os.path.abspath(__file__)] + sys.argv[1:], env=env))
    run_inside()
