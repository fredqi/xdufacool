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

## Developer Workflows

### Setup & Dependencies
- **Installation**: `pip install -e .[dev]`
- **External Tools**: `pandoc`, `latex` (TeXLive/MikTeX) are critical.
- **Optional Deps**: `bibtexparser`, `pyzotero` are optional; tests relying on them are skipped if missing.

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
- **Markdown Processing**: Uses `mistletoe`. Note: usage in `form_automa.py` may require specific handling for front matter.

## Key Conventions
- **Path Handling**: Use `pathlib.Path` exclusively. `validate_paths` in `utils.py` is used to check existence of config-referenced files relative to `exercise` folders.
- **Filenames**: Strict naming conventions (`StudentID-Name.ext`) are enforced for submission matching.
- **Logging**: Use `logging.info` for user-facing status, `logging.debug` for internals.
- **Docstrings**: Google style docstrings preferred.

## Gotchas
- **Mistletoe Compatibility**: Be aware of `mistletoe` version differences regarding `front_matter` parsing in `Document.read`.
- **Encoding**: Always specify `encoding='utf-8'` for file I/O, especially for Chinese text support.
- **Relative Paths**: `Course` and `Assignment` make heavy use of paths relative to `base_dir`. Ensure `base_dir` is correctly set in tests (use `tmp_path` fixture).
