"""CLI entry-point for translating LaTeX Beamer slides via Google Gemini.

Usage::

    beamer-translate input.tex [-o output.zh.tex] [--model gemini-2.5-pro]
                               [--batch-size 3] [--max-tokens 20000]
                               [--verbose] [--dry-run]
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from tqdm import tqdm

from .beamer.gemini_client import DEFAULT_MODEL, GeminiTranslator
from .beamer.latex_parser import BeamerDocument, read_and_parse, reconstruct
from .beamer.utils import batch_frames, default_output_path, write_output

logger = logging.getLogger(__name__)


# ── Argument parsing ────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """Build and return the ``argparse.ArgumentParser``."""
    parser = argparse.ArgumentParser(
        prog="beamer-translate",
        description=(
            "Translate LaTeX Beamer slide decks from English to Chinese "
            "using the Google Gemini API."
        ),
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the input .tex file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: <input>.zh.tex).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Gemini model name (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=3,
        help="Maximum number of frames per API request (default: 3).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=20_000,
        help="Soft token limit per batch (default: 20000).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and batch without calling the Gemini API.",
    )
    return parser


# ── Logging setup ───────────────────────────────────────────────────────────

def _configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ── Pipeline ────────────────────────────────────────────────────────────────

def translate_pipeline(
    doc: BeamerDocument,
    batches: List[List[str]],
    translator: GeminiTranslator,
) -> List[str]:
    """Run translation across all batches with a progress bar.

    Args:
        doc: Parsed Beamer document (used only for metadata here).
        batches: Pre-computed frame batches.
        translator: Initialised ``GeminiTranslator`` instance.

    Returns:
        Flat list of translated frame strings (same order as
        ``doc.frames``).
    """
    translated: List[str] = []
    total_frames = sum(len(b) for b in batches)

    with tqdm(total=total_frames, desc="Translating", unit="frame") as pbar:
        for batch_idx, batch in enumerate(batches, 1):
            logger.info(
                "Processing batch %d/%d (%d frame(s)).",
                batch_idx,
                len(batches),
                len(batch),
            )
            result = translator.translate_batch(batch)
            translated.extend(result)
            pbar.update(len(batch))

    return translated


# ── Main entry-point ────────────────────────────────────────────────────────

def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry-point.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)

    # ── 1. Parse input ──────────────────────────────────────────────────
    input_path: Path = args.input
    output_path: Path = args.output or default_output_path(input_path)

    try:
        doc = read_and_parse(input_path)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1
    except ValueError as exc:
        logger.error("Parsing failed: %s", exc)
        return 1

    logger.info(
        "Parsed %d frame(s) from %s.",
        len(doc.frames),
        input_path,
    )

    # ── 2. Batch frames ────────────────────────────────────────────────
    batches = batch_frames(
        doc.frames,
        batch_size=args.batch_size,
        max_tokens=args.max_tokens,
    )
    logger.info(
        "Frames grouped into %d batch(es) (batch_size=%d, max_tokens=%d).",
        len(batches),
        args.batch_size,
        args.max_tokens,
    )

    if args.dry_run:
        for i, batch in enumerate(batches, 1):
            logger.info(
                "  Batch %d: %d frame(s), ~%d chars.",
                i,
                len(batch),
                sum(len(f) for f in batch),
            )
        logger.info("Dry-run complete. No API calls made.")
        return 0

    # ── 3. Translate ────────────────────────────────────────────────────
    try:
        translator = GeminiTranslator(
            model_name=args.model,
        )
    except EnvironmentError as exc:
        logger.error("%s", exc)
        return 1

    try:
        translated_frames = translate_pipeline(doc, batches, translator)
    except RuntimeError as exc:
        logger.error("Translation failed: %s", exc)
        return 1

    # ── 4. Reconstruct & write ──────────────────────────────────────────
    try:
        full_text = reconstruct(doc, translated_frames)
    except ValueError as exc:
        logger.error("Reconstruction failed: %s", exc)
        return 1

    write_output(full_text, output_path)
    logger.info("Done. Output: %s", output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
