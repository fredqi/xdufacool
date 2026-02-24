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

from .latex_parser import _FRAME_PATTERN

logger = logging.getLogger(__name__)

# ── System instruction (verbatim per spec) ──────────────────────────────────

SYSTEM_INSTRUCTION = (
    "You are a professional LaTeX Beamer translator for machine learning "
    "course slides.\n\n"
    "Your task is to translate English text into Chinese while preserving "
    "LaTeX structure exactly.\n\n"
    "STRICT RULES:\n"
    "1. DO NOT modify any LaTeX commands, environments, or syntax.\n"
    "2. DO NOT translate:\n"
    "   * commands (e.g., \\begin, \\end, \\item)\n"
    "   * math expressions ($...$, \\[...\\], equation, align, etc.)\n"
    "   * labels, refs, citations, URLs, file paths\n"
    "3. ONLY translate human-readable English text.\n"
    "4. Preserve:\n"
    "   * frame boundaries\n"
    "   * line breaks\n"
    "   * indentation\n"
    "5. DO NOT add or remove any content.\n"
    "6. DO NOT output explanations or markdown.\n"
    "7. Output must compile as valid LaTeX.\n"
    "8. If uncertain, leave the text unchanged."
)

# ── Defaults ────────────────────────────────────────────────────────────────

DEFAULT_MODEL = "gemini-2.5-pro"
MAX_RETRIES = 2
RETRY_BACKOFF_BASE = 2.0  # seconds


# ── Helpers ─────────────────────────────────────────────────────────────────

def _build_user_prompt(frames: List[str]) -> str:
    """Compose the user message for a single batch of frames.

    Args:
        frames: List of LaTeX frame strings.

    Returns:
        Formatted user prompt.
    """
    joined = "\n\n".join(frames)
    return (
        "Translate the following LaTeX Beamer frames into Chinese:\n\n"
        "<FRAMES>\n"
        f"{joined}\n"
        "</FRAMES>"
    )


def _count_frames_in_text(text: str) -> int:
    r"""Count occurrences of ``\begin{frame}`` in *text*."""
    return len(_FRAME_PATTERN.findall(text))


def _extract_frames_from_response(text: str) -> List[str]:
    r"""Extract frame blocks from an API response string."""
    return _FRAME_PATTERN.findall(text)


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
    ) -> None:
        self.model_name = model_name
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self._api_key:
            raise EnvironmentError(
                "Gemini API key not found. Set the GEMINI_API_KEY "
                "environment variable or pass api_key explicitly."
            )
        self._client = genai.Client(api_key=self._api_key)
        logger.info("GeminiTranslator initialised (model=%s).", self.model_name)

    # ── Core translation method ─────────────────────────────────────────

    def translate_batch(
        self,
        frames: List[str],
        *,
        max_retries: int = MAX_RETRIES,
    ) -> List[str]:
        """Translate a batch of frames, with retry & validation.

        Args:
            frames: LaTeX frame strings to translate.
            max_retries: Number of retry attempts on frame-count mismatch.

        Returns:
            List of translated frame strings (same length as *frames*).

        Raises:
            RuntimeError: If validation fails after all retries.
        """
        expected = len(frames)
        prompt = _build_user_prompt(frames)

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

            translated_frames = _extract_frames_from_response(response)
            if len(translated_frames) == expected:
                logger.debug(
                    "Batch validated: %d frame(s) in / %d out.",
                    expected,
                    len(translated_frames),
                )
                return translated_frames

            logger.warning(
                "Frame count mismatch (expected %d, got %d). "
                "Retry %d/%d.",
                expected,
                len(translated_frames),
                attempt + 1,
                max_retries,
            )
            if attempt < max_retries:
                self._backoff(attempt)

        raise RuntimeError(
            f"Frame count validation failed after {1 + max_retries} "
            f"attempt(s): expected {expected} frame(s)."
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

    @staticmethod
    def _backoff(attempt: int) -> None:
        """Sleep with exponential back-off."""
        delay = RETRY_BACKOFF_BASE * (2 ** attempt)
        logger.info("Backing off %.1f s before retry.", delay)
        time.sleep(delay)
