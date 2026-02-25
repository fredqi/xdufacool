# Copilot Instructions for xdufacool

## Project Overview
`xdufacool` is a Python-based toolkit for faculty members at Xidian University to manage courses, assignments, and student submissions. It handles defining courses via configuration, creating assignment packages, collecting submissions (local or email), and generating reports.

## Architecture & Core Concepts
- **Configuration Driven**: The system state is defined primarily by YAML configuration files.
- **Object Model**: 
    - `Course` (root, manages teachers/students/groups) -> `StudentGroup`
    - `Assignment` (base class) -> `ReportAssignment`, `CodingAssignment`, `ChallengeAssignment`
    - `Submission` -> `ReportSubmission`, `CodingSubmission`
    - Defined in `xdufacool/models.py`.
- **Assignment Structure**: each assignment maps to directories:
    - `exercise/{alias}`: Source materials (templates, data).
    - `dist/`: Output packaged assignments.
    - `workspace_dir/assignments/{common_name}`: collected submissions.
- **Collectors**: `LocalSubmissionCollector` and `EmailSubmissionCollector` (in `xdufacool/collectors.py`).
- **Helpers**: `ScoreHelper` (statistics), `FormAutoma` (markdown forms), `DupCheck` (code similarity).
- **Beamer Translation**: `beamer_translate` CLI tool with modular architecture:
    - `latex_parser.py`: Extracts frames, sections, preamble from LaTeX Beamer files.
    - `gemini_client.py`: Google Gemini API integration with model validation, retry logic, comment stripping.
    - `utils.py`: Token estimation, batching, I/O helpers.
    - Supports preamble templates, section/subsection translation, cost-efficient comment removal.

## Developer Workflows

### Setup & Dependencies
- **Dependency Management**: Project uses **pixi** for conda/PyPI package management. Configuration in `pixi.toml`.
- **Installation**: 
  - With pixi (recommended): `pixi install` then `pixi run <command>`
  - Editable install: `pip install -e .[dev]` (uses `pyproject.toml` for build metadata)
- **Running Commands**: Use `pixi run <task>` (e.g., `pixi run beamer-translate -h`)
- **External Tools**: `pandoc`, `laor `pixi run pytest` (30 tests across all modules).
- **Ignoring Optional Tests**: `python3 -m pytest --ignore=tests/test_organize_bib.py --ignore=tests/test_zothelper.py`
- **Fixtures**: Tests use `setup_data` fixtures to instantiate valid object graphs (`Teacher` -> `Course` -> `Assignment` -> `Submission`).
- **Dummy Files**: When testing `CodingAssignment`, ensure `setup_data` creates dummy files (`env_template.yml`, `data.csv`) as the model validates their existence during init.
- **Beamer Tests**: `test_beamer_translate.py` covers comment stripping, section extraction, preamble templates, and API mocking
### Testing
- **Command**: `python3 -m pytest` (preferred over `pytest` directly).
- **Ignoring Optional Tests**: `python3 -m pytest --ignore=tests/test_organize_bib.py --ignore=tests/test_zothelper.py`
- **Fixtures**: Tests use `setup_data` fixtures to instantiate valid object graphs (`Teacher` -> `Course` -> `Assignment` -> `Submission`).
- **Dummy Files**: When testing `CodingAssignment`, ensure `setup_data` creates dummy files (`env_template.yml`, `data.csv`) as the model validates their existence during init.

### Implementation Details
- **Assignment Model**: Constructor requires `alias` (folder name in `exercise/`). 
  ```python
  Assignment(..., alias="HW1", ...)
  ```
- **ScoreStat**: Initialized with a single list of scores: `ScoreStat(["85", "90"])`.
- **Beamer Parser**: `BeamerDocument.content_items` returns mixed list of frames and sections in document order. Use `doc.frames` for backward compatibility (frames only).
- **Comment Stripping**: `strip_latex_comments()` removes whole-line LaTeX comments (lines starting with %) before API calls to reduce token usage.
- **Model Validation**: `GeminiTranslator` validates model names against API or hardcoded `RECOMMENDED_MODELS` list: `["gemini-3.1-pro-preview", "gemini-3-pro-preview", "gemini-3-flash-preview", "gemini-2.5-pro"]`.
- **Markdown Processing**: Uses `mistletoe`. Note: usage in `form_automa.py` may require specific handling for front matter.

## Key Conventions
- **Path Handling**: Use `pathlib.Path` exclusively. `validate_paths` in `utils.py` is used to check existence of config-referenced files relative to `exercise` folders.
- **Filenames**: Strict naming conventions (`StudentID-Name.ext`) are enforced for submission matching.
- **Logging**: Use `logging.info` for user-facing status, `logging.debug` for internals.
- **Docstrings**: Google style docstrings preferred.

- **Pixi vs PyPI**: `pixi.toml` manages all runtime/dev dependencies. `pyproject.toml` retained for build system config and pip editable installs only.
- **Gemini Model Names**: Always use actual API-validated model names with `-preview` suffix for Gemini 3.x models. Use `scripts/list_gemini_models.py` to query available models.
- **Beamer Backward Compatibility**: When refactoring beamer code, use `@property` pattern to maintain backward compatibility (e.g., `frames` property wrapping `content_items`).
## Gotchas
- **Mistletoe Compatibility**: Be aware of `mistletoe` version differences regarding `front_matter` parsing in `Document.read`.
- **Encoding**: Always specify `encoding='utf-8'` for file I/O, especially for Chinese text support.
- **Relative Paths**: `Course` and `Assignment` make heavy use of paths relative to `base_dir`. Ensure `base_dir` is correctly set in tests (use `tmp_path` fixture).
