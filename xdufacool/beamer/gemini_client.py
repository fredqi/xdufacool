"""Google Gemini API client for LaTeX Beamer translation.

Handles prompt construction, API calls with retry/backoff, and
frame-count validation of responses.
"""

import logging
import os
import re
import time
from typing import List, Optional

from google import genai
from google.genai import types

from .latex_parser import _FRAME_PATTERN, _SECTION_PATTERN
from .utils import strip_latex_comments

logger = logging.getLogger(__name__)

# ── System instruction (verbatim per spec) ──────────────────────────────────

# SYSTEM_INSTRUCTION = (
#     "You are a professional LaTeX Beamer translator for machine learning "
#     "course slides.\n\n"
#     "Your task is to translate English text into Chinese while preserving "
#     "LaTeX structure exactly.\n\n"
#     "STRICT RULES:\n"
#     "1. DO NOT modify any LaTeX commands, environments, or syntax.\n"
#     "2. DO NOT translate:\n"
#     "   * commands themselves (e.g., \\begin, \\end, \\item, \\section, \\subsection)\n"
#     "   * math expressions ($...$, \\[...\\], equation, align, etc.)\n"
#     "   * labels, refs, citations, URLs, file paths\n"
#     "3. ONLY translate human-readable English text (including section/subsection titles).\n"
#     "4. Preserve:\n"
#     "   * frame boundaries\n"
#     "   * line breaks\n"
#     "   * indentation\n"
#     "5. DO NOT add or remove any content.\n"
#     "6. DO NOT output explanations or markdown.\n"
#     "7. Output must compile as valid LaTeX.\n"
#     "8. If uncertain, leave the text unchanged."
# )

SYSTEM_INSTRUCTION = (
    "You are an expert LaTeX Beamer translator specializing in machine learning and artificial intelligence.\n\n"
    "Your task is to translate the English text in the provided LaTeX source into natural, "
    "professional Simplified Chinese, while strictly preserving all LaTeX and Beamer structure.\n\n"
    "STRICT RULES:\n"
    "1. DOMAIN TERMINOLOGY: Use standard, widely accepted Chinese machine learning terminology.\n"
    "2. NO EXTRA OUTPUT: Output ONLY the raw translated LaTeX code. DO NOT output conversational text or explanations. DO NOT wrap the output in markdown code blocks (e.g., do not use ```latex ... ```). Start directly with the LaTeX code.\n"
    "3. WHAT TO TRANSLATE:\n"
    "   * Plain human-readable English text.\n"
    "   * Text inside structural and formatting commands (e.g., \\section{Translate}, \\frametitle{Translate}, \\textbf{Translate}, \\textcolor{red}{Translate}).\n"
    "4. WHAT NOT TO TRANSLATE:\n"
    "   * LaTeX command names and environments (e.g., \\begin, \\end, \\item).\n"
    "   * Beamer overlay specifications (e.g., <1->, <2>).\n"
    "   * Math expressions ($...$, $$...$$, \\[...\\], equation, align, etc.).\n"
    "   * System arguments: labels, references (\\ref, \\cite), URLs, and file paths (e.g., in \\includegraphics).\n"
    "5. STRUCTURAL INTEGRITY: Preserve all frame boundaries, exact line breaks, and indentation exactly as provided. Output must compile as valid LaTeX.\n"
    "6. SAFETY: DO NOT add or remove any structural content. If uncertain about translating a highly specific technical phrase, leave the English text unchanged."
)

# ── Defaults ────────────────────────────────────────────────────────────────

DEFAULT_MODEL = "gemini-3-flash-preview"
MAX_RETRIES = 2
RETRY_BACKOFF_BASE = 2.0  # seconds

# Known Gemini 2.5+ models (non-exhaustive, for validation hints)
RECOMMENDED_MODELS = [
    "gemini-pro-latest",
    "gemini-3.1-pro-preview",
    "gemini-3-pro-preview",
    "gemini-2.5-pro",
    "gemini-flash-latest",
    "gemini-3-flash-preview",
]


# ── Helpers ─────────────────────────────────────────────────────────────────

