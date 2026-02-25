"""Tests for the beamer-translate pipeline (parser, utils, CLI)."""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from xdufacool.beamer.latex_parser import (
    BeamerDocument,
    parse_beamer_tex,
    read_and_parse,
    reconstruct,
    load_preamble_template,
)
from xdufacool.beamer.utils import batch_frames, default_output_path, estimate_tokens, strip_latex_comments


# ── Fixtures ────────────────────────────────────────────────────────────────

SAMPLE_TEX = textwrap.dedent(r"""
\documentclass{beamer}
\usepackage{amsmath}
\title{Machine Learning}
\begin{document}
\maketitle

\begin{frame}{Introduction}
  Machine learning is a branch of AI.
  \begin{itemize}
    \item Supervised learning
    \item Unsupervised learning
  \end{itemize}
\end{frame}

\begin{frame}{Gradient Descent}
  Minimize the loss function $L(\theta)$ using:
  \[
    \theta_{t+1} = \theta_t - \eta \nabla L(\theta_t)
  \]
\end{frame}

\begin{frame}{Summary}
  Key takeaways from this lecture.
\end{frame}

\end{document}
""").lstrip()


@pytest.fixture
def sample_tex_file(tmp_path: Path) -> Path:
    """Write the sample TeX to a temporary file and return its path."""
    p = tmp_path / "slides.tex"
    p.write_text(SAMPLE_TEX, encoding="utf-8")
    return p


# ── latex_parser tests ──────────────────────────────────────────────────────


class TestParseBeamerTex:
    """Tests for ``parse_beamer_tex``."""

    def test_extracts_correct_frame_count(self) -> None:
        doc = parse_beamer_tex(SAMPLE_TEX)
        assert len(doc.frames) == 3

    def test_preamble_contains_documentclass(self) -> None:
        doc = parse_beamer_tex(SAMPLE_TEX)
        assert r"\documentclass{beamer}" in doc.preamble

    def test_preamble_does_not_contain_frames(self) -> None:
        doc = parse_beamer_tex(SAMPLE_TEX)
        assert r"\begin{frame}" not in doc.preamble

    def test_tail_contains_end_document(self) -> None:
        doc = parse_beamer_tex(SAMPLE_TEX)
        assert r"\end{document}" in doc.tail

    def test_tail_does_not_contain_frames(self) -> None:
        doc = parse_beamer_tex(SAMPLE_TEX)
        assert r"\begin{frame}" not in doc.tail

    def test_each_frame_has_boundaries(self) -> None:
        doc = parse_beamer_tex(SAMPLE_TEX)
        for frame in doc.frames:
            assert frame.startswith(r"\begin{frame}")
            assert frame.endswith(r"\end{frame}")

    def test_raises_on_no_frames(self) -> None:
        with pytest.raises(ValueError, match="No .* blocks found"):
            parse_beamer_tex(r"\documentclass{article}\begin{document}\end{document}")


class TestReadAndParse:
    """Tests for ``read_and_parse``."""

    def test_reads_file_successfully(self, sample_tex_file: Path) -> None:
        doc = read_and_parse(sample_tex_file)
        assert len(doc.frames) == 3
        assert doc.source_path == sample_tex_file

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            read_and_parse(tmp_path / "nonexistent.tex")


class TestReconstruct:
    """Tests for ``reconstruct``."""

    def test_roundtrip_identity(self) -> None:
        doc = parse_beamer_tex(SAMPLE_TEX)
        rebuilt = reconstruct(doc, doc.frames)
        # The reconstructed text should contain all original frames and structure.
        assert r"\documentclass{beamer}" in rebuilt
        assert r"\end{document}" in rebuilt
        assert rebuilt.count(r"\begin{frame}") == 3

    def test_raises_on_count_mismatch(self) -> None:
        doc = parse_beamer_tex(SAMPLE_TEX)
        with pytest.raises(ValueError, match="Content item count mismatch"):
            reconstruct(doc, doc.frames[:2])


# ── utils tests ─────────────────────────────────────────────────────────────


class TestEstimateTokens:
    def test_empty_string(self) -> None:
        assert estimate_tokens("") == 0

    def test_known_length(self) -> None:
        # 100 chars → ceil(100/4) = 25 tokens
        assert estimate_tokens("a" * 100) == 25


class TestBatchFrames:
    def test_single_batch(self) -> None:
        frames = ["f1", "f2", "f3"]
        batches = batch_frames(frames, batch_size=5)
        assert len(batches) == 1
        assert batches[0] == frames

    def test_splits_by_batch_size(self) -> None:
        frames = [f"frame{i}" for i in range(7)]
        batches = batch_frames(frames, batch_size=3)
        assert len(batches) == 3
        assert len(batches[0]) == 3
        assert len(batches[1]) == 3
        assert len(batches[2]) == 1

    def test_splits_by_token_limit(self) -> None:
        # Each frame ~100 chars → 25 tokens.  max_tokens=30 → 1 frame/batch.
        frames = ["x" * 100 for _ in range(3)]
        batches = batch_frames(frames, batch_size=10, max_tokens=30)
        assert len(batches) == 3

    def test_empty_input(self) -> None:
        assert batch_frames([]) == []


