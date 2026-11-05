"""번역된 PDF 페이지를 PNG로 렌더링해서 눈으로 확인한다.

usage: render_pages.py <pdf> <out_dir> [pages, 예: 1,4,10 | all] [dpi=70]
"""
import os
import sys

import pymupdf


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    pdf, out = sys.argv[1], sys.argv[2]
    sel = sys.argv[3] if len(sys.argv) > 3 else "all"
    dpi = int(sys.argv[4]) if len(sys.argv) > 4 else 70
    os.makedirs(out, exist_ok=True)
    d = pymupdf.open(pdf)
    pages = range(1, d.page_count + 1) if sel == "all" else [int(p) for p in sel.split(",")]
    for p in pages:
        path = os.path.join(out, f"p{p:02d}.png")
        d[p - 1].get_pixmap(dpi=dpi).save(path)
        print(path)


if __name__ == "__main__":
    main()
