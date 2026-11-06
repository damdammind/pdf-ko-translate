"""Claude가 쓴 번역을 pdf2zh 캐시에 넣는다.

usage: apply_translations.py <segments.json> <ko.json> [--partial]
  --partial: 고칠 조각만 담은 json이면 붙인다 (누락 경고, 원문 유지 조각 재기록 생략)
  segments.json에서 keep(참고문헌)인 조각이 ko.json에 없으면 원문 그대로 넣는다.
  terms(용어집) 번역어가 번역문에 없으면 [용어] 경고를 낸다.
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
    sys.dont_write_bytecode = True
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from glossary import target_ok

    segs = {str(s["id"]): s for s in json.load(open(sys.argv[1], encoding="utf-8"))}
    ko = json.load(open(sys.argv[2], encoding="utf-8"))
    partial = "--partial" in sys.argv  # 고칠 조각만 담은 작은 json
    keep = [k for k, s in segs.items() if s.get("keep") and k not in ko]
    missing = sorted(set(segs) - set(ko) - set(keep), key=int)
    extra = sorted(set(ko) - set(segs), key=int)
    if missing and not partial:
        print("번역 누락 id:", missing)
    if extra:
        print("segments에 없는 id (무시):", extra)
    con = sqlite3.connect(DB)
    n = 0
    items = list(ko.items()) + ([] if partial else [(k, None) for k in keep])
    term_miss = 0
    for k, v in items:
        if k not in segs:
            continue
        s = segs[k]
        if v is None:
            v = s["src"]
        else:
            for src_t, tgt_t in s.get("terms", {}).items():
                if not target_ok(tgt_t, v):
                    term_miss += 1
                    print(f"[용어] id {k}: '{src_t}' -> 용어집은 '{tgt_t}' (문맥상 다른 뜻이면 무시)")
        if sorted(PH.findall(s["src"])) != sorted(PH.findall(v)):
            print(f"[경고] id {k}: 자리표시자 불일치 {PH.findall(s['src'])} -> {PH.findall(v)}")
        nb = v.count("\n")
        if nb != s.get("hard_breaks", 0) and not s.get("keep"):
            print(f"[참고] id {k}: 줄바꿈 {nb}개 (원본 강제 줄바꿈 {s.get('hard_breaks', 0)}개)")
        con.execute("update _translationcache set translation=? where id=?", (v, int(k)))
        n += 1
    con.commit()
    print(f"{n}개 번역을 캐시에 반영" + (f" (참고문헌 등 원문 유지 {len(keep)}개 포함)" if keep and not partial else ""))
    if term_miss:
        print(f"용어집과 다른 번역 {term_miss}곳 — 위 [용어] 줄 확인")


if __name__ == "__main__":
    main()