class TestDefaultOutputPath:
    def test_adds_zh_suffix(self) -> None:
        assert default_output_path(Path("slides.tex")) == Path("slides-zh.tex")

    def test_handles_compound_suffix(self) -> None:
        assert default_output_path(Path("dir/a.b.tex")) == Path("dir/a.b-zh.tex")


# ── CLI / beamer_translate tests ────────────────────────────────────────────


class TestCLIDryRun:
    """Test the CLI in --dry-run mode (no API calls)."""

    def test_dry_run_returns_zero(self, sample_tex_file: Path) -> None:
        from xdufacool.beamer_translate import main

        rc = main([str(sample_tex_file), "--dry-run"])
        assert rc == 0

    def test_dry_run_does_not_create_output(
        self, sample_tex_file: Path, tmp_path: Path
    ) -> None:
        from xdufacool.beamer_translate import main

        out = tmp_path / "out.zh.tex"
        rc = main([str(sample_tex_file), "-o", str(out), "--dry-run"])
        assert rc == 0
        assert not out.exists()


class TestCLIMissingFile:
    def test_returns_nonzero_for_missing_input(self) -> None:
        from xdufacool.beamer_translate import main

        rc = main(["/tmp/does_not_exist_12345.tex"])
        assert rc == 1


class TestCLITranslation:
    """End-to-end test with a mocked Gemini translator."""

    def test_full_pipeline_with_mock(
        self, sample_tex_file: Path, tmp_path: Path
    ) -> None:
        from xdufacool.beamer_translate import main

        out = tmp_path / "result.zh.tex"

        # Build fake translated frames (just prefix each with '翻译:')
        doc = parse_beamer_tex(SAMPLE_TEX)
        fake_translated = [f.replace("Introduction", "简介") for f in doc.frames]

        mock_translator = MagicMock()
        # translate_batch will be called once per batch; wire up return values
        mock_translator.translate_batch.side_effect = lambda batch, **kw: [
            fake_translated[doc.frames.index(f)] for f in batch
        ]

        with patch(
            "xdufacool.beamer_translate.GeminiTranslator",
            return_value=mock_translator,
        ):
            rc = main(
                [str(sample_tex_file), "-o", str(out), "--batch-size", "10"]
            )

        assert rc == 0
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert r"\documentclass{beamer}" in content
        assert r"\end{document}" in content
        assert "简介" in content


# ── Tests for new features ──────────────────────────────────────────────────


class TestStripLatexComments:
    """Tests for comment stripping functionality."""

    def test_strips_whole_line_comments(self) -> None:
        text = "Line 1\n% This is a comment\nLine 2"
        result = strip_latex_comments(text)
        assert "% This is a comment" not in result
        assert "Line 1" in result
        assert "Line 2" in result

    def test_preserves_inline_comments(self) -> None:
        text = "Some text % inline comment"
        result = strip_latex_comments(text)
        # Inline comments are preserved (only whole-line comments are stripped)
        assert "Some text % inline comment" in result

    def test_preserves_empty_lines(self) -> None:
        text = "Line 1\n\nLine 2"
        result = strip_latex_comments(text)
        assert result == text


class TestSectionExtraction:
    """Tests for section/subsection extraction."""

    def test_extracts_sections_and_frames(self) -> None:
        tex_with_sections = textwrap.dedent(r"""
        \documentclass{beamer}
        \begin{document}
        
        \section{Introduction}
        
        \begin{frame}{First}
          Content
        \end{frame}
        
        \subsection{Details}
        
        \begin{frame}{Second}
          More content
        \end{frame}
        
        \end{document}
        """).lstrip()
        
        doc = parse_beamer_tex(tex_with_sections)
        # Should have 2 frames + 2 section commands = 4 content items
        assert len(doc.content_items) == 4
        assert len(doc.frames) == 2  # Only frames via the property
        
        # Check that sections are included
        sections = [item for item in doc.content_items if 'section' in item and not item.startswith(r'\begin{frame}')]
        assert len(sections) == 2


class TestPreambleTemplate:
    """Tests for preamble template loading."""

    def test_loads_preamble_from_file(self, tmp_path: Path) -> None:
        template = tmp_path / "preamble.tex"
        template.write_text(r"\documentclass{beamer}" + "\n" + r"\usepackage{custom}", encoding="utf-8")
        
        loaded = load_preamble_template(template)
        assert r"\documentclass{beamer}" in loaded
        assert r"\usepackage{custom}" in loaded

    def test_raises_on_missing_template(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_preamble_template(tmp_path / "nonexistent.tex")

    def test_reconstruct_with_preamble_override(self) -> None:
        doc = parse_beamer_tex(SAMPLE_TEX)
        custom_preamble = r"\documentclass{article}" + "\n"
        
        result = reconstruct(doc, doc.content_items, preamble_override=custom_preamble)
        assert r"\documentclass{article}" in result
        assert r"\documentclass{beamer}" not in result
        assert r"\end{document}" in result
