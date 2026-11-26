"""Load source documents into page-indexed text and split them into chunks.

Pages:
  * PDF  – one page per PDF page (pdfplumber)
  * TXT/MD – split on `[[PAGE n]]` markers if present; otherwise one page
  * DOCX – paragraphs; `[[PAGE n]]` markers honoured if present; otherwise one page
  * HTML – tags stripped; treated like TXT
The verifier matches excerpts against exactly this text, so loading and
verification always see the same characters.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from pathlib import Path

PAGE_MARK = re.compile(r"\[\[PAGE\s+(\d+)\]\]")


@dataclass
class SourceDoc:
    source_id: str
    path: Path
    pages: dict[int, str] = field(default_factory=dict)   # page number -> text

    @property
    def full_text(self) -> str:
        return "\n".join(self.pages[p] for p in sorted(self.pages))

    @property
    def word_count(self) -> int:
        return sum(len(t.split()) for t in self.pages.values())


@dataclass
class Chunk:
    source_id: str
    index: int
    pages: list[int]
    text: str            # includes [[PAGE n]] markers so the agent can cite pages


def _split_markers(text: str) -> dict[int, str]:
    parts = PAGE_MARK.split(text)
    if len(parts) == 1:
        return {1: text}
    pages: dict[int, str] = {}
    if parts[0].strip():
        pages[0] = parts[0]
    for i in range(1, len(parts), 2):
        pages[int(parts[i])] = pages.get(int(parts[i]), "") + parts[i + 1]
    return pages


def load_source(source_id: str, path: Path) -> SourceDoc:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        import pdfplumber
        pages = {}
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                pages[i] = page.extract_text() or ""
    elif suffix in (".txt", ".md"):
        pages = _split_markers(path.read_text(encoding="utf-8", errors="replace"))
    elif suffix == ".docx":
        import docx
        text = "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
        pages = _split_markers(text)
    elif suffix in (".html", ".htm"):
        raw = path.read_text(encoding="utf-8", errors="replace")
        raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
        text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))
        pages = _split_markers(text)
    else:
        raise ValueError(f"{source_id}: unsupported file type {suffix}")
    return SourceDoc(source_id=source_id, path=path, pages=pages)


def chunk_source(doc: SourceDoc, chunk_words: int) -> list[Chunk]:
    """Group whole pages into chunks of about `chunk_words` words.

    A single page longer than the limit is split by paragraphs. Its chunks keep
    the same page number, so page citations stay correct.
    """
    chunks: list[Chunk] = []
    buf_pages: list[int] = []
    buf_text: list[str] = []
    words = 0

    def flush():
        nonlocal buf_pages, buf_text, words
        if buf_text:
            chunks.append(Chunk(doc.source_id, len(chunks), buf_pages[:], "".join(buf_text)))
        buf_pages, buf_text, words = [], [], 0

    for p in sorted(doc.pages):
        text = doc.pages[p]
        n = len(text.split())
        if n > chunk_words:
            flush()
            paras = re.split(r"\n\s*\n", text)
            part: list[str] = []
            pw = 0
            for para in paras:
                k = len(para.split())
                if pw + k > chunk_words and part:
                    chunks.append(Chunk(doc.source_id, len(chunks), [p], f"[[PAGE {p}]]\n" + "\n\n".join(part)))
                    part, pw = [], 0
                part.append(para)
                pw += k
            if part:
                chunks.append(Chunk(doc.source_id, len(chunks), [p], f"[[PAGE {p}]]\n" + "\n\n".join(part)))
            continue
        if words + n > chunk_words and buf_text:
            flush()
        buf_pages.append(p)
        buf_text.append(f"[[PAGE {p}]]\n{text}\n")
        words += n
    flush()
    return chunks


def prefilter_pages(doc: SourceDoc, pf: dict) -> tuple[list[int], list[int]]:
    """D-28: deterministic keyword filter for long documents. Returns (kept, skipped) page numbers."""
    pages = sorted(doc.pages)
    if len(pages) <= pf["apply_when_pages_over"]:
        return pages, []
    kws = [k.lower() for group in pf["keywords"].values() for k in group]
    pattern = re.compile(r"\b(?:" + "|".join(re.escape(k) for k in kws) + ")", re.I)
    first = set(pages[: pf["always_keep_first_pages"]])
    hits = {p for p in pages if p in first or pattern.search(doc.pages[p] or "")}
    n = pf.get("keep_neighbour_pages", 0)
    if n:
        hits |= {q for p in list(hits) for q in range(p - n, p + n + 1) if q in doc.pages}
    kept = [p for p in pages if p in hits]
    return kept, [p for p in pages if p not in hits]


def chunk_pages(doc: SourceDoc, keep: list[int], chunk_words: int) -> list[Chunk]:
    """chunk_source restricted to the kept pages."""
    sub = SourceDoc(doc.source_id, doc.path, {p: doc.pages[p] for p in keep})
    return chunk_source(sub, chunk_words)


def batch_chunks(chunks: list[Chunk], batch_words: int) -> list[list[Chunk]]:
    """Group consecutive chunks (any source) into prompts of about batch_words words.

    API mode uses small batches (cheaper retries). Paste mode uses large batches,
    so a person handles fewer prompts in claude.ai.
    """
    batches: list[list[Chunk]] = []
    cur: list[Chunk] = []
    words = 0
    for ch in chunks:
        n = len(ch.text.split())
        if cur and words + n > batch_words:
            batches.append(cur)
            cur, words = [], 0
        cur.append(ch)
        words += n
    if cur:
        batches.append(cur)
    return batches
