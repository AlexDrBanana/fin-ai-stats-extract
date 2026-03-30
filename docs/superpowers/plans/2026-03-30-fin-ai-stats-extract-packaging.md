# Fin AI Stats Extract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the project into a clean installable package that users can run as `uvx fin-ai-stats-extract`, with packaged prompt resources and tag-based PyPI publishing.

**Architecture:** Move all runtime code into the `fin_ai_stats_extract` package under `src/`, make the CLI entry point package-native, and treat the default system prompt as packaged data rather than a repo-root file. Add prompt resolution utilities that support an explicit prompt path and current-directory prompt bootstrapping.

**Tech Stack:** Python 3.14, setuptools via `pyproject.toml`, unittest, GitHub Actions, PyPI trusted publishing.

---

## Task 1: Add Failing Tests For New Package Paths And Prompt Resolution

**Files:**

- Modify: `tests/test_main_cli.py`
- Modify: `tests/test_extractor.py`
- Modify: `tests/test_cost.py`
- Create: `tests/test_prompts.py`

- [ ] **Step 1: Write the failing tests**

```python
from fin_ai_stats_extract.cli import build_parser
from fin_ai_stats_extract.prompts import ensure_default_prompt_file, load_prompt_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python3 -m unittest discover -s tests -v`
Expected: import failures for `fin_ai_stats_extract` and missing prompt helpers.

- [ ] **Step 3: Implement minimal package imports and prompt helpers**

Create package modules and prompt utility functions so the new imports resolve.

- [ ] **Step 4: Run tests to verify the new tests pass**

Run: `uv run python3 -m unittest discover -s tests -v`
Expected: package import and prompt tests pass, with remaining failures only from unfinished migration work.

## Task 2: Migrate Runtime Code Into The Package

**Files:**

- Create: `src/fin_ai_stats_extract/__init__.py`
- Create: `src/fin_ai_stats_extract/cli.py`
- Create: `src/fin_ai_stats_extract/streamlit_app.py`
- Create: `src/fin_ai_stats_extract/cost.py`
- Create: `src/fin_ai_stats_extract/extractor.py`
- Create: `src/fin_ai_stats_extract/openai_utils.py`
- Create: `src/fin_ai_stats_extract/parser.py`
- Create: `src/fin_ai_stats_extract/pipeline.py`
- Create: `src/fin_ai_stats_extract/prompts.py`
- Create: `src/fin_ai_stats_extract/schema.py`
- Create: `src/fin_ai_stats_extract/writer.py`
- Delete: `main.py`
- Delete: `streamlit_app.py`
- Delete: `src/*.py`

- [ ] **Step 1: Copy modules into the new package path with package-local imports**
- [ ] **Step 2: Move CLI code into `cli.py` and Streamlit app into package module**
- [ ] **Step 3: Delete obsolete repo-root and old `src/` modules**
- [ ] **Step 4: Run tests to verify imports and runtime wiring are intact**

## Task 3: Package The Default Prompt And Add Runtime Prompt Selection

**Files:**

- Create: `src/fin_ai_stats_extract/resources/system_prompt.md`
- Modify: `src/fin_ai_stats_extract/prompts.py`
- Modify: `src/fin_ai_stats_extract/cli.py`
- Modify: `src/fin_ai_stats_extract/pipeline.py`

- [ ] **Step 1: Add the packaged default prompt resource**
- [ ] **Step 2: Add `--prompt` to the CLI parser**
- [ ] **Step 3: Implement runtime behavior**

```text
If --prompt PATH is provided: use PATH.
Else if ./system_prompt.md exists: use it.
Else copy packaged default to ./system_prompt.md, then use it.
```

- [ ] **Step 4: Thread the resolved prompt text into cost estimation and extraction**
- [ ] **Step 5: Re-run tests to verify prompt-file behavior**

## Task 4: Update Packaging Metadata And Docs

**Files:**

- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `uv.lock` (via lock refresh if needed)

- [ ] **Step 1: Rename the distribution to `fin-ai-stats-extract`**
- [ ] **Step 2: Set package discovery to `src` layout and include packaged markdown resources**
- [ ] **Step 3: Point console scripts at `fin_ai_stats_extract.cli:main`**
- [ ] **Step 4: Update README usage examples to `uvx fin-ai-stats-extract` and the new prompt location**

## Task 5: Add Tag-Based PyPI Publishing

**Files:**

- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Build on tag push using current stable action versions**
- [ ] **Step 2: Publish distributions to PyPI using trusted publishing**
- [ ] **Step 3: Keep the workflow minimal and deterministic**

## Task 6: Verify The Migration End To End

**Files:**

- Test: `tests/`
- Test: `pyproject.toml`

- [ ] **Step 1: Run unit tests**

Run: `uv run python3 -m unittest discover -s tests -v`
Expected: all tests pass.

- [ ] **Step 2: Build the package**

Run: `uv build`
Expected: wheel and sdist created successfully under `dist/`.

- [ ] **Step 3: Confirm final CLI entry point metadata**

Run: `uv run python -c "import importlib.metadata as m; print(m.metadata('fin-ai-stats-extract')['Name'])"`
Expected: `fin-ai-stats-extract` after installation context, or verify from built metadata if not installed.