def _build_user_prompt(items: List[str]) -> str:
    """Compose the user message for a single batch of content items.
    
    Implements two robustness strategies:
    1. Count Injection: Explicitly tell the model how many items to return
    2. Rigid Delimiters: Insert % === FRAME_BOUNDARY_X === markers between items

    Args:
        items: List of LaTeX frame or section/subsection strings.

    Returns:
        Formatted user prompt with delimiters and count constraint.
    """
    # Strip comments from each item before sending to API
    cleaned_items = [strip_latex_comments(item) for item in items]
    
    # Strategy 2: Add rigid delimiters between items
    # This makes it nearly impossible for the model to merge items or lose boundaries
    delimited_content = []
    for idx, item in enumerate(cleaned_items, 1):
        boundary_marker = f"% === FRAME_BOUNDARY_{idx} ==="
        delimited_content.append(boundary_marker)
        delimited_content.append(item)
    
    joined = "\n\n".join(delimited_content)
    
    # Strategy 1: Count Injection
    # Explicitly tell the model the exact count to improve reliability
    return (
        f"Translate the following LaTeX Beamer content into Chinese. "
        f"I am providing you with exactly {len(items)} item(s). "
        f"You MUST return exactly {len(items)} translated item(s). "
        f"Do not alter or remove the % === FRAME_BOUNDARY_X === markers.\n\n"
        "<CONTENT>\n"
        f"{joined}\n"
        "</CONTENT>"
    )


def _count_items_in_text(text: str) -> int:
    r"""Count occurrences of frames and sections in *text*."""
    frame_count = len(_FRAME_PATTERN.findall(text))
    section_count = len(_SECTION_PATTERN.findall(text))
    return frame_count + section_count


def _extract_items_from_response(text: str) -> List[str]:
    r"""Extract frame and section blocks from an API response string.
    
    Uses FRAME_BOUNDARY markers as primary extraction method for robustness.
    Falls back to frame/section pattern matching if no markers are found.
    
    Handles both \\begin{frame}...\\end{frame} blocks and \\section/\\subsection commands.
    Items are ordered by their position in the response text.
    """
    items = []
    
    # Strategy 2 (Extraction): First try to use rigid delimiters
    # Look for % === FRAME_BOUNDARY_X === markers
    delimiter_pattern = re.compile(r"% === FRAME_BOUNDARY_\d+ ===")
    delimiter_matches = list(delimiter_pattern.finditer(text))
    
    if delimiter_matches:
        # Extract content between delimiters
        for i, match in enumerate(delimiter_matches):
            start = match.end()
            # End is either the next delimiter or the end of text
            end = delimiter_matches[i + 1].start() if i + 1 < len(delimiter_matches) else len(text)
            content = text[start:end].strip()
            if content:  # Only add non-empty content
                items.append(content)
        logger.debug(
            "Extracted %d item(s) using FRAME_BOUNDARY delimiters.",
            len(items),
        )
        return items
    
    # Fallback: Use original frame/section pattern matching
    extracted_items = []
    for match in _FRAME_PATTERN.finditer(text):
        extracted_items.append((match.start(), match.group(0)))
    for match in _SECTION_PATTERN.finditer(text):
        extracted_items.append((match.start(), match.group(0)))
    
    # Sort by position and return only the matched strings
    extracted_items.sort(key=lambda x: x[0])
    result = [item[1] for item in extracted_items]
    
    # Debug logging for mismatches
    frame_count = len(_FRAME_PATTERN.findall(text))
    section_count = len(_SECTION_PATTERN.findall(text))
    if not result:
        logger.debug(
            "No items extracted from response. "
            "Response length: %d chars, Frame matches: %d, Section matches: %d",
            len(text), frame_count, section_count
        )
    
    return result


# ── Client class ────────────────────────────────────────────────────────────

