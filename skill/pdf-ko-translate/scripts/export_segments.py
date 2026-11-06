"""pdf2zh 캐시에서 이번 PDF의 원문 조각을 꺼내고, 원본 PDF의 줄바꿈 정보를 붙인다.

usage: export_segments.py <원본.pdf> <marker_id> <out.json> [옵션]
  marker_id: pdf2zh(--ignore-cache) 실행 직전의 캐시 max(id). 그보다 큰 id가 이번 문서 조각.
  --glossary/-g <csv>      용어집 추가 (여러 번 가능, 먼저 준 것이 우선)
  --no-default-glossary    스킬 기본 용어집(glossary/*.csv) 끄기
  --translate-references   참고문헌도 번역 (기본: 원문 유지)

out.json: [{"id", "src", "lines", "hard_breaks", "terms"?, "keep"?}]
  lines: 원문을 원본의 '강제 줄바꿈' 위치에서 \n 으로 나눈 것 (목록 항목, 짧게 끝난 줄)
         번역문에도 같은 위치에 \n 을 넣으면 pdf2zh(패치판)가 그 자리에서 줄을 바꾼다.
  terms: 이 조각에 나온 용어집 용어 {"원어": "번역어"} — 번역할 때 이 번역어를 쓴다.
  keep:  "references" = 참고문헌 조각. 번역하지 않으면 apply 단계에서 자동으로 원문 유지.
         (보통은 pdf2zh_claude.py가 참고문헌 영역을 아예 손대지 않아 조각이 생기지 않는다. 이건 안전망.)
out.todo.json: keep 조각을 뺀 번역 작업 목록 (Claude는 이것만 읽으면 된다).
"""
import json
import os
import re
import sqlite3
import sys

import pymupdf

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glossary  # noqa: E402
from refs import reference_range, visual_lines  # noqa: E402

DB = os.path.expanduser("~/.cache/pdf2zh/cache.v1.db")
LIST_RE = re.compile(r"^(\d+[.):]|[•\-–→▪◦·*])\s*")


PH_RE = re.compile(r"\{v\d+\}")


def nows(s):
    """글자·숫자만 남긴 비교용 문자열과 원래 위치 (공백, 기호, {vN} 자리표시자 무시)."""
    skip = set()
    for m in PH_RE.finditer(s):
        skip.update(range(m.start(), m.end()))
    idx, chars = [], []
    for i, ch in enumerate(s):
        if i not in skip and ch.isalnum():
            chars.append(ch)
            idx.append(i)
    return "".join(chars), idx


def first_word_width(text, size):
    w = text.strip().split(" ")[0] if text.strip() else ""
    return (len(w) * 0.55 + 0.3) * size  # 대략적인 라틴 글자 폭 + 공백


def annotate(src, L):
    sN, sIdx = nows(src)
    if len(sN) < 6:
        return src, 0
    for j, line in enumerate(L):
        tN, _ = nows(line["t"])
        if len(tN) < 2 or not sN.startswith(tN):
            continue
        run = [(0, line)]
        cur = len(tN)
        k = j + 1
        while cur < len(sN) and k < len(L):
            tN2, _ = nows(L[k]["t"])
            if tN2 and sN.startswith(tN2, cur):
                run.append((cur, L[k]))
                cur += len(tN2)
                k += 1
            else:
                break
        if cur < len(sN) * 0.9 or len(run) < 2:
            continue
        x1max = max(r[1]["bbox"][2] for r in run)
        cuts = []
        for (_, a), (pos, b) in zip(run, run[1:]):
            # 다음 줄 첫 단어가 앞줄 남은 공간에 들어갔을 텐데 줄이 바뀌었다 = 강제 줄바꿈
            fits = x1max - a["bbox"][2] > first_word_width(b["t"], a["size"])
            if fits or LIST_RE.match(b["t"].strip()):
                c, lo = sIdx[pos], sIdx[pos - 1] + 1
                while c > lo and not src[c - 1].isspace():  # 줄 첫머리의 기호·{vN}까지 포함
                    c -= 1
                cuts.append(c)
        if not cuts:
            return src, 0
        out, last = [], 0
        for c in cuts:
            out.append(src[last:c].rstrip())
            last = c
        out.append(src[last:])
        return "\n".join(out), len(cuts)
    return src, 0


def locate(src, L):
    """조각이 시작하는 '눈에 보이는 줄'의 번호 (못 찾으면 None)."""
    sN, _ = nows(src)
    if len(sN) < 3:
        return None
    for j, line in enumerate(L):
        tN, _ = nows(line["t"])
        if len(tN) < 3:
            continue
        if sN.startswith(tN) or (len(sN) >= 6 and tN.startswith(sN)):
            return j
    return None


def parse_args(argv):
    pos, opt = [], {"glossary": [], "default_glossary": True, "references": False}
    it = iter(argv)
    for a in it:
        if a in ("--glossary", "-g"):
            opt["glossary"].append(next(it))
        elif a == "--no-default-glossary":
            opt["default_glossary"] = False
        elif a == "--translate-references":
            opt["references"] = True
        else:
            pos.append(a)
    if len(pos) != 3:
        sys.exit(__doc__)
    return pos, opt


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    (pdf, marker, outp), opt = parse_args(sys.argv[1:])
    marker = int(marker)
    con = sqlite3.connect(DB)
    rows = con.execute(
        "select id, original_text from _translationcache "
        "where translate_engine='claude' and id>? order by id",
        (marker,),
    ).fetchall()
    L = visual_lines(pymupdf.open(pdf))

    rr = None if opt["references"] else reference_range(L)
    terms = glossary.load(opt["glossary"], opt["default_glossary"])
    compiled = glossary.compile_terms(terms)

    res, prev_ref, used = [], False, {}
    for i, src in rows:
        lines, n = annotate(src, L)
        r = {"id": i, "src": src, "lines": lines, "hard_breaks": n}
        if rr:
            j = locate(src, L)
            is_ref = (rr[0] < j < rr[1]) if j is not None else prev_ref
            prev_ref = is_ref
            if is_ref:
                r["keep"] = "references"
        if "keep" not in r:
            t = glossary.find(src, compiled)
            if t:
                r["terms"] = t
                used.update(t)
        res.append(r)

    with open(outp, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    # Claude가 번역할 것만 담은 작업 목록 (참고문헌 등 원문 유지 조각은 뺌 -> 토큰 절약)
    todo = os.path.splitext(outp)[0] + ".todo.json"
    with open(todo, "w", encoding="utf-8") as f:
        json.dump([r for r in res if "keep" not in r], f, ensure_ascii=False, indent=1)

    nref = sum(1 for r in res if r.get("keep") == "references")
    print(f"{len(res)} segments, {sum(1 for r in res if r['hard_breaks'])} with hard line breaks -> {outp}")
    if rr:
        print(f"참고문헌: '{L[rr[0]]['t'].strip()}' (p.{L[rr[0]]['page'] + 1}) 이후는 원문 유지"
              + (f" (남은 조각 {nref}개도 원문 유지)" if nref else ""))
    else:
        print("참고문헌: " + ("번역함(--translate-references)" if opt["references"] else "찾지 못함"))
    print(f"용어집: {len(terms)}개 용어 중 이 문서에 {len(used)}개 등장")
    print(f"번역할 조각 {len(res) - nref}개 -> {todo}")


if __name__ == "__main__":
    main()
