"""LaTeX Beamer file parser.

Extracts preamble, frames, and tail from a LaTeX Beamer .tex file.
"""

import re
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional


logger = logging.getLogger(__name__)

# Regex to match \begin{frame}...\end{frame} blocks (DOTALL for multiline).
_FRAME_PATTERN = re.compile(
    r"(\\begin\{frame\}.*?\\end\{frame\})", re.DOTALL
)

# Regex to match section/subsection commands with robust nested brace handling.
# Matches \section{...} or \subsection{...} with optional * (starred version).
# Note: This pattern handles simple cases; for nested braces use _match_section_command.
_SECTION_PATTERN = re.compile(
    r"(\\(?:sub)?section\*?\s*\{(?:[^{}]|\{[^{}]*\})*\})"
)

_BEGIN_DOCUMENT = r"\\begin{document}"
_END_DOCUMENT = r"\\end{document}"


@dataclass
class BodyPart:
    """A segment of document body.

    Attributes:
        text: Raw text for this body segment.
        translatable: True for frames/sections that should be translated.
    """

    text: str
    translatable: bool


@dataclass
class DocumentTemplate:
    """Template parts extracted from a LaTeX document."""

    preamble: str
    begin_document: str | None
    end_document: str | None
    tail: str | None


@dataclass
class BeamerDocument:
    """Parsed representation of a LaTeX Beamer document.

    Attributes:
        preamble: Everything before ``\\begin{document}``.
        begin_document: The ``\\begin{document}`` marker.
        body_parts: Ordered list of body segments (frames/sections or passthrough).
        content_items: Ordered list of frames and sections/subsections to translate.
        end_document: The ``\\end{document}`` marker.
        tail: Everything after ``\\end{document}``.
        source_path: Original file path, if available.
    """

    preamble: str
    begin_document: str
    body_parts: List[BodyPart]
    content_items: List[str]
    end_document: str
    tail: str
    source_path: Path | None = None

    @property
    def frames(self) -> List[str]:
        """Return only frame items for backward compatibility."""
        return [item for item in self.content_items if item.strip().startswith('\\begin{frame}')]


def parse_beamer_tex(text: str, source_path: Path | None = None) -> BeamerDocument:
    """Parse a LaTeX Beamer file into preamble, content items, and tail.

    Args:
        text: Full LaTeX source text.
        source_path: Optional path used for logging purposes.

    Returns:
        A ``BeamerDocument`` with preamble, content_items (frames and sections), and tail.

    Raises:
        ValueError: If no ``\\begin{frame}`` blocks are found.
    """
    begin_match = re.search(_BEGIN_DOCUMENT, text)
    end_match = re.search(_END_DOCUMENT, text)
    if not begin_match or not end_match or end_match.start() < begin_match.end():
        raise ValueError(
            f"Missing \\begin{{document}} or \\end{{document}}"
            f"{f' in {source_path}' if source_path else ''}."
        )

    preamble = text[:begin_match.start()]
    begin_document = text[begin_match.start():begin_match.end()]
    body = text[begin_match.end():end_match.start()]
    end_document = text[end_match.start():end_match.end()]
    tail = text[end_match.end():]

    masked_body = _mask_whole_line_comments(body)

    items: list[tuple[int, int, str]] = []
    for match in _FRAME_PATTERN.finditer(masked_body):
        items.append((match.start(), match.end(), "frame"))

    for match in _SECTION_PATTERN.finditer(masked_body):
        items.append((match.start(), match.end(), "section"))

    frame_count = sum(1 for _, _, kind in items if kind == "frame")
    if frame_count == 0:
        raise ValueError(
            f"No \\begin{{frame}} blocks found"
            f"{f' in {source_path}' if source_path else ''}."
        )

    items.sort(key=lambda x: x[0])

    body_parts: List[BodyPart] = []
    content_items: List[str] = []
    cursor = 0
    section_count = 0

    for start, end, kind in items:
        if cursor < start:
            body_parts.append(BodyPart(text=body[cursor:start], translatable=False))
        item_text = body[start:end]
        body_parts.append(BodyPart(text=item_text, translatable=True))
        content_items.append(item_text)
        cursor = end
        if kind == "section":
            section_count += 1

    if cursor < len(body):
        body_parts.append(BodyPart(text=body[cursor:], translatable=False))
    
    logger.info(
        "Parsed %d frame(s) and %d section/subsection(s) from %s.",
        frame_count,
        section_count,
        source_path or "<string>",
    )
    return BeamerDocument(
        preamble=preamble,
        begin_document=begin_document,
        body_parts=body_parts,
        content_items=content_items,
        end_document=end_document,
        tail=tail,
        source_path=source_path,
    )


