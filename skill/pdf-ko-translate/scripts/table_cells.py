"""표를 셀 단위로 번역하게 만든다 (pdf2zh_claude.py가 pdf2zh 안에서 불러 씀).

pdf2zh 1.9.11은 레이아웃 모델이 '표(table)'로 본 영역을 통째로 번역에서 뺀다.
여기서는 레이아웃 결과를 가로채 표 상자 하나를 '셀 상자' 여러 개로 바꾼다.
  - 셀 안에서 여러 줄로 나뉜 글은 한 문단으로 합친다(여러 줄 셀 합치기).
    합친 문단은 원래 셀 폭 안에서 줄을 바꿔 아래 행과 겹치지 않는다.
  - 숫자·기호만 있는 칸은 번역하지 않고 원문 그대로 둔다.

환경 변수
  PDF2ZH_TABLE_CELLS=0        표 번역 끄기 (pdf2zh 기본 동작: 표는 원문 유지)
  PDF2ZH_TABLE_LINE_SKIP=1.35 위아래 줄 기준선 간격이 글자 크기의 몇 배 이하일 때 같은 셀로 합칠지
"""
import os
import re

import numpy as np

WORD_RE = re.compile(r"[A-Za-z]{2,}")


def _pieces(page, clip):
    """표 영역의 글자를 '칸 조각'으로 나눈다. 같은 줄이라도 간격이 넓으면 다른 칸."""
    out = []
    d = page.get_text("rawdict", clip=clip)
    for b in d["blocks"]:
        if b["type"] != 0:
            continue
        for line in b["lines"]:
            cur = None
            for span in line["spans"]:
                size = span["size"]
                for ch in span["chars"]:
                    c = ch["c"]
                    x0, y0, x1, y1 = ch["bbox"]
                    if cur and x0 - cur["bbox"][2] > 0.8 * max(size, cur["size"]):
                        out.append(cur)
                        cur = None
                    if c.isspace() and cur is None:
                        continue
                    if cur is None:
                        cur = {"t": "", "bbox": [x0, y0, x1, y1], "size": size, "chars": []}
                    cur["t"] += c
                    cur["chars"].append((c, x0, y0, x1, y1))
                    bb = cur["bbox"]
                    bb[0], bb[1], bb[2], bb[3] = min(bb[0], x0), min(bb[1], y0), max(bb[2], x1), max(bb[3], y1)
                    cur["size"] = max(cur["size"], size)
            if cur:
                out.append(cur)
    out = _split_columns([p for p in out if p["t"].strip()])
    for p in out:
        p["tr"] = bool(WORD_RE.search(p["t"]))
    return out


def _piece(chars, size):
    t = "".join(c[0] for c in chars).strip()
    xs = [c for c in chars if not c[0].isspace()]
    return {"t": t, "size": size, "chars": chars,
            "bbox": [min(c[1] for c in xs), min(c[2] for c in xs), max(c[3] for c in xs), max(c[4] for c in xs)]}


def _split_columns(P):
    """칸 사이 여백이 좁아 한 조각이 된 경우, 다른 행들이 시작하는 x 위치(열 경계)에서 자른다."""
    starts = [round(p["bbox"][0]) for p in P]
    cols = sorted({x for x in starts if starts.count(x) >= 2})
    out = []
    for p in P:
        cut, cur = [], []
        for k, ch in enumerate(p["chars"]):
            if cur and not ch[0].isspace() and p["chars"][k - 1][0].isspace() and any(abs(ch[1] - x) <= 1.0 for x in cols):
                cut.append(cur)
                cur = []
            cur.append(ch)
        cut.append(cur)
        out += [_piece(c, p["size"]) for c in cut if "".join(x[0] for x in c).strip()]
    return out


def _rules(page, clip, size):
    """표 안의 가로줄(행 구분선) y 좌표."""
    ys = []
    try:
        for dr in page.get_drawings():
            r = dr.get("rect")
            if r is None or not r.intersects(clip):
                continue
            if r.height < 1.5 and r.width > 2 * size:
                ys.append((r.y0 + r.y1) / 2)
    except Exception:
        pass
    return ys


def cell_groups(page, clip, line_skip):
    """[(rect(x0,y0,x1,y1), translatable)]  rect는 PyMuPDF 좌표(위가 0)."""
    P = _pieces(page, clip)
    if not P:
        return []
    size = float(np.median([p["size"] for p in P]))
    rules = _rules(page, clip, size)
    P.sort(key=lambda p: (p["bbox"][1], p["bbox"][0]))
    parent = list(range(len(P)))
    taken_below = set()

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for bi, B in enumerate(P):
        if not B["tr"]:
            continue
        best, best_gap = None, None
        for ai in range(bi):
            A = P[ai]
            if not A["tr"] or ai in taken_below:
                continue
            s = max(A["size"], B["size"])
            pitch = B["bbox"][3] - A["bbox"][3]  # 기준선(아래 끝) 간격
            if not (0.5 * s < pitch <= line_skip * s):
                continue
            ax0, ax1, bx0, bx1 = A["bbox"][0], A["bbox"][2], B["bbox"][0], B["bbox"][2]
            if min(ax1, bx1) - max(ax0, bx0) <= 0:  # 가로로 겹쳐야 같은 칸
                continue
            left = abs(ax0 - bx0) < 0.6 * s
            center = abs((ax0 + ax1) / 2 - (bx0 + bx1) / 2) < 0.6 * s
            inside = bx0 >= ax0 - 0.6 * s and bx1 <= ax1 + 0.6 * s
            if not (left or center or inside):
                continue
            ya = (A["bbox"][1] + A["bbox"][3]) / 2
            yb = (B["bbox"][1] + B["bbox"][3]) / 2
            if any(ya < y < yb for y in rules):  # 사이에 가로줄 = 다른 행
                continue
            if best is None or pitch < best_gap:
                best, best_gap = ai, pitch
        if best is not None:
            taken_below.add(best)
            parent[find(bi)] = find(best)

    groups = {}
    for i, p in enumerate(P):
        groups.setdefault(find(i), []).append(p)
    res = []
    for g in groups.values():
        x0 = min(p["bbox"][0] for p in g)
        y0 = min(p["bbox"][1] for p in g)
        x1 = max(p["bbox"][2] for p in g)
        y1 = max(p["bbox"][3] for p in g)
        res.append(((x0, y0, x1, y1), any(p["tr"] for p in g)))
    return res


