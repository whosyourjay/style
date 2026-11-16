"""Post-build checks for TikZ/mdframed named theorem boxes.

Unlike a source/log check, this reads the borders actually drawn in the PDF.
An open bottom and a matching open top on the next page identify a split;
ordinary adjacent boxes and references to a lemma are not continuations.
PDF coordinates and thresholds are in points (72 pt = one inch).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from statistics import median
import sys


TITLE_RE = re.compile(
    r"\b(?:Theorem|Lemma|Corollary|Proposition|Definition|Claim|Remark|"
    r"Conjecture|Example|Fact)\s+\d+(?:\.\d+)*\b"
)
TOLERANCE = 1.5
BODY_MARGIN = 72  # geometry's one-inch margins in book-preamble.tex
SHORT_BOX = 216  # flag split boxes no taller than three inches in total
TINY_FRAGMENT = 72
MIN_TEXT_ROWS = 3
BLANK_GAP = 72


@dataclass(frozen=True)
class Frame:
    page: int
    x0: float
    x1: float
    top: float
    bottom: float
    color: tuple
    closed_top: bool
    closed_bottom: bool
    title: str
    text_rows: int

    @property
    def height(self) -> float:
        return self.bottom - self.top


@dataclass
class Page:
    number: int
    height: float
    content_bottom: float
    frames: list[Frame]


@dataclass(frozen=True)
class Finding:
    page: int
    rule: str
    message: str


def _near(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCE


def _color(value) -> tuple:
    return tuple(round(c, 3) for c in value) if isinstance(value, (tuple, list)) \
        else (round(value or 0, 3),)


def _segments(path: list) -> list:
    """Only accept straight paths; diagram curves must not become frames."""
    segments = []
    current = start = None
    for command in path:
        op = command[0]
        if op == "m":
            current = start = command[1]
        elif op in {"l", "h"} and current is not None:
            end = start if op == "h" else command[1]
            segments.append((current, end))
            current = end
        else:
            return []
    return segments


def _outlines(shapes: list) -> list:
    """Recognize the four-sided, three-sided and middle-piece frame paths."""
    paths = []
    verticals: dict[tuple, list] = {}
    for shape in shapes:
        # namedthmbox uses a 2 TeX-pt stroke (= 1.993 PDF points).
        if not shape.get("stroke") or not 1.8 <= (shape.get("linewidth") or 0) <= 2.2:
            continue
        color = _color(shape.get("stroking_color"))
        segments = _segments(shape.get("path") or [])
        if len(segments) == 1:
            (x0, y0), (x1, y1) = segments[0]
            if _near(x0, x1):
                key = (color, round(min(y0, y1), 1), round(max(y0, y1), 1))
                verticals.setdefault(key, []).extend(segments)
        elif segments:
            paths.append((color, segments))
    # mdframed may draw a middle piece as two separate vertical strokes.
    paths += [(key[0], edges) for key, edges in verticals.items() if len(edges) == 2]

    outlines = []
    for color, segments in paths:
        points = [point for segment in segments for point in segment]
        x0, x1 = min(p[0] for p in points), max(p[0] for p in points)
        top, bottom = min(p[1] for p in points), max(p[1] for p in points)
        if x1 - x0 < 80 or bottom - top < 1:
            continue
        sides = set()
        for (ax, ay), (bx, by) in segments:
            if _near(ax, bx) and _near(min(ay, by), top) and _near(max(ay, by), bottom):
                if _near(ax, x0):
                    sides.add("left")
                elif _near(ax, x1):
                    sides.add("right")
                else:
                    break
            elif _near(ay, by) and _near(min(ax, bx), x0) and _near(max(ax, bx), x1):
                if _near(ay, top):
                    sides.add("top")
                elif _near(ay, bottom):
                    sides.add("bottom")
                else:
                    break
            else:
                break
        else:
            if {"left", "right"} <= sides:
                outlines.append((x0, x1, top, bottom, color, "top" in sides, "bottom" in sides))
    return outlines


def count_text_rows(words: list) -> int:
    """Cluster baselines approximately, keeping math scripts with their row."""
    if not words:
        return 0
    tolerance = median(w["bottom"] - w["top"] for w in words) / 2
    centers = sorted((w["top"] + w["bottom"]) / 2 for w in words)
    rows, anchor = 0, float("-inf")
    for center in centers:
        if center - anchor > tolerance:
            rows += 1
            anchor = center
    return rows


def read_page(number: int, height: float, shapes: list, words: list, images: list) -> Page:
    """Pure geometry adapter, also used by the extracted-PDF regression tests."""
    frames = []
    for x0, x1, top, bottom, color, closed_top, closed_bottom in _outlines(shapes):
        inside = [w for w in words if x0 <= (w["x0"] + w["x1"]) / 2 <= x1]
        title_words = [w for w in inside if top - 14 <= w["top"] and w["bottom"] <= top + 13]
        title_text = " ".join(w["text"] for w in sorted(title_words, key=lambda w: w["x0"]))
        match = TITLE_RE.search(title_text) if closed_top else None
        title = match.group() if match else ""
        body_top = max(w["bottom"] for w in title_words) + 1 if title else top - 3
        body = [w for w in inside if body_top <= (w["top"] + w["bottom"]) / 2 <= bottom + 1]
        frames.append(Frame(number, x0, x1, top, bottom, color, closed_top,
                            closed_bottom, title, count_text_rows(body)))

    ink = words + images + [s for s in shapes if
        (s.get("stroke") and min(_color(s.get("stroking_color"))) < 0.99)
        or (s.get("fill") and min(_color(s.get("non_stroking_color"))) < 0.99)]
    # Exclude running headers/footers and background rectangles. A float below
    # the frame occupies real space and must not trigger the blank-gap test.
    bottoms = [min(s["bottom"], height - BODY_MARGIN) for s in ink
               if BODY_MARGIN - 3 <= s["top"] < height - BODY_MARGIN]
    return Page(number, height, max(bottoms, default=BODY_MARGIN),
                sorted(frames, key=lambda f: (f.top, f.x0)))


def _continues(first: Frame, second: Frame) -> bool:
    return not second.closed_top and not second.title \
        and first.color == second.color \
        and _near(first.x0, second.x0) and _near(first.x1, second.x1)


def check_pages(pages: list[Page]) -> tuple[list[Finding], int, int]:
    """Return findings, number of named boxes, and number of confirmed splits."""
    by_number = {p.number: p for p in pages}
    starts = [f for p in pages for f in p.frames if f.title]
    findings, split_count = [], 0
    claimed = set()
    for start in starts:
        if start.closed_bottom:
            continue
        chain = [start]
        while not chain[-1].closed_bottom:
            next_page = by_number.get(chain[-1].page + 1)
            candidates = [] if next_page is None else [
                f for f in next_page.frames if f not in claimed and _continues(start, f)]
            if len(candidates) != 1:
                findings.append(Finding(start.page, "E402",
                    f"{start.title}: cannot uniquely match the open border to a continuation "
                    f"on PDF page {chain[-1].page + 1}; check the frame or PDF style"))
                break
            chain.append(candidates[0])
            claimed.add(candidates[0])
        else:
            split_count += 1
            reasons = []
            total_height = sum(f.height for f in chain)
            if total_height <= SHORT_BOX:
                rows = sum(f.text_rows for f in chain)
                reasons.append(f"short box ({total_height:.0f} pt total, about {rows} text rows)")
            for f in chain:
                if f.height <= TINY_FRAGMENT and f.text_rows < MIN_TEXT_ROWS:
                    noun = "row" if f.text_rows == 1 else "rows"
                    reasons.append(f"only {f.text_rows} text {noun} in a {f.height:.0f} pt "
                                   f"fragment on PDF page {f.page}")
            for f in chain[:-1]:
                page = by_number[f.page]
                gap = page.height - BODY_MARGIN - f.bottom
                if gap >= BLANK_GAP and page.content_bottom <= f.bottom + TOLERANCE:
                    reasons.append(f"{gap:.0f} pt unused below the split on PDF page {f.page}")
            if reasons:
                findings.append(Finding(start.page, "E401",
                    f"{start.title} (PDF pages {start.page}-{chain[-1].page}): " + "; ".join(reasons)))
    return findings, len(starts), split_count


def check_pdf(path: Path) -> tuple[list[Finding], int, int]:
    try:
        import pdfplumber
        from pdfplumber.utils.exceptions import MalformedPDFException, PdfminerException
    except ImportError as exc:
        raise RuntimeError("PDF lint needs pdfplumber; install the optional layout group: "
                           "python3 -m pip install pdfplumber") from exc
    pages = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                pages.append(read_page(page.page_number, page.height,
                    page.rects + page.curves + page.lines, page.extract_words(), page.images))
                page.close()  # Do not retain the entire book's glyph/path caches.
    except (MalformedPDFException, PdfminerException) as exc:
        raise ValueError(f"cannot read PDF: {exc}") from exc
    return check_pages(pages)


def main(paths: list[str]) -> int:
    if not paths or any(p.startswith("-") for p in paths):
        print("usage: styleck --pdf BOOK.pdf [BOOK.pdf ...]", file=sys.stderr)
        return 2
    status = 0
    for filename in paths:
        try:
            findings, boxes, splits = check_pdf(Path(filename))
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"{filename}: {exc}", file=sys.stderr)
            status = 2
            continue
        for finding in findings:
            print(f"{filename}:{finding.page}: {finding.rule} {finding.message}")
        if not boxes:
            print(f"{filename}: no named theorem boxes detected; this checker requires "
                  "TikZ/mdframed named theorem boxes", file=sys.stderr)
            status = 2
        else:
            print(f"{filename}: checked {boxes} boxes, {splits} splits, {len(findings)} findings")
            status = max(status, int(bool(findings)))
    return status
