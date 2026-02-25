"""LaTeX Beamer file parser.

Extracts preamble, frames, and tail from a LaTeX Beamer .tex file.
"""

import re
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Union

logger = logging.getLogger(__name__)

# Regex to match \begin{frame}...\end{frame} blocks (DOTALL for multiline).
_FRAME_PATTERN = re.compile(
    r"(\\begin\{frame\}.*?\\end\{frame\})", re.DOTALL
)

# Regex to match section/subsection commands.
_SECTION_PATTERN = re.compile(
    r"(\\(?:sub)?section\*?\{[^}]*\})"
)


@dataclass
class BeamerDocument:
    """Parsed representation of a LaTeX Beamer document.

    Attributes:
        preamble: Everything before the first ``\\begin{frame}``.
        content_items: Ordered list of frames and sections/subsections.
            Each item is either a frame string or a section/subsection command.
        tail: Everything after the last frame/section (includes
            ``\\end{document}``).
        source_path: Original file path, if available.
    """

    preamble: str
    content_items: List[str]
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
    # Find all frames and sections/subsections with their positions
    items = []
    
    # Find frames
    for match in _FRAME_PATTERN.finditer(text):
        items.append((match.start(), match.end(), match.group(0), 'frame'))
    
    # Find section/subsection commands
    for match in _SECTION_PATTERN.finditer(text):
        items.append((match.start(), match.end(), match.group(0), 'section'))
    
    if not items:
        raise ValueError(
            f"No \\begin{{frame}} blocks found"
            f"{f' in {source_path}' if source_path else ''}."
        )
    
    # Sort by position in document
    items.sort(key=lambda x: x[0])
    
    # Extract preamble (everything before first item)
    first_start = items[0][0]
    preamble = text[:first_start]
    
    # Extract tail (everything after last item)
    last_end = items[-1][1]
    tail = text[last_end:]
    
    # Extract content items in order
    content_items = [item[2] for item in items]
    
    frame_count = sum(1 for item in items if item[3] == 'frame')
    section_count = sum(1 for item in items if item[3] == 'section')
    
    logger.info(
        "Parsed %d frame(s) and %d section/subsection(s) from %s.",
        frame_count,
        section_count,
        source_path or "<string>",
    )
    return BeamerDocument(
        preamble=preamble,
        content_items=content_items,
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


def reconstruct(doc: BeamerDocument, translated_items: List[str], preamble_override: Optional[str] = None) -> str:
    """Rebuild the full LaTeX source from translated content items.

    Args:
        doc: The original parsed document (preamble/tail are reused).
        translated_items: Translated content items (frames and sections, same count as
            ``doc.content_items``).
        preamble_override: Optional preamble to use instead of doc.preamble.

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
    return preamble + "\n".join(translated_items) + doc.tail


def load_preamble_template(template_path: Path) -> str:
    """Load a preamble template from an external file.

    Args:
        template_path: Path to the preamble template file.

    Returns:
        Preamble text from the template.

    Raises:
        FileNotFoundError: If template file does not exist.
    """
    template_path = Path(template_path)
    if not template_path.exists():
        raise FileNotFoundError(f"Preamble template not found: {template_path}")
    preamble = template_path.read_text(encoding="utf-8")
    logger.info("Loaded preamble template from %s (%d chars).", template_path, len(preamble))
    return preamble
