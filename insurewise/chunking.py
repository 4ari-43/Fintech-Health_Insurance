"""
Split a PolicyDocument into Chunks (small, citable passages).

Every chunk is an exact, contiguous piece of the policy's cleaned text.
Heading lines are kept INSIDE the chunk text and also stored in `section`.

Run from the project folder:
    python -m insurewise.chunking policies/sample_cigna.pdf
    python -m insurewise.chunking policies/sample_cigna.pdf --page 17
"""

import argparse
import re
import sys
import textwrap
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass

from insurewise.ingest import IngestionError, process_pdf
from insurewise.models import Chunk, PolicyDocument

HEADING_HINTS = (
    "exclusion", "limitation", "emergency", "urgent care", "definition",
    "pre-admission", "pre admission", "precertification", "pre-certification",
    "prior authorization", "out-of-network", "out of network", "in-network",
    "covered services", "benefit", "schedule of", "general provisions",
    "inpatient", "outpatient", "prescription", "deductible", "coinsurance",
    "copayment", "waiting period",
)
SMALL_WORDS = {"and", "of", "the", "for", "to", "in", "or", "a", "an", "on", "with", "by"}
# A real heading never ends with one of these words (it would be a cut-off sentence).
BAD_ENDINGS = SMALL_WORDS | {"is", "are", "that", "which", "if", "when", "as", "at",
                             "be", "not", "will", "may", "shall"}

NUMBERED_HEADING_RE = re.compile(r"^\d+(?:\.\d+)*[\.\)]?\s+[A-Z]")
BULLET_RE = re.compile(r"^(?:[•●▪◦\-\*–]|\(?(?:\d{1,2}|[a-zA-Z])[\.\)])\s+")
PAGE_NUMBER_RE = re.compile(r"^(?:page\s+)?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?$", re.IGNORECASE)
FORM_CODE_RE = re.compile(r"^[A-Z]{1,5}-[A-Z]{0,6}\d+[A-Za-z0-9\-]*$")   # e.g. HC-COV631
REVISION_STAMP_RE = re.compile(r"^\d{2}-\d{2}$")   # form revision stamps such as 01-24
SENTENCE_BREAK_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"“•])")

MIN_CHUNK_CHARS = 40   # smaller chunks are merged into the previous one when possible


# ---------------------------------------------------------------- cleaning

def find_repeated_lines(pages, ratio=0.4, min_pages=5):
    """Lines repeated on many pages are running headers/footers, not policy clauses."""
    text_pages = [p for p in pages if p.has_text]
    if len(text_pages) < min_pages:
        return set()
    counts = Counter()
    for page in text_pages:
        counts.update({ln.strip() for ln in page.text.splitlines() if ln.strip()})
    limit = max(min_pages, int(len(text_pages) * ratio))
    return {line for line, n in counts.items() if n >= limit and len(line) <= 100}


def clean_lines(page, repeated):
    """Yield a page's lines without blanks, repeated headers/footers, page numbers or form codes."""
    for raw in page.text.splitlines():
        line = raw.strip()
        if (line and line not in repeated and not PAGE_NUMBER_RE.match(line)
                and not FORM_CODE_RE.match(line) and not REVISION_STAMP_RE.match(line)):
            yield line


def _capitalised_ratio(words):
    """Share of meaningful words that start with a capital letter."""
    content = [w for w in words if w[0].isalpha() and w.lower() not in SMALL_WORDS]
    return sum(w[0].isupper() for w in content) / len(content) if content else 0.0


