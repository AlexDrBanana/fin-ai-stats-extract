# Copilot Processing

## User Request

Restructure the project for PyPI and `uvx fin-ai-stats-extract` by moving code into `src/fin_ai_stats_extract`, renaming `fin-ai-extract` to `fin-ai-stats-extract`, moving prompts into package resources, adding `--prompt` prompt-file selection with current-directory fallback/copy behavior, and adding a GitHub Actions release workflow that publishes on tag push.

## Action Plan

- [x] Create failing tests for renamed package imports, CLI prompt resolution, and packaged prompt behavior.
- [x] Move Python modules into `src/fin_ai_stats_extract` and update imports, entry points, and labels.
- [x] Package `resources/system_prompt.md` and implement prompt-path resolution and default copy-to-CWD behavior.
- [x] Update packaging metadata and documentation for `fin-ai-stats-extract` and `uvx` usage.
- [x] Add a tag-triggered PyPI publish workflow using current GitHub Actions components.
- [x] Run unit tests and packaging build to verify the migration.

## Progress Tracking

- [x] Planning complete
- [x] Tests added
- [x] Package migration complete
- [x] Prompt logic complete
- [x] Packaging metadata complete
- [x] Release workflow complete
- [x] Verification complete

## Progress Log

### 2026-03-30

- Captured the requested repository rename, src-layout migration, prompt packaging requirements, and release automation work.
- Confirmed the current project still uses repo-root entry points and a non-packaged `prompts/system_prompt.md` file.
- Confirmed the target migration should be clean only, with no backward-compatibility wrappers.
- Rewrote the test imports first, added prompt-resolution tests, and confirmed the initial red state before implementing the package move.
- Moved the runtime into `src/fin_ai_stats_extract`, packaged `resources/system_prompt.md`, and updated package-local imports.
- Added `--prompt`, current-directory prompt bootstrapping, a tag-based PyPI release workflow, and refreshed package metadata and docs for `uvx fin-ai-stats-extract`.
- Verified the migration with `uv run python3 -m unittest discover -s tests -v`, `uv lock`, and `uv build`.

## Summary

- The project now builds as the `fin-ai-stats-extract` distribution with code located under `src/fin_ai_stats_extract`.
- The CLI now supports `--prompt` and automatically creates `./system_prompt.md` from the packaged default when no prompt file is provided.
- The repository includes a tag-triggered GitHub Actions workflow that builds and publishes to PyPI using current action versions and trusted publishing.
