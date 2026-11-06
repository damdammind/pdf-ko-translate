"""참고문헌 구간 찾기 (export_segments.py와 table_cells.py가 같이 씀).

마지막 'References / Bibliography / 참고문헌' 제목 다음 줄부터, 'Appendix' 같은 부록 제목 전까지.
제목 줄 자체는 번역한다('참고문헌').
"""
import re

REF_HEAD = re.compile(
    r"^\s*(?:[\dIVX]+\.?\s+)?(references|bibliography|works cited|literature cited|reference list|참고\s*문헌)\s*$",
    re.IGNORECASE,
)
APPX_HEAD = re.compile(r"^\s*(appendix|appendices|supplementary|부록)\b", re.IGNORECASE)
SEC_HEAD = re.compile(r"^\s*[A-H](?:\.\d+)*\s{1,4}[A-Z][A-Za-z\-]+(?:\s+[A-Za-z\-:]+){0,10}\s*$")
YEAR = re.compile(r"(19|20)\d\d")


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


def reference_range(L):
    """참고문헌 구간 (제목 줄 번호, 끝 줄 번호) — 끝은 포함하지 않음. 없으면 None."""
    heads = [j for j, l in enumerate(L) if REF_HEAD.match(l["t"])]
    if not heads:
        return None
    start = heads[-1]
    body = [l["size"] for l in L[start + 1 : start + 40]]
    ref_size = sorted(body)[len(body) // 2] if body else L[start]["size"]
    end = len(L)
    for j in range(start + 1, len(L)):
        t = L[j]["t"]
        if len(t) > 90 or YEAR.search(t):
            continue
        if APPX_HEAD.match(t) or (SEC_HEAD.match(t) and L[j]["size"] > ref_size * 1.08):
            end = j
            break
    return start, end


def reference_boxes(doc):
    """{페이지 번호: [(x0, y0, x1, y1), ...]} 참고문헌 본문 줄들의 영역 (PyMuPDF 좌표)."""
    L = visual_lines(doc)
    rr = reference_range(L)
    out = {}
    if rr:
        for l in L[rr[0] + 1 : rr[1]]:
            out.setdefault(l["page"], []).append(tuple(l["bbox"]))
    return out
