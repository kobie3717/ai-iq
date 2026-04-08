# Changelog

All notable changes to AI-IQ will be documented in this file.

## [5.8.0] - 2026-04-08

### Added - Retrieval Improvements (MemPalace-inspired)

Three significant search enhancements inspired by MemPalace:

1. **Quoted phrase boosting** - Search queries with "quoted phrases" now receive a 1.5x score boost for exact matches. This ensures precise retrieval when you need specific terminology or phrases.

2. **Person name detection and boosting** - The search engine now detects capitalized person names in queries (e.g., "John Smith") and boosts results containing those names by 1.3x. This improves retrieval when searching for people-related memories.

3. **Metadata pre-filtering** - Project and tag filters are now applied BEFORE semantic/keyword search, not after. This reduces the search space and improves performance when filtering by `--project` or `--tags`.

### Changed

- `search_memories()` function now accepts `project` and `tags` parameters for pre-filtering
- CLI `memory-tool search` command now supports `--project X` and `--tags X` flags
- Search logic now extracts quoted phrases and person names for specialized boosting
- Updated help text to document new search flags

### Performance

- Metadata pre-filtering reduces vector search space when using project/tag filters
- Quoted phrase boosting provides more precise results for technical queries
- Person name boosting improves recall for people-related searches

## [5.7.0] - Previous Release

See git history for earlier versions.
