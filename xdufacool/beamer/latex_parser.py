"""LaTeX Beamer file parser.

Extracts preamble, frames, and tail from a LaTeX Beamer .tex file.
"""

import re
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Regex to match \begin{frame}...\end{frame} blocks (DOTALL for multiline).
_FRAME_PATTERN = re.compile(
    r"(\\begin\{frame\}.*?\\end\{frame\})", re.DOTALL
)


@dataclass
class BeamerDocument:
    """Parsed representation of a LaTeX Beamer document.

    Attributes:
        preamble: Everything before the first ``\\begin{frame}``.
        frames: Ordered list of frame blocks (including delimiters).
        tail: Everything after the last ``\\end{frame}`` (includes
            ``\\end{document}``).
        source_path: Original file path, if available.
    """

    preamble: str
    frames: List[str]
    tail: str
    source_path: Path | None = None


def parse_beamer_tex(text: str, source_path: Path | None = None) -> BeamerDocument:
    """Parse a LaTeX Beamer file into preamble, frames, and tail.

    Args:
        text: Full LaTeX source text.
        source_path: Optional path used for logging purposes.

    Returns:
        A ``BeamerDocument`` with the three structural parts.

    Raises:
        ValueError: If no ``\\begin{frame}`` blocks are found.
    """
    frames = _FRAME_PATTERN.findall(text)
    if not frames:
        raise ValueError(
            f"No \\begin{{frame}} blocks found"
            f"{f' in {source_path}' if source_path else ''}."
        )

    first_start = text.index(frames[0])
    last_end = text.rindex(frames[-1]) + len(frames[-1])

    preamble = text[:first_start]
    tail = text[last_end:]

    logger.info(
        "Parsed %d frame(s) from %s.",
        len(frames),
        source_path or "<string>",
    )
    return BeamerDocument(
        preamble=preamble,
        frames=frames,
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


def reconstruct(doc: BeamerDocument, translated_frames: List[str]) -> str:
    """Rebuild the full LaTeX source from translated frames.

    Args:
        doc: The original parsed document (preamble/tail are reused).
        translated_frames: Translated frame strings (same count as
            ``doc.frames``).

    Returns:
        Complete LaTeX source text ready to be written to disk.

    Raises:
        ValueError: If the number of translated frames does not match
            the original.
    """
    if len(translated_frames) != len(doc.frames):
        raise ValueError(
            f"Frame count mismatch: expected {len(doc.frames)}, "
            f"got {len(translated_frames)}."
        )
    return doc.preamble + "\n".join(translated_frames) + doc.tail
