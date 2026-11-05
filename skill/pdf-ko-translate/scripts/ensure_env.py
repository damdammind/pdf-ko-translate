"""번역에 필요한 환경을 확인하고, 없으면 자동으로 갖춘다.

usage: uv run --no-project python -I ensure_env.py [--check]

1) pdf2zh 1.9.11 이 uv tool 로 설치돼 있는지 확인 -> 없거나 버전이 다르면
   `uv tool install pdf2zh==1.9.11 --python 3.12 -c requirements-lock.txt --force`
2) 줄바꿈 패치 확인 -> 없으면 apply_patch.py 로 적용

--check: 확인만 하고 아무것도 설치하지 않음.
종료 코드 0 = 준비 완료, 1 = 준비 안 됨(--check) 또는 실패.
"""
import importlib.util
import os
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True  # 스킬 폴더에 __pycache__ 를 만들지 않음
HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = "1.9.11"


def load_patch_module():
    spec = importlib.util.spec_from_file_location("apply_patch", os.path.join(HERE, "apply_patch.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(cmd):
    print("$ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd).returncode


def main():
    check_only = "--check" in sys.argv
    ap = load_patch_module()

    conv = ap.find_converter()
    ver = ap.version_of(conv) if conv else None
    print(f"pdf2zh: {ver or '없음'}" + (f" ({conv})" if conv else ""))

    if ver != VERSION:
        if check_only:
            print(f"준비 안 됨: pdf2zh {VERSION} 설치 필요")
            sys.exit(1)
        if not shutil.which("uv"):
            sys.exit("uv 가 없습니다. 먼저 uv 를 설치하세요.")
        lock = os.path.join(HERE, "requirements-lock.txt")
        rc = run(["uv", "tool", "install", f"pdf2zh=={VERSION}", "--python", "3.12", "-c", lock, "--force"])
        if rc != 0:
            sys.exit("pdf2zh 설치 실패")
        conv = ap.find_converter()
        ver = ap.version_of(conv) if conv else None
        if ver != VERSION:
            sys.exit(f"설치 후에도 pdf2zh {VERSION} 을 찾지 못했습니다.")

    src = open(conv, encoding="utf-8").read()
    if ap.MARK not in src:
        if check_only:
            print("준비 안 됨: 줄바꿈 패치 필요")
            sys.exit(1)
        rc = run([sys.executable, "-I", os.path.join(HERE, "apply_patch.py"), "--path", conv])
        if rc != 0:
            sys.exit("패치 실패")
    print("줄바꿈 패치: 적용됨")

    print("준비 완료 (pdf2zh는 pdf2zh_claude.py로 실행)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
