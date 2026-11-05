"""pdf2zh 캐시에서 이번 PDF의 원문 조각을 꺼내고, 원본 PDF의 줄바꿈 정보를 붙인다.

usage: export_segments.py <원본.pdf> <marker_id> <out.json>
  marker_id: pdf2zh(--ignore-cache) 실행 직전의 캐시 max(id). 그보다 큰 id가 이번 문서 조각.

out.json: [{"id", "src", "lines", "hard_breaks"}]
  lines: 원문을 원본의 '강제 줄바꿈' 위치에서 \n 으로 나눈 것 (목록 항목, 짧게 끝난 줄)
         번역문에도 같은 위치에 \n 을 넣으면 pdf2zh(패치판)가 그 자리에서 줄을 바꾼다.
"""
import json
import os
import re
import sqlite3
import sys

import pymupdf

DB = os.path.expanduser("~/.cache/pdf2zh/cache.v1.db")
LIST_RE = re.compile(r"^(\d+[.):]|[•\-–→▪◦·*])\s*")


def visual_lines(doc):
    """페이지별로 같은 기준선의 줄을 합친 '눈에 보이는 줄' 목록."""
    out = []
    for pno, page in enumerate(doc):
        raw = []
        for b in page.get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            for l in b["lines"]:
                t = "".join(s["text"] for s in l["spans"])
                if not t.strip():
                    continue
                size = max(s["size"] for s in l["spans"])
                raw.append({"t": t, "bbox": list(l["bbox"]), "size": size, "page": pno})
        merged = []
        for r in raw:
            p = merged[-1] if merged else None
            if p and abs(p["bbox"][3] - r["bbox"][3]) < 2 and r["bbox"][0] >= p["bbox"][0]:
                p["t"] += " " + r["t"]
                p["bbox"][2] = max(p["bbox"][2], r["bbox"][2])
                p["size"] = max(p["size"], r["size"])
            else:
                merged.append(r)
        out.extend(merged)
    return out


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


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    pdf, marker, outp = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    con = sqlite3.connect(DB)
    rows = con.execute(
        "select id, original_text from _translationcache "
        "where translate_engine='bing' and id>? order by id",
        (marker,),
    ).fetchall()
    L = visual_lines(pymupdf.open(pdf))
    res = []
    for i, src in rows:
        lines, n = annotate(src, L)
        res.append({"id": i, "src": src, "lines": lines, "hard_breaks": n})
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(f"{len(res)} segments, {sum(1 for r in res if r['hard_breaks'])} with hard line breaks -> {outp}")


if __name__ == "__main__":
    main()