def heading_strength(line):
    """2 = confident heading, 1 = maybe a heading, 0 = not a heading. A guess, not a certainty."""
    s = line.strip()
    if not 4 <= len(s) <= 80:
        return 0
    if any(c.isalpha() and ord(c) > 0x024F for c in s):   # NEW: Japanese, Arabic, etc. are not English headings
        return 0
    if s.endswith((".", ",", ";")) or "," in s or re.search(r"[.!?]\s", s):
           return 0
    if not s[0].isalnum() or s[0].islower():
           return 0
    words = s.split()
    if len(words) > 10 or not any(c.isalpha() for c in s):
        return 0
    if words[-1].lower().strip(":") in BAD_ENDINGS:
        return 0

    lowered = s.lower().rstrip(":").strip()
    if len(words) <= 8 and any(lowered.startswith(h) for h in HEADING_HINTS) \
            and _capitalised_ratio(words) >= 0.6:
        return 2
    if s.isupper() and len(words) <= 6:
        return 2
    if NUMBERED_HEADING_RE.match(s) and len(words) <= 8 and _capitalised_ratio(words[1:]) >= 0.6:
        return 2

    alpha_words = [w for w in words if w[0].isalpha()]
    if (2 <= len(words) <= 6 and alpha_words and alpha_words[0][0].isupper()
            and all(w[0].isupper() or w.lower() in SMALL_WORDS for w in alpha_words)):
        return 1
    return 0


# ------------------------------------------------- sentences that know their pages

@dataclass
class _Unit:
    text: str
    start_page: int
    end_page: int
    new_paragraph: bool
    is_heading: bool = False


def _paragraph_to_units(buffer, target_chars):
    """buffer = [(line, page), ...] for one paragraph -> sentence units with page numbers."""
    parts, offsets, pages, position = [], [], [], 0
    for line, page in buffer:
        if parts:
            position += 1
        offsets.append(position)
        pages.append(page)
        parts.append(line)
        position += len(line)
    text = " ".join(parts)

    def page_at(index):
        return pages[bisect_right(offsets, index) - 1]

    spans, start = [], 0
    for match in SENTENCE_BREAK_RE.finditer(text):
        spans.append((start, match.start()))
        start = match.end()
    spans.append((start, len(text)))

    units, first = [], True
    for span_start, span_end in spans:
        sentence = text[span_start:span_end]
        if not sentence.strip():
            continue
        if len(sentence) <= target_chars:
            pieces = [(sentence, span_start, span_end)]
        else:   # rare: one sentence longer than the target
            pieces, cursor = [], span_start
            for piece in textwrap.wrap(sentence, width=target_chars,
                                       break_long_words=False, break_on_hyphens=False):
                found = text.find(piece, cursor)
                found = cursor if found == -1 else found
                pieces.append((piece, found, found + len(piece)))
                cursor = found + len(piece)
        for piece_text, p_start, p_end in pieces:
            units.append(_Unit(piece_text, page_at(p_start), page_at(max(p_start, p_end - 1)), first))
            first = False
    return units


# ------------------------------------------------------- packing into chunks

class _Packer:
    """Collects sentence units and emits chunks of roughly `target` characters."""

    def __init__(self, target, overlap):
        self.target, self.overlap = target, overlap
        self.units, self.fresh = [], 0   # fresh = units at the END that are not copied overlap
        self.section = None
        self.output = []                 # (text, start_page, end_page, section)
        self.skipped_dotted = 0

    def _fresh_units(self):
        return self.units[len(self.units) - self.fresh:]

    def _size(self):
        return sum(len(u.text) + 1 for u in self.units)

    def add(self, unit):
        has_body = any(not u.is_heading for u in self._fresh_units())
        size = self._size()
        if has_body and size + len(unit.text) > self.target:
            self._flush(carry_overlap=True)
        elif has_body and unit.new_paragraph and size >= 0.7 * self.target:
            self._flush(carry_overlap=True)   # prefer breaking between paragraphs
        self.units.append(unit)
        self.fresh += 1

    def new_section(self, label, page):
        """Start a new section. The heading line itself becomes part of the chunk text."""
        self._flush(carry_overlap=False)
        self.section = label
        self.units.append(_Unit(label, page, page, True, is_heading=True))
        self.fresh += 1

    def finish(self):
        self._flush(carry_overlap=False)

    def _flush(self, carry_overlap):
        fresh_units = self._fresh_units()
        if any(not u.is_heading for u in fresh_units):
            all_text = " ".join(u.text for u in self.units)
            new_text = " ".join(u.text for u in fresh_units)
            start = min(u.start_page for u in self.units)
            end = max(u.end_page for u in self.units)
            self._emit(all_text, new_text, start, end)

            carried, total = [], 0
            if carry_overlap:
                for unit in reversed(self.units):
                    if total + len(unit.text) > self.overlap:
                        break
                    carried.insert(0, unit)
                    total += len(unit.text) + 1
            self.units, self.fresh = carried, 0
        elif not carry_overlap:
            # Only headings so far (a heading directly followed by a sub-heading):
            # keep them so they prefix the next section's text instead of becoming a tiny chunk.
            self.units, self.fresh = fresh_units, len(fresh_units)

    def _emit(self, text, new_text, start, end):
        if text.count(".") / len(text) > 0.3:      # table-of-contents dot leaders
            self.skipped_dotted += 1
            return
        if len(text) < MIN_CHUNK_CHARS and self.output and self.output[-1][3] == self.section:
            prev_text, prev_start, prev_end, prev_section = self.output[-1]
            self.output[-1] = (prev_text + " " + new_text, prev_start, max(prev_end, end), prev_section)
            return
        self.output.append((text, start, end, self.section))


