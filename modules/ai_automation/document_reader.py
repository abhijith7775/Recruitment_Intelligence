"""Resume document text extraction utilities for the AI Automation module.

Supports PDF, DOCX, TXT, and best-effort legacy DOC text extraction while
preserving clean error reporting when a document is missing, corrupted, or
contains no extractable text (e.g., scanned image-only PDFs).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Optional
import xml.etree.ElementTree as ET
import zipfile


MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".txt": "text/plain",
}

SUPPORTED_MIME_TYPES = set(MIME_BY_EXTENSION.values())


@dataclass
class DocumentReadResult:
    """Result returned after reading a resume document."""

    text: str
    mime_type: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error_code is None and bool(self.text.strip())


def infer_mime_type(file_name: str, explicit_mime_type: Optional[str] = None) -> str:
    """Infer a supported MIME type from an explicit value or file extension."""
    if explicit_mime_type and explicit_mime_type in SUPPORTED_MIME_TYPES:
        return explicit_mime_type
    suffix = Path(file_name).suffix.lower()
    return MIME_BY_EXTENSION.get(suffix, explicit_mime_type or "application/octet-stream")


def _clean_extracted_text(raw_text: str) -> str:
    """Normalize line breaks and whitespace while preserving line structure."""
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")

    # Normalize common PDF font kerning artifacts where intra-word spaces occur
    text = re.sub(r"\bE\s*D\s*U\s*C\s*A\s*T\s*I\s*O\s*N\b", "EDUCATION", text, flags=re.I)
    text = re.sub(r"\bE\s*X\s*P\s*E\s*R\s*I\s*E\s*N\s*C\s*E\b", "EXPERIENCE", text, flags=re.I)
    text = re.sub(r"\bP\s*R\s*O\s*J\s*E\s*C\s*T\s*S\b", "PROJECTS", text, flags=re.I)
    text = re.sub(r"\bS\s*K\s*I\s*L\s*L\s*S\b", "SKILLS", text, flags=re.I)
    text = re.sub(r"\bC\s*E\s*R\s*T\s*I\s*F\s*I\s*C\s*A\s*T\s*I\s*O\s*N\s*S?\b", "CERTIFICATIONS", text, flags=re.I)
    text = re.sub(r"\bB\s*\.?\s*T\s+ech\b", "B.Tech", text, flags=re.I)
    text = re.sub(r"\bM\s*\.?\s*T\s+ech\b", "M.Tech", text, flags=re.I)
    text = re.sub(r"\bB\s*\.?\s*S\s*c\b", "B.Sc", text, flags=re.I)
    text = re.sub(r"\bM\s*\.?\s*S\s*c\b", "M.Sc", text, flags=re.I)
    text = re.sub(r"\bB\s*\.?\s*C\s*\.?\s*A\b", "BCA", text, flags=re.I)
    text = re.sub(r"\bM\s*\.?\s*C\s*\.?\s*A\b", "MCA", text, flags=re.I)

    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    # Collapse runs of 3+ blank lines down to 2 to retain section separation.
    cleaned_lines: list[str] = []
    blank_run = 0
    for line in lines:
        if not line:
            blank_run += 1
            if blank_run <= 2:
                cleaned_lines.append("")
        else:
            blank_run = 0
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def _read_txt(file_path: Path) -> DocumentReadResult:
    """Read a plain-text resume trying common encodings."""
    raw_bytes = file_path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            text = _clean_extracted_text(raw_bytes.decode(encoding))
            if not text:
                return DocumentReadResult(
                    text="",
                    mime_type="text/plain",
                    error_code="EMPTY_DOCUMENT_TEXT",
                    error_message=f"No text content found in '{file_path.name}'.",
                )
            return DocumentReadResult(text=text, mime_type="text/plain")
        except UnicodeDecodeError:
            continue
    return DocumentReadResult(
        text="",
        mime_type="text/plain",
        error_code="DECODE_ERROR",
        error_message=f"Could not decode text file '{file_path.name}'.",
    )


def _read_docx_with_xml_fallback(file_path: Path) -> str:
    """Extract text from DOCX XML parts using the standard library."""
    chunks: list[str] = []
    with zipfile.ZipFile(file_path, "r") as zf:
        xml_names = [
            name
            for name in zf.namelist()
            if name == "word/document.xml"
            or (name.startswith("word/header") and name.endswith(".xml"))
            or (name.startswith("word/footer") and name.endswith(".xml"))
        ]
        for xml_name in sorted(xml_names):
            root = ET.fromstring(zf.read(xml_name))
            paragraphs: list[str] = []
            for elem in root.iter():
                if elem.tag.endswith("}p"):
                    runs = [t.text for t in elem.iter() if t.tag.endswith("}t") and t.text]
                    if runs:
                        paragraphs.append("".join(runs))
            if paragraphs:
                chunks.append("\n".join(paragraphs))
    return _clean_extracted_text("\n".join(chunks))


def _read_docx(file_path: Path) -> DocumentReadResult:
    """Read paragraphs, tables, headers, and footers from a DOCX resume."""
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    try:
        import docx  # type: ignore

        document = docx.Document(str(file_path))
        parts: list[str] = []

        for section in document.sections:
            for header_para in section.header.paragraphs:
                if header_para.text.strip():
                    parts.append(header_para.text.strip())

        for para in document.paragraphs:
            if para.text.strip():
                parts.append(para.text.strip())

        for table in document.tables:
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_cells:
                    parts.append(" | ".join(dict.fromkeys(row_cells)))

        for section in document.sections:
            for footer_para in section.footer.paragraphs:
                if footer_para.text.strip():
                    parts.append(footer_para.text.strip())

        text = _clean_extracted_text("\n".join(parts))
        if not text:
            text = _read_docx_with_xml_fallback(file_path)
    except ImportError:
        try:
            text = _read_docx_with_xml_fallback(file_path)
        except Exception as exc:
            return DocumentReadResult(
                text="",
                mime_type=mime,
                error_code="DOCX_READ_ERROR",
                error_message=f"Failed to read DOCX '{file_path.name}': {exc}",
            )
    except Exception as exc:
        return DocumentReadResult(
            text="",
            mime_type=mime,
            error_code="DOCX_READ_ERROR",
            error_message=f"Failed to read DOCX '{file_path.name}': {exc}",
        )

    if not text:
        return DocumentReadResult(
            text="",
            mime_type=mime,
            error_code="EMPTY_DOCUMENT_TEXT",
            error_message=f"No text content found in '{file_path.name}'.",
        )
    return DocumentReadResult(text=text, mime_type=mime)


def _read_pdf(file_path: Path) -> DocumentReadResult:
    """Extract text across all pages of a PDF resume."""
    mime = "application/pdf"
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(file_path))
        pages_text: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages_text.append(page_text)
        text = _clean_extracted_text("\n".join(pages_text))
    except ImportError:
        return DocumentReadResult(
            text="",
            mime_type=mime,
            error_code="MISSING_PDF_DEPENDENCY",
            error_message=(
                "pypdf is not installed in this Python interpreter. "
                "Install it with 'pip install pypdf'."
            ),
        )
    except Exception as exc:
        return DocumentReadResult(
            text="",
            mime_type=mime,
            error_code="PDF_READ_ERROR",
            error_message=f"Failed to read PDF '{file_path.name}': {exc}",
        )

    if not text:
        return DocumentReadResult(
            text="",
            mime_type=mime,
            error_code="EMPTY_DOCUMENT_TEXT",
            error_message=(
                f"No extractable text found in '{file_path.name}'. "
                "The PDF may be scanned/image-only."
            ),
        )
    return DocumentReadResult(text=text, mime_type=mime)


def _read_legacy_doc(file_path: Path) -> DocumentReadResult:
    """Best-effort text extraction for legacy .doc files (no external Word/LibreOffice)."""
    mime = "application/msword"
    raw = file_path.read_bytes()
    # Some .doc files are actually RTF or plain text saved with .doc extension.
    if raw.lstrip().startswith(b"{\\rtf"):
        stripped = re.sub(rb"\\[a-zA-Z]+-?\d* ?", b" ", raw)
        stripped = stripped.replace(b"{", b" ").replace(b"}", b" ")
        text = _clean_extracted_text(stripped.decode("latin-1", errors="ignore"))
        if text:
            return DocumentReadResult(text=text, mime_type=mime)

    # Extract readable ASCII/UTF-16LE spans if not an encrypted binary stream.
    utf16_runs = re.findall(rb"(?:[\x20-\x7e]\x00){6,}", raw)
    decoded_runs = [chunk.decode("utf-16-le", errors="ignore") for chunk in utf16_runs]
    ascii_runs = [
        chunk.decode("latin-1", errors="ignore")
        for chunk in re.findall(rb"[A-Za-z0-9@.,:+/()\- \t\r\n]{12,}", raw)
    ]
    combined = _clean_extracted_text("\n".join(decoded_runs or ascii_runs))
    if len(combined) >= 40 and any(ch.isalpha() for ch in combined):
        return DocumentReadResult(text=combined, mime_type=mime)

    return DocumentReadResult(
        text="",
        mime_type=mime,
        error_code="UNSUPPORTED_LEGACY_DOC",
        error_message=(
            f"Legacy binary .doc '{file_path.name}' could not be reliably parsed "
            "without Word/LibreOffice. Please convert to PDF or DOCX."
        ),
    )


def resolve_content_path(
    content_uri: Optional[str],
    file_name: str,
    base_dir: Optional[Path] = None,
) -> Optional[Path]:
    """Resolve a local path from content_uri or file_name."""
    candidates: list[Path] = []
    if content_uri:
        if content_uri.startswith("file://"):
            candidates.append(Path(content_uri[7:]))
        elif "://" not in content_uri:
            p = Path(content_uri)
            candidates.append(p)
            if base_dir and not p.is_absolute():
                candidates.append(base_dir / p)
    if file_name:
        p_name = Path(file_name)
        candidates.append(p_name)
        if base_dir and not p_name.is_absolute():
            candidates.append(base_dir / p_name)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def read_resume_document(
    file_path: Path,
    mime_type: Optional[str] = None,
) -> DocumentReadResult:
    """Read and return cleaned text from a PDF, DOCX, DOC, or TXT resume file."""
    resolved_mime = infer_mime_type(file_path.name, mime_type)
    if not file_path.exists() or not file_path.is_file():
        return DocumentReadResult(
            text="",
            mime_type=resolved_mime,
            error_code="FILE_NOT_FOUND",
            error_message=f"Resume file not found: '{file_path}'.",
        )

    if resolved_mime == "application/pdf":
        return _read_pdf(file_path)
    if resolved_mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _read_docx(file_path)
    if resolved_mime == "text/plain":
        return _read_txt(file_path)
    if resolved_mime == "application/msword":
        return _read_legacy_doc(file_path)

    return DocumentReadResult(
        text="",
        mime_type=resolved_mime,
        error_code="UNSUPPORTED_MIME_TYPE",
        error_message=f"Unsupported resume format '{resolved_mime}' for '{file_path.name}'.",
    )