class GeminiTranslator:
    """Stateful wrapper around the Gemini generative-AI SDK.

    Args:
        model_name: Gemini model identifier.
        api_key: Explicit API key.  When *None* the ``GEMINI_API_KEY``
            environment variable is used.

    Raises:
        EnvironmentError: If no API key is available.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        api_key: Optional[str] = None,
        validate_model: bool = True,
    ) -> None:
        self.model_name = model_name
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self._api_key:
            raise EnvironmentError(
                "Gemini API key not found. Set the GEMINI_API_KEY "
                "environment variable or pass api_key explicitly."
            )
        self._client = genai.Client(api_key=self._api_key)
        
        # Validate model name if requested
        if validate_model:
            self._validate_model()
        
        logger.info("GeminiTranslator initialised (model=%s).", self.model_name)

    # ── Core translation method ─────────────────────────────────────────

    def translate_batch(
        self,
        items: List[str],
        *,
        max_retries: int = MAX_RETRIES,
    ) -> List[str]:
        """Translate a batch of content items (frames/sections), with retry & validation.
        
        Implements Strategy 3: Dynamic Batch Reduction on failure.
        If a full batch fails, splits it in half for retry attempts.

        Args:
            items: LaTeX frame or section/subsection strings to translate.
            max_retries: Number of retry attempts on item count mismatch.

        Returns:
            List of translated content item strings (same length as *items*).

        Raises:
            RuntimeError: If validation fails after all retries.
        """
        expected = len(items)
        prompt = _build_user_prompt(items)
        translated_items_list = []  # To collect results from split batches

        for attempt in range(1 + max_retries):
            try:
                response = self._call_api(prompt)
            except Exception as exc:
                logger.warning(
                    "API call failed (attempt %d/%d): %s",
                    attempt + 1,
                    1 + max_retries,
                    exc,
                )
                if attempt < max_retries:
                    self._backoff(attempt)
                    continue
                raise RuntimeError(
                    f"Gemini API call failed after {1 + max_retries} "
                    f"attempt(s): {exc}"
                ) from exc

            translated_items = _extract_items_from_response(response)
            if len(translated_items) == expected:
                logger.debug(
                    "Batch validated: %d item(s) in / %d out.",
                    expected,
                    len(translated_items),
                )
                return translated_items

            # Provide diagnostic info on mismatch
            logger.warning(
                "Item count mismatch (expected %d, got %d). "
                "Attempt %d/%d. "
                "(Response length: %d chars, %d frame(s), %d section(s) found)",
                expected,
                len(translated_items),
                attempt + 1,
                1 + max_retries,
                len(response),
                len(_FRAME_PATTERN.findall(response)),
                len(_SECTION_PATTERN.findall(response)),
            )
            
            # Strategy 3: Dynamic Batch Reduction
            # If we have retries left and batch size > 1, split the batch
            if attempt < max_retries and expected > 1:
                logger.info(
                    "Batch reduction: splitting %d item(s) in half for next attempt.",
                    expected,
                )
                mid = (expected + 1) // 2  # Ceiling division for uneven splits
                # Recursively translate split batches
                first_half = self.translate_batch(
                    items[:mid],
                    max_retries=max_retries - attempt - 1,
                )
                second_half = self.translate_batch(
                    items[mid:],
                    max_retries=max_retries - attempt - 1,
                )
                return first_half + second_half
            
            if attempt < max_retries:
                self._backoff(attempt)

        raise RuntimeError(
            f"Item count validation failed after {1 + max_retries} "
            f"attempt(s): expected {expected} item(s), got {len(translated_items)}. "
            f"Even after batch reduction, the API could not produce the expected number of items. "
            f"Try reducing batch size on the command line or checking the input LaTeX structure."
        )

    # ── Internal helpers ────────────────────────────────────────────────

    def _call_api(self, prompt: str) -> str:
        """Send *prompt* to Gemini and return the text response.

        Args:
            prompt: User prompt string.

        Returns:
            Raw text from the model response.
        """
        logger.debug("Sending prompt (%d chars) to %s.", len(prompt), self.model_name)
        response = self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
            ),
        )
        text = response.text
        logger.debug("Received response (%d chars).", len(text))
        return text

    def _validate_model(self) -> None:
        """Validate model name and provide helpful suggestions."""
        try:
            # Try to list available models
            available_models = self.list_available_models()
            if available_models and self.model_name not in available_models:
                logger.warning(
                    "Model '%s' not found in available models. "
                    "Available models: %s",
                    self.model_name,
                    ", ".join(available_models[:10]),
                )
        except Exception as exc:
            # If listing fails, just check against known models
            logger.debug("Could not list available models: %s", exc)
            if self.model_name not in RECOMMENDED_MODELS:
                logger.warning(
                    "Model '%s' is not in the list of recommended models. "
                    "Recommended: %s",
                    self.model_name,
                    ", ".join(RECOMMENDED_MODELS),
                )

    def list_available_models(self) -> List[str]:
        """List available Gemini models from the API.
        
        Returns:
            List of model names, or empty list if listing fails.
        """
        try:
            models = self._client.models.list()
            # Filter for generative models and extract names
            model_names = []
            for model in models:
                name = model.name
                # Remove 'models/' prefix if present
                if name.startswith('models/'):
                    name = name[7:]
                # Only include Gemini 2.5+ or 3.x models
                if 'gemini-2.5' in name.lower() or 'gemini-3' in name.lower():
                    model_names.append(name)
            return sorted(model_names)
        except Exception as exc:
            logger.debug("Failed to list models: %s", exc)
            return []

    @staticmethod
    def _backoff(attempt: int) -> None:
        """Sleep with exponential back-off."""
        delay = RETRY_BACKOFF_BASE * (2 ** attempt)
        logger.info("Backing off %.1f s before retry.", delay)
        time.sleep(delay)