# --------------------------------------------------------------- public API

def chunk_policy_with_report(policy: PolicyDocument, target_chars=1000, overlap_chars=150,
                             repeated_line_ratio=0.4):
    """Returns (chunks, report). `report` lists what was removed, so nothing is hidden."""
    if target_chars < 200:
        raise ValueError("target_chars should be at least 200.")
    if not 0 <= overlap_chars < target_chars:
        raise ValueError("overlap_chars must be between 0 and target_chars.")

    repeated = find_repeated_lines(policy.pages, repeated_line_ratio)
    packer = _Packer(target_chars, overlap_chars)
    buffer = []   # (line, page) pairs of the paragraph being built

    def flush_paragraph():
        if buffer:
            for unit in _paragraph_to_units(buffer, target_chars):
                packer.add(unit)
            buffer.clear()

    for page in policy.pages:
        if not page.has_text:
            continue
        for line in clean_lines(page, repeated):
            strength = heading_strength(line)
            previous_ended = (not buffer) or buffer[-1][0].endswith((".", ":", "?", "!"))
            if strength == 2 or (strength == 1 and previous_ended):
                flush_paragraph()
                packer.new_section(line, page.page_number)
                continue
            if BULLET_RE.match(line):
                flush_paragraph()
            buffer.append((line, page.page_number))

    flush_paragraph()
    packer.finish()

    counters, chunks = Counter(), []
    for text, start, end, section in packer.output:
        counters[start] += 1
        chunks.append(Chunk(
            chunk_id=f"{policy.policy_id}-p{start:03d}-c{counters[start]:02d}",
            policy_id=policy.policy_id,
            text=text,
            page_start=start,
            page_end=end,
            section=section,
        ))
    report = {
        "repeated_lines_removed": sorted(repeated),
        "table_of_contents_chunks_skipped": packer.skipped_dotted,
    }
    return chunks, report


def chunk_policy(policy: PolicyDocument, target_chars=1000, overlap_chars=150):
    """Main entry point for other modules: PolicyDocument -> list[Chunk]."""
    return chunk_policy_with_report(policy, target_chars, overlap_chars)[0]


# ------------------------------------------------------ page-accuracy check

def _norm(text):
    return " ".join(text.split())


def _starts_on(text, page_text, page):
    """Does the chunk's beginning sit on `page` (not on the next page)?"""
    own = page_text.get(page, "")
    joined = own + " " + page_text.get(page + 1, "")
    index = joined.find(text[:30])
    return 0 <= index < len(own)


def _ends_on(text, page_text, page):
    """Does the chunk's ending sit on `page` (not on the previous page)?"""
    prev = page_text.get(page - 1, "")
    joined = prev + " " + page_text.get(page, "")
    tail = text[-30:]
    index = joined.rfind(tail)
    return index >= 0 and index + len(tail) > len(prev) + 1


