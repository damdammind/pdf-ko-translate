"""용어집 CSV 읽기와 원문 속 용어 찾기.

CSV 형식(UTF-8, 머리글 줄은 있어도 되고 없어도 됨, # 으로 시작하면 주석):
    source,target[,note]
    hallucination,환각
    retrieval-augmented generation,검색 증강 생성(RAG)
    Claude,Claude            <- 번역하지 않고 그대로 둘 이름

우선순위 (앞이 이김):
    1. export_segments.py --glossary 로 준 파일 (여러 개면 먼저 준 것이 우선)
    2. 개인 용어집  ~/.pdf-ko-translate/glossary.csv  (스킬을 업데이트해도 유지)
    3. 기본 용어집  <스킬 폴더>/glossary/*.csv       (--no-default-glossary 로 끔)
"""
import csv
import glob
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
USER_GLOSSARY = os.path.join(os.path.expanduser("~"), ".pdf-ko-translate", "glossary.csv")
DEFAULT_DIR = os.path.join(os.path.dirname(HERE), "glossary")


def read_csv(path):
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip() or row[0].lstrip().startswith("#"):
                continue
            if len(row) < 2 or not row[1].strip():
                continue
            src, tgt = row[0].strip(), row[1].strip()
            if src.lower() == "source" and tgt.lower() == "target":
                continue
            out.append((src, tgt))
    return out


def load(extra=(), use_default=True):
    """[(source, target, 출처)] 우선순위 높은 것이 이긴다. 대소문자 무시로 같은 source는 하나만."""
    files = [(p, os.path.basename(p)) for p in extra]
    if os.path.exists(USER_GLOSSARY):
        files.append((USER_GLOSSARY, "개인"))
    if use_default:
        files += [(p, "기본:" + os.path.basename(p)) for p in sorted(glob.glob(os.path.join(DEFAULT_DIR, "*.csv")))]
    seen, terms = set(), []
    for path, label in files:
        if not os.path.exists(path):
            raise SystemExit(f"용어집 파일이 없습니다: {path}")
        for src, tgt in read_csv(path):
            k = src.lower()
            if k in seen:
                continue
            seen.add(k)
            terms.append((src, tgt, label))
    return terms


def compile_terms(terms):
    """긴 용어부터 찾도록 정렬한 정규식 목록. 영어 복수형(s/es)도 같은 용어로 본다."""
    out = []
    for src, tgt, label in sorted(terms, key=lambda t: -len(t[0])):
        # 단어 사이 공백·하이픈은 있든 없든 같은 용어 (fine-tuning = fine tuning = finetuning)
        esc = r"[\s\-]*".join(re.escape(w) for w in re.split(r"[\s\-]+", src.strip()))
        flags = 0 if (src.isupper() and len(src) <= 5) else re.IGNORECASE  # 짧은 약어는 대소문자 구분
        out.append((re.compile(r"(?<![A-Za-z0-9])" + esc + r"(?:s|es)?(?![A-Za-z0-9])", flags), src, tgt))
    return out


def find(text, compiled):
    """text 안에 나온 용어 {source: target}. 긴 용어에 포함된 짧은 용어는 뺀다."""
    found, spans = {}, []
    for rx, src, tgt in compiled:
        for m in rx.finditer(text):
            if any(a <= m.start() and m.end() <= b for a, b in spans):
                continue
            spans.append((m.start(), m.end()))
            found[src] = tgt
    return found


def target_ok(tgt, translation):
    """번역문에 용어집 번역이 들어 있는가. '검색 증강 생성(RAG)'은 '검색 증강 생성'만 있어도 통과."""
    base = re.split(r"[(（]", tgt)[0].strip() or tgt
    norm = lambda s: re.sub(r"\s+", "", s)
    return norm(base) in norm(translation)
