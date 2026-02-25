# Beamer Translate

A production-quality CLI tool for translating LaTeX Beamer slide decks from English to Chinese using the Google Gemini API.

## Features

- **LaTeX Structure Preservation**: Strictly preserves all LaTeX syntax, commands, math expressions, and formatting
- **Section/Subsection Translation**: Translates `\section` and `\subsection` titles outside frames
- **Comment Stripping**: Removes whole-line comments before API calls to reduce token usage and costs
- **Preamble Template Support**: Optionally replace the original preamble with a custom template
- **Intelligent Batching**: Groups content items to optimize API usage while respecting token limits
- **Robust Validation**: Ensures output count matches input with automatic retry
- **Progress Tracking**: Uses tqdm for visual progress feedback
- **Dry-run Mode**: Preview batching strategy without API calls

## Installation

The tool is part of the `xdufacool` package:

```bash
pixi install
# or for development
pip install -e .
```

## Prerequisites

1. **Google Gemini API Key**: Set the `GEMINI_API_KEY` environment variable:

   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   ```

2. **Dependencies**: 
   - `google-genai` (the new SDK, replacing deprecated `google-generativeai`)
   - `tqdm` for progress bars

## Usage

### Basic Command

```bash
beamer-translate slides.tex
```

This will:
- Read `slides.tex`
- Extract frames and section/subsection commands
- Strip whole-line comments from content
- Translate English text to Chinese
- Output to `slides-zh.tex`

### Options

```bash
beamer-translate INPUT [-o OUTPUT] [OPTIONS]
```

**Required Arguments:**
- `INPUT`: Path to input .tex file

**Optional Arguments:**
- `-o, --output PATH`: Output file path (default: `<input>-zh.tex`)
- `--template PATH`: Optional full-document template file to replace preamble/tail
- `--model NAME`: Gemini model name (default: `gemini-3-flash-preview`)
- `--batch-size N`: Max items per API request (default: 3)
- `--max-tokens N`: Soft token limit per batch (default: 20000)
- `--verbose`: Enable DEBUG logging
- `--dry-run`: Parse and batch without calling API

### Examples

**Basic translation:**
```bash
beamer-translate lecture-01.tex
```

**Use custom preamble template:**
```bash
beamer-translate lecture-01.tex --template custom-template.tex
```

**Specify output file:**
```bash
beamer-translate lecture-02.tex -o lecture-02-zh.tex
```

**Use smaller batches for complex slides:**
```bash
beamer-translate lecture-03.tex --batch-size 2
```

**Preview batching strategy:**
```bash
beamer-translate slides.tex --dry-run --verbose
```

**Use different model:**
```bash
beamer-translate slides.tex --model gemini-2.0-flash-exp
```

## How It Works

1. **Parsing**: Extracts preamble, content items (frames and sections), and document tail
2. **Comment Stripping**: Removes whole-line LaTeX comments from content items
3. **Batching**: Groups content items respecting `--batch-size` and `--max-tokens`
4. **Translation**: Sends batches to Gemini API with strict LaTeX preservation instructions
5. **Validation**: Verifies item count matches with automatic retry and batch reduction
6. **Reconstruction**: Reassembles document with translated content (and optional custom preamble)

### Robustness Strategies (v0.9.1+)

The tool implements three reliability strategies to handle API response variability:

1. **Count Injection**: Explicitly tells the model "I am providing you with exactly {X} items. You MUST return exactly {X} translated items." This dramatically improves compliance.

2. **Rigid Delimiters**: Each content item is prefixed with `% === FRAME_BOUNDARY_X ===` markers. The model is instructed never to alter these markers, allowing foolproof extraction via delimiter positions rather than regex patterns alone.

3. **Dynamic Batch Reduction**: If an initial batch fails item count validation, it is automatically split in half. Each half is recursively translated and results are merged. This handles cases where the model struggles with large batch sizes.
   - Example: 5-item batch fails → splits into 3 + 2 → individually translates each → combines results

These strategies work together to dramatically reduce the frequency of item count mismatches from API responses.

## Translation Rules

The system instruction ensures:

✅ **Translated:**
- Human-readable English text
- Section and subsection titles
- Slide titles and content
- Comments (inline comments are preserved, whole-line comments are stripped before API call)

❌ **Never Modified:**
- LaTeX commands themselves (`\begin`, `\end`, `\item`, `\section`, etc.)
- Math expressions (`$...$`, `\[...\]`, equations)
- Labels, refs, citations
- URLs and file paths
- Code blocks
- Document structure

## Architecture

```
xdufacool/beamer/
├── __init__.py
├── latex_parser.py      # Parse .tex into preamble/content_items/tail
│                        # Extract frames and section/subsection commands
│                        # Support preamble template loading
├── utils.py             # Batching, token estimation, comment stripping, I/O
├── gemini_client.py     # API client with retry & validation
└── README.md            # This file

xdufacool/beamer_translate.py  # CLI entry-point with preamble template support
tests/test_beamer_translate.py # Comprehensive test suite (30 tests)
```

## Testing

Run the test suite:

```bash
pixi run python -m pytest tests/test_beamer_translate.py -v
```

Tests cover:
- LaTeX parsing and reconstruction (frames + sections)
- Comment stripping functionality
- Section/subsection extraction
- Preamble template loading
- Batching algorithms
- CLI argument handling
- Dry-run mode
- End-to-end translation (with mocked API)

## Troubleshooting

**API Key Not Found:**
```
EnvironmentError: Gemini API key not found
```
→ Ensure `GEMINI_API_KEY` is set in your environment.

**Content Item Count Mismatch:**
```
RuntimeError: Item count validation failed after 3 attempt(s)
```
→ The API output didn't match expected item count. Try:
- Reducing `--batch-size`
- Using a more capable model
- Checking for complex LaTeX that confuses the model

**Preamble Template Not Found:**
```
FileNotFoundError: Preamble template not found: custom.tex
```
→ Verify the template file path is correct.

**Import Error:**
```
ImportError: cannot import name 'genai' from 'google'
```
→ Run `pixi install` to ensure `google-genai` is installed.

## Known Limitations

- Requires valid LaTeX input with well-formed `\begin{frame}...\end{frame}` blocks
- Only whole-line comments (lines starting with `%`) are stripped; inline comments are preserved
- Section/subsection commands must use standard syntax: `\section{...}`, `\subsection{...}`, `\section*{...}`
- Very complex nested environments may occasionally confuse the LLM
- Token estimation is approximate (assumes 4 chars/token)

## Recent Improvements (v0.9.0)

1. **Comment Stripping**: Whole-line LaTeX comments are now removed before API calls, reducing token usage and costs
2. **Section Translation**: `\section` and `\subsection` commands outside frames are now translated
3. **Document Templates**: Full-document templates can be loaded via `--template`
4. **Better Content Handling**: Parser now extracts both frames and structural commands in document order

## Migration from Deprecated SDK

This tool uses the new **`google-genai`** package, which replaces the deprecated `google-generativeai`. Key changes:

```python
# Old (deprecated)
import google.generativeai as genai
genai.configure(api_key=key)
model = genai.GenerativeModel(...)

# New (current)
from google import genai
client = genai.Client(api_key=key)
response = client.models.generate_content(...)
```

## License

Same as the parent `xdufacool` project.