def verify_chunk_pages(policy: PolicyDocument, chunks):
    """
    Strict check. For every chunk:
      1. its ENTIRE text must appear exactly in the cleaned text of pages page_start..page_end,
      2. its beginning must be on page_start and its ending on page_end.
    Returns a list of problems (empty = all good).
    """
    repeated = find_repeated_lines(policy.pages)
    page_text = {p.page_number: _norm(" ".join(clean_lines(p, repeated))) for p in policy.pages}
    problems = []
    for chunk in chunks:
        text = _norm(chunk.text)
        span = " ".join(page_text.get(n, "") for n in range(chunk.page_start, chunk.page_end + 1))
        label = f"{chunk.chunk_id} (pages {chunk.page_start}-{chunk.page_end})"
        if text not in span:
            problems.append(f"{label}: text not found in those pages. Starts: {chunk.text[:80]!r}")
        elif not _starts_on(text, page_text, chunk.page_start):
            problems.append(f"{label}: beginning is not on page_start. Starts: {chunk.text[:80]!r}")
        elif not _ends_on(text, page_text, chunk.page_end):
            problems.append(f"{label}: ending is not on page_end. Ends: {chunk.text[-80:]!r}")
    return problems


# -------------------------------------------------------------- CLI report

def _print_chunk(chunk):
    pages = str(chunk.page_start) if chunk.page_start == chunk.page_end else f"{chunk.page_start}-{chunk.page_end}"
    print(f"\n[{chunk.chunk_id}]  pages {pages}  |  section: {chunk.section}")
    print(chunk.text)


def main():
    parser = argparse.ArgumentParser(description="Chunk a policy PDF and report the result.")
    parser.add_argument("pdf_path", nargs="?", default="policies/sample_cigna.pdf")
    parser.add_argument("--target", type=int, default=1000)
    parser.add_argument("--overlap", type=int, default=150)
    parser.add_argument("--show", type=int, default=3, help="number of sample chunks to print")
    parser.add_argument("--page", type=int, default=None, help="print chunks that start on this page")
    args = parser.parse_args()

    try:
        policy = process_pdf(args.pdf_path)
        chunks, report = chunk_policy_with_report(policy, args.target, args.overlap)
    except (IngestionError, ValueError) as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    sizes = [len(c.text) for c in chunks]
    print("=== SUMMARY ===")
    print(f"Pages with text          : {len(policy.text_pages())}")
    print(f"Chunks created           : {len(chunks)}")
    print(f"Chunk size (characters)  : min {min(sizes)}, avg {sum(sizes) // len(sizes)}, max {max(sizes)}")
    print(f"Chunks under 100 chars   : {sum(1 for s in sizes if s < 100)}")
    print(f"Chunks spanning pages    : {sum(1 for c in chunks if c.page_end > c.page_start)}")
    print(f"Repeated lines removed   : {report['repeated_lines_removed']}")
    print(f"Contents-page chunks skipped: {report['table_of_contents_chunks_skipped']}")

    print("\n=== MOST COMMON SECTION LABELS (do these look like real headings?) ===")
    for label, count in Counter(c.section for c in chunks).most_common(25):
        print(f"  {count:3d} x {label}")

    problems = verify_chunk_pages(policy, chunks)
    print(f"\n=== PAGE-ACCURACY CHECK: {len(problems)} problem(s) ===")
    for problem in problems[:10]:
        print("  -", problem)

    if args.page is not None:
        selected = [c for c in chunks if c.page_start == args.page]
        print(f"\n=== CHUNKS STARTING ON PAGE {args.page}: {len(selected)} ===")
    else:
        selected = chunks[: args.show]
        print(f"\n=== FIRST {args.show} CHUNKS ===")
    for chunk in selected:
        _print_chunk(chunk)


if __name__ == "__main__":
    main()