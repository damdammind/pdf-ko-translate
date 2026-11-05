"""Claude가 쓴 번역을 pdf2zh 캐시에 넣는다.

usage: apply_translations.py <segments.json> <ko.json>
  ko.json: {"<id>": "번역문" | null}
    null  -> 원문 그대로 둔다 (UI 텍스트, 아이콘과 겹치는 영역 등)
    " "   -> 줄이 잘려 나뉜 조각: 앞 조각에 문장 전체를 넣고 나머지는 공백 하나
    "\n"  -> 원본의 강제 줄바꿈 자리 (segments.json의 hard_breaks 수와 맞추는 게 원칙)
"""
import json
import os
import re
import sqlite3
import sys

DB = os.path.expanduser("~/.cache/pdf2zh/cache.v1.db")
PH = re.compile(r"\{v\d+\}")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    segs = {str(s["id"]): s for s in json.load(open(sys.argv[1], encoding="utf-8"))}
    ko = json.load(open(sys.argv[2], encoding="utf-8"))
    missing = sorted(set(segs) - set(ko), key=int)
    extra = sorted(set(ko) - set(segs), key=int)
    if missing:
        print("번역 누락 id:", missing)
    if extra:
        print("segments에 없는 id (무시):", extra)
    con = sqlite3.connect(DB)
    n = 0
    for k, v in ko.items():
        if k not in segs:
            continue
        s = segs[k]
        if v is None:
            v = s["src"]
        if sorted(PH.findall(s["src"])) != sorted(PH.findall(v)):
            print(f"[경고] id {k}: 자리표시자 불일치 {PH.findall(s['src'])} -> {PH.findall(v)}")
        nb = v.count("\n")
        if nb != s.get("hard_breaks", 0):
            print(f"[참고] id {k}: 줄바꿈 {nb}개 (원본 강제 줄바꿈 {s.get('hard_breaks', 0)}개)")
        con.execute("update _translationcache set translation=? where id=?", (v, int(k)))
        n += 1
    con.commit()
    print(f"{n}개 번역을 캐시에 반영")


if __name__ == "__main__":
    main()
