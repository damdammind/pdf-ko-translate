"""설치된 pdf2zh 1.9.11의 converter.py에 '번역문 \\n = 강제 줄바꿈' 패치를 넣는다.

usage:
  python apply_patch.py            # 자동으로 pdf2zh 설치 위치를 찾아 패치 (이미 돼 있으면 건너뜀)
  python apply_patch.py --check    # 패치 여부만 확인
  python apply_patch.py --revert   # converter.py.orig 로 되돌림
  python apply_patch.py --path <.../pdf2zh/converter.py>   # 위치 직접 지정

변경 내용은 patch/converter.diff 와 같다.
"""
import glob
import hashlib
import os
import shutil
import subprocess
import sys

MARK = "[patch] 译文强制换行"
ORIG_SHA256 = "32ebf01c1fd20016c198e1be9a1d4ee52f4f7a9e83a5899192aace88e9d39c60"  # pdf2zh 1.9.11 원본

EDITS = [
    (
        "            ptr = 0\n",
        "            ptr = 0\n"
        "            nbrk = 0  # [patch] 强制换行次数\n",
    ),
    (
        "                    ch = new[ptr]\n"
        "                    fcur_ = None\n",
        "                    ch = new[ptr]\n"
        "                    if ch == \"\\n\":  # [patch] 译文强制换行\n"
        "                        if cstk:\n"
        "                            ops_vals.append({\n"
        "                                \"type\": OpType.TEXT,\n"
        "                                \"font\": fcur,\n"
        "                                \"size\": size,\n"
        "                                \"x\": tx,\n"
        "                                \"dy\": 0,\n"
        "                                \"rtxt\": raw_string(fcur, cstk),\n"
        "                                \"lidx\": lidx\n"
        "                            })\n"
        "                            cstk = \"\"\n"
        "                        x = x0\n"
        "                        lidx += 1\n"
        "                        nbrk += 1\n"
        "                        ptr += 1\n"
        "                        continue\n"
        "                    fcur_ = None\n",
    ),
    (
        "            line_height = default_line_height\n",
        "            line_height = default_line_height\n"
        "            if nbrk and lidx:  # [patch] 强制换行时按原段落高度均匀分布行距\n"
        "                line_height = max(default_line_height, min((height - size) / (lidx * size), 2.5))\n",
    ),
    (  # v2: 원문 문단의 실제 줄 간격(pitch)을 기록
        "                            pstk[-1].brk = True\n",
        "                            pstk[-1].brk = True\n"
        "                            _pitch = xt.y0 - child.y0  # [patch] 原文行距\n"
        "                            if pstk[-1].size * 0.9 < _pitch < pstk[-1].size * 3:\n"
        "                                pstk[-1].pitch = min(getattr(pstk[-1], \"pitch\", _pitch), _pitch)\n",
    ),
    (  # v2: 번역문이 여러 줄이면 원문 줄 간격을 그대로 쓴다 (넘치면 아래 루프가 줄임)
        "            while (lidx + 1) * size * line_height > height and line_height >= 1:\n",
        "            _pitch = getattr(pstk[id], \"pitch\", 0)  # [patch] 按原文行距排版\n"
        "            if _pitch and lidx:\n"
        "                line_height = max(line_height, min(_pitch / size, 2.5))\n"
        "            else:\n"
        "                _pitch = 0\n"
        "            # 원문 행간을 쓸 때는 마지막 줄 높이(size)만 더해 넘침을 판단\n"
        "            while ((lidx * line_height + 1) * size - 0.5 if _pitch else (lidx + 1) * size * line_height) > height and line_height >= 1:\n",
    ),
]


def tool_dirs():
    if os.environ.get("UV_TOOL_DIR"):  # uv와 같이, 지정돼 있으면 그곳만 본다
        return [os.environ["UV_TOOL_DIR"]]
    dirs = []
    try:
        out = subprocess.run(["uv", "tool", "dir"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30).stdout.strip()
        if out:
            dirs.append(out)
    except Exception:
        pass
    home = os.path.expanduser("~")
    dirs += [
        os.path.join(home, ".uv", "tools"),
        os.path.join(home, ".local", "share", "uv", "tools"),
        os.path.join(os.environ.get("APPDATA", ""), "uv", "tools"),
    ]
    return dirs


def find_converter():
    for d in tool_dirs():
        for pat in ("Lib/site-packages/pdf2zh/converter.py", "lib/python3*/site-packages/pdf2zh/converter.py"):
            hits = glob.glob(os.path.join(d, "pdf2zh", pat))
            if hits:
                return hits[0]
    return None


def version_of(conv):
    sp = os.path.dirname(os.path.dirname(conv))
    for meta in glob.glob(os.path.join(sp, "pdf2zh-*.dist-info", "METADATA")):
        for line in open(meta, encoding="utf-8"):
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    return "?"


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def main():
    args = sys.argv[1:]
    conv = args[args.index("--path") + 1] if "--path" in args else find_converter()
    if not conv or not os.path.exists(conv):
        sys.exit("pdf2zh를 찾지 못했습니다. 먼저 setup 스크립트로 설치하거나 --path 로 converter.py 위치를 지정하세요.")
    ver = version_of(conv)
    src = open(conv, encoding="utf-8").read()
    todo = [(o, r) for o, r in EDITS if r not in src]  # 이전 버전 패치면 빠진 부분만
    patched = not todo
    print(f"pdf2zh {ver}: {conv}")

    if "--check" in args:
        print("패치됨" if patched else ("일부만 패치됨(업데이트 필요)" if MARK in src else "패치 안 됨"))
        sys.exit(0 if patched else 1)

    if "--revert" in args:
        if os.path.exists(conv + ".orig"):
            shutil.copyfile(conv + ".orig", conv)
            print("원본으로 되돌렸습니다.")
        else:
            print("converter.py.orig 가 없어 되돌릴 수 없습니다.")
        return

    if patched:
        print("이미 패치되어 있습니다.")
        return
    if ver != "1.9.11":
        sys.exit(f"이 패치는 pdf2zh 1.9.11 전용입니다 (설치된 버전: {ver}).")
    if MARK not in src and sha(conv) != ORIG_SHA256:
        print("[경고] converter.py가 1.9.11 원본과 다릅니다. 기준 문자열이 모두 있으면 계속 진행합니다.")

    new = src
    for old, rep in todo:
        if new.count(old) != 1:
            sys.exit(f"패치 기준 위치를 찾지 못했습니다(파일 변경 없음):\n{old}")
        new = new.replace(old, rep)
    if not os.path.exists(conv + ".orig"):
        shutil.copyfile(conv, conv + ".orig")
    # uv는 패키지 파일을 캐시와 하드링크로 공유하므로, 지우고 새로 써야 캐시 원본이 안 바뀐다
    os.remove(conv)
    with open(conv, "w", encoding="utf-8", newline="") as f:
        f.write(new)
    print("패치 완료. (원본: converter.py.orig)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