class TableCellModel:
    """pdf2zh의 레이아웃 모델을 감싸 표 상자를 셀 상자로 바꿔 돌려준다."""

    def __init__(self, model, doc, pages, line_skip, tables=True, keep_refs=True):
        self._m = model
        self._doc = doc
        self._order = [p for p in range(doc.page_count) if not pages or p in pages]
        self._k = 0
        self._skip = line_skip
        self._tables = tables
        self._refs = {}
        if keep_refs:
            from refs import reference_boxes

            try:
                self._refs = reference_boxes(doc)
            except Exception as e:
                print(f"[refs] 참고문헌 찾기 실패: {e}")
        self.stats = {"tables": 0, "cells": 0, "ref_lines": sum(len(v) for v in self._refs.values())}

    def __getattr__(self, name):
        return getattr(self._m, name)

    def predict(self, image, *a, **kw):
        res = self._m.predict(image, *a, **kw)
        pno = self._order[self._k] if self._k < len(self._order) else None
        self._k += 1
        if pno is None:
            return res
        try:
            if self._tables:
                self._split(res[0], self._doc[pno])
        except Exception as e:  # 표 처리 실패 시 원래 동작(표는 원문 유지)
            print(f"[table_cells] page {pno + 1}: {e}")
        if pno in self._refs:
            self._keep(res[0], self._refs[pno])
        return res

    def _keep(self, r, rects):
        """참고문헌 줄 영역을 '손대지 않음(abandon)'으로 표시 -> 원본 글자가 그대로 남는다."""
        from pdf2zh.doclayout import YoloBox

        inv = {v: k for k, v in r.names.items()}
        if "abandon" not in inv:
            return
        for x0, y0, x1, y1 in rects:
            r.boxes.append(YoloBox(np.array([x0, y0, x1, y1, 1.0, inv["abandon"]], dtype=np.float32)))

    def _split(self, r, page):
        from pdf2zh.doclayout import YoloBox
        import pymupdf

        names = r.names
        inv = {v: k for k, v in names.items()}
        if "table" not in inv:
            return
        tcls, text_cls, keep_cls = inv["table"], inv.get("plain text"), inv.get("abandon")
        if text_cls is None or keep_cls is None:
            return
        kept, extra = [], []
        for b in r.boxes:
            if int(b.cls) != tcls:
                kept.append(b)
                continue
            x0, y0, x1, y1 = [float(v) for v in np.asarray(b.xyxy).squeeze()[:4]]
            clip = pymupdf.Rect(x0 - 1, y0 - 1, x1 + 1, y1 + 1)
            groups = cell_groups(page, clip, self._skip)
            if not groups:
                kept.append(b)
                continue
            self.stats["tables"] += 1
            for (gx0, gy0, gx1, gy1), tr in groups:
                cls = text_cls if tr else keep_cls
                self.stats["cells"] += int(tr)
                # pdf2zh는 상자를 1px씩 넓혀 쓰므로, 이웃 칸을 덮지 않게 살짝 줄인다
                extra.append(YoloBox(np.array([gx0 + 0.5, gy0 + 0.5, gx1 - 0.5, gy1 - 0.5, 1.0, cls], dtype=np.float32)))
        r.boxes = kept + extra  # 셀 상자를 뒤에 둬야 겹치는 일반 문단 상자보다 우선


def install(high_level):
    """high_level.translate_patch를 감싸 레이아웃 모델을 TableCellModel로 바꾼다."""
    tables = os.environ.get("PDF2ZH_TABLE_CELLS", "1") != "0"
    keep_refs = os.environ.get("PDF2ZH_KEEP_REFERENCES", "1") != "0"
    if not (tables or keep_refs):
        return
    skip = float(os.environ.get("PDF2ZH_TABLE_LINE_SKIP", "1.35"))
    orig = high_level.translate_patch

    def translate_patch(inf, **kw):
        if kw.get("model") is not None and kw.get("doc_zh") is not None:
            tm = TableCellModel(kw["model"], kw["doc_zh"], kw.get("pages"), skip, tables, keep_refs)
            kw["model"] = tm
            try:
                return orig(inf, **kw)
            finally:
                if tm.stats["tables"]:
                    print(f"[table] tables={tm.stats['tables']} cells={tm.stats['cells']}")
                if tm.stats["ref_lines"]:
                    print(f"[references] kept original lines={tm.stats['ref_lines']}")
        return orig(inf, **kw)

    high_level.translate_patch = translate_patch