def read_and_parse(filepath: Path) -> BeamerDocument:
    """Read a LaTeX file from disk and parse it.

    Args:
        filepath: Path to the ``.tex`` file.

    Returns:
        A ``BeamerDocument``.

    Raises:
        FileNotFoundError: If *filepath* does not exist.
        ValueError: Propagated from ``parse_beamer_tex``.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"Input file not found: {filepath}")
    text = filepath.read_text(encoding="utf-8")
    return parse_beamer_tex(text, source_path=filepath)


def reconstruct(
    doc: BeamerDocument,
    translated_items: List[str],
    preamble_override: Optional[str] = None,
    tail_override: Optional[str] = None,
) -> str:
    """Rebuild the full LaTeX source from translated content items.

    Args:
        doc: The original parsed document (preamble/body/tail are reused).
        translated_items: Translated content items (frames and sections, same count as
            ``doc.content_items``).
        preamble_override: Optional preamble to use instead of doc.preamble.
        tail_override: Optional tail to use instead of doc.tail.
    Returns:
        Complete LaTeX source text ready to be written to disk.

    Raises:
        ValueError: If the number of translated items does not match
            the original.
    """
    if len(translated_items) != len(doc.content_items):
        raise ValueError(
            f"Content item count mismatch: expected {len(doc.content_items)}, "
            f"got {len(translated_items)}."
        )
    
    preamble = preamble_override if preamble_override is not None else doc.preamble
    begin_document = doc.begin_document
    end_document = doc.end_document
    tail = tail_override if tail_override is not None else doc.tail

    rebuilt_body: List[str] = []
    translated_iter = iter(translated_items)
    for part in doc.body_parts:
        if part.translatable:
            rebuilt_body.append(next(translated_iter))
        else:
            rebuilt_body.append(part.text)

    return preamble + begin_document + "".join(rebuilt_body) + end_document + tail


def load_document_template(template_path: Path) -> DocumentTemplate:
    """Load a full-document template from an external file.

    Args:
        template_path: Path to the template file.

    Returns:
        Extracted template parts from a complete LaTeX document.

    Raises:
        FileNotFoundError: If template file does not exist.
    """
    template_path = Path(template_path)
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    template_text = template_path.read_text(encoding="utf-8")
    begin_match = re.search(_BEGIN_DOCUMENT, template_text)
    end_match = re.search(_END_DOCUMENT, template_text)

    if not begin_match or not end_match or end_match.start() < begin_match.end():
        raise ValueError(
            f"Template must include \\begin{{document}} and \\end{{document}}"
            f"{f' in {template_path}'}."
        )

    preamble = template_text[:begin_match.start()]
    begin_document = template_text[begin_match.start():begin_match.end()]
    end_document = template_text[end_match.start():end_match.end()]
    tail = template_text[end_match.end():]
    logger.info(
        "Loaded document template from %s (%d chars).",
        template_path,
        len(template_text),
    )
    return DocumentTemplate(
        preamble=preamble,
        begin_document=begin_document,
        end_document=end_document,
        tail=tail,
    )


def _mask_whole_line_comments(text: str) -> str:
    """Mask whole-line comments while preserving character positions."""
    masked_lines = []
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("%"):
            content = line.rstrip("\r\n")
            newline = line[len(content):]
            masked_lines.append(" " * len(content) + newline)
        else:
            masked_lines.append(line)
    return "".join(masked_lines)
