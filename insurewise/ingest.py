"""
Safe PDF ingestion: PDF file -> PolicyDocument.

Run from the project folder:
    python -m insurewise.ingest policies/sample_cigna.pdf
    python -m insurewise.ingest policies/sample_cigna.pdf --page 17

This module never logs or prints extracted policy text (except --page, which you ask for).
"""

import argparse
import hashlib
import sys
from enum import Enum
from pathlib import Path

import pymupdf

from insurewise.models import Page, PolicyDocument

DEFAULT_MAX_FILE_MB = 50
DEFAULT_MAX_PAGES = 500
MIN_CHARS_FOR_TEXT = 20   # fewer visible characters than this = "no real text"


class IngestionErrorCode(str, Enum):
    """Stable, machine-readable codes. The API layer can map these to HTTP responses."""
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    PDF_PARSE_FAILED = "PDF_PARSE_FAILED"
    PDF_ENCRYPTED = "PDF_ENCRYPTED"
    PAGE_LIMIT_EXCEEDED = "PAGE_LIMIT_EXCEEDED"
    NO_EXTRACTABLE_TEXT = "NO_EXTRACTABLE_TEXT"


class IngestionError(Exception):
    """Raised when a PDF cannot be used at all. Messages are safe to show to users."""

    def __init__(self, code: IngestionErrorCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def __str__(self):
        return f"[{self.code.value}] {self.message}"


def _sha256(path: Path) -> str:
    """Hash the file in 1 MB blocks so large files do not fill memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def process_pdf(
    pdf_path,
    max_file_mb: float = DEFAULT_MAX_FILE_MB,
    max_pages: int = DEFAULT_MAX_PAGES,
    min_chars_for_text: int = MIN_CHARS_FOR_TEXT,
) -> PolicyDocument:
    """
    Read a policy PDF and return a PolicyDocument.

    Raises IngestionError for unusable files (wrong type, too big, corrupt, encrypted,
    too many pages, or no text anywhere). A few empty pages are NOT an error:
    they become page-level warnings.
    """
    path = Path(pdf_path).expanduser()
    name = path.name[:255]   # base name only; treated as untrusted text

    # ---- Checks before opening the file ----
    if not path.is_file():
        raise IngestionError(IngestionErrorCode.FILE_NOT_FOUND, f"File not found: {name}")
    if path.suffix.lower() != ".pdf":
        raise IngestionError(IngestionErrorCode.UNSUPPORTED_FILE_TYPE, f"Only .pdf files are supported: {name}")
    if path.stat().st_size > max_file_mb * 1024 * 1024:
        raise IngestionError(IngestionErrorCode.FILE_TOO_LARGE, f"File is larger than {max_file_mb} MB: {name}")

    file_hash = _sha256(path)

    # ---- Open ----
    try:
        # Open bounded bytes so a corrupt PDF cannot retain a Windows file handle.
        doc = pymupdf.open(stream=path.read_bytes(), filetype='pdf')
    except Exception as exc:
        raise IngestionError(IngestionErrorCode.PDF_PARSE_FAILED, f"Could not read this PDF: {name}") from exc

    # ---- Extract (finally = always close the file, even after an error) ----
    pages, warnings = [], []
    try:
        if doc.needs_pass:
            raise IngestionError(IngestionErrorCode.PDF_ENCRYPTED, f"PDF is password-protected: {name}")
        page_count = doc.page_count
        if page_count == 0:
            raise IngestionError(IngestionErrorCode.PDF_PARSE_FAILED, f"PDF has no pages: {name}")
        if page_count > max_pages:
            raise IngestionError(IngestionErrorCode.PAGE_LIMIT_EXCEEDED,
                                 f"PDF has {page_count} pages; the limit is {max_pages}.")

        for number in range(1, page_count + 1):   # starts at 1 = original PDF numbering
            try:
                page = doc[number - 1]
                text = page.get_text("text")
                image_count = len(page.get_images(full=True))
            except Exception:
                text, image_count = "", 0
                warnings.append(f"Page {number}: text extraction failed.")

            has_text = len(text.strip()) >= min_chars_for_text
            pages.append(Page(
                page_number=number,
                text=text if has_text else "",
                has_text=has_text,
                needs_ocr=(not has_text) and image_count > 0,   # heuristic, not perfect
            ))
        title = ((doc.metadata or {}).get("title") or "").strip() or None
    finally:
        doc.close()

    # ---- Decide the outcome ----
    if not any(p.has_text for p in pages):
        raise IngestionError(IngestionErrorCode.NO_EXTRACTABLE_TEXT,
                             "No extractable text found. This PDF is probably scanned and needs OCR.")

    empty = [p.page_number for p in pages if not p.has_text]
    ocr = [p.page_number for p in pages if p.needs_ocr]
    if empty:
        warnings.append(f"{len(empty)} page(s) have no extractable text, e.g. {empty[:10]}.")
    if ocr:
        warnings.append(f"{len(ocr)} page(s) look like images and may need OCR, e.g. {ocr[:10]}.")

    return PolicyDocument(
        policy_id=f"pol_{file_hash[:12]}",
        filename=name,
        file_hash=file_hash,
        page_count=len(pages),
        title=title,
        pages=pages,
        status="completed_with_warnings" if warnings else "completed",
        warnings=warnings,
    )


def main():
    parser = argparse.ArgumentParser(description="Ingest a policy PDF and print a summary.")
    parser.add_argument("pdf_path", nargs="?", default="policies/sample_cigna.pdf")
    parser.add_argument("--page", type=int, default=None, help="also print the text of this page")
    args = parser.parse_args()

    try:
        doc = process_pdf(args.pdf_path)
    except IngestionError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    print(f"Policy id  : {doc.policy_id}")
    print(f"Filename   : {doc.filename}")
    print(f"SHA-256    : {doc.file_hash[:16]}...")
    print(f"Title      : {doc.title}")
    print(f"Status     : {doc.status}")
    print(f"Pages      : {doc.page_count} total, {len(doc.text_pages())} with text")
    for warning in doc.warnings:
        print(f"Warning    : {warning}")

    if args.page is not None:
        if 1 <= args.page <= doc.page_count:
            print(f"\n----- Page {args.page} -----\n{doc.pages[args.page - 1].text or '(no text)'}")
        else:
            print(f"\nPage {args.page} does not exist (1 to {doc.page_count}).")


if __name__ == "__main__":
    main()
