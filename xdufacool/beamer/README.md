# Beamer Translate

A production-quality CLI tool for translating LaTeX Beamer slide decks from English to Chinese using the Google Gemini API.

## Features

- **LaTeX Structure Preservation**: Strictly preserves all LaTeX syntax, commands, math expressions, and formatting
- **Intelligent Batching**: Groups frames to optimize API usage while respecting token limits
- **Robust Validation**: Ensures output frame count matches input with automatic retry
- **Progress Tracking**: Uses tqdm for visual progress feedback
- **Dry-run Mode**: Preview batching strategy without API calls

## Installation

The tool is part of the `xdufacool` package:

```bash
uv sync
# or
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
- Translate English text to Chinese
- Output to `slides.zh.tex`

### Options

```bash
beamer-translate INPUT [-o OUTPUT] [OPTIONS]
```

**Required Arguments:**
- `INPUT`: Path to input .tex file

**Optional Arguments:**
- `-o, --output PATH`: Output file path (default: `<input>.zh.tex`)
- `--model NAME`: Gemini model name (default: `gemini-2.5-pro`)
- `--batch-size N`: Max frames per API request (default: 3)
- `--max-tokens N`: Soft token limit per batch (default: 20000)
- `--verbose`: Enable DEBUG logging
- `--dry-run`: Parse and batch without calling API

### Examples

**Specify output file:**
```bash
beamer-translate lecture-01.tex -o lecture-01-zh.tex
```

**Use smaller batches for complex slides:**
```bash
beamer-translate lecture-02.tex --batch-size 2
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

1. **Parsing**: Extracts preamble, frame blocks, and document tail
2. **Batching**: Groups frames respecting `--batch-size` and `--max-tokens`
3. **Translation**: Sends batches to Gemini API with strict LaTeX preservation instructions
4. **Validation**: Verifies frame count matches (retries up to 2 times on mismatch)
5. **Reconstruction**: Reassembles document with translated frames

## Translation Rules

The system instruction ensures:

✅ **Translated:**
- Human-readable English text
- Comments and explanations
- Slide titles and content

❌ **Never Modified:**
- LaTeX commands (`\begin`, `\end`, `\item`, etc.)
- Math expressions (`$...$`, `\[...\]`, equations)
- Labels, refs, citations
- URLs and file paths
- Code blocks
- Document structure

## Architecture

```
xdufacool/beamer/
├── __init__.py
├── latex_parser.py      # Parse .tex into preamble/frames/tail
├── utils.py             # Batching, token estimation, I/O
├── gemini_client.py     # API client with retry & validation
└── README.md            # This file

xdufacool/beamer_translate.py  # CLI entry-point
tests/test_beamer_translate.py # Comprehensive test suite
```

## Testing

Run the test suite:

```bash
uv run pytest tests/test_beamer_translate.py -v
```

Tests cover:
- LaTeX parsing and reconstruction
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

**Frame Count Mismatch:**
```
RuntimeError: Frame count validation failed after 3 attempt(s)
```
→ The API output didn't match expected frame count. Try:
- Reducing `--batch-size`
- Using a more capable model
- Checking for complex LaTeX that confuses the model

**Import Error:**
```
ImportError: cannot import name 'genai' from 'google'
```
→ Run `uv sync` to ensure `google-genai` is installed.

## Known Limitations

- Requires valid LaTeX input with well-formed `\begin{frame}...\end{frame}` blocks
- Very complex nested environments may occasionally confuse the LLM
- Token estimation is approximate (assumes 4 chars/token)

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
