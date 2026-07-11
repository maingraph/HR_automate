# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-05-09

### Added
- Split parser.ts into 8 focused modules for better maintainability
- Centralized selectors in `selectors.ts` for easier maintenance
- Text utilities module (`text-utils.ts`) for reusable text manipulation
- Proper directory structure: `core/`, `extractors/`, `utils/`, `storage/`
- Path aliases in tsconfig.json for cleaner imports
- `.opencode-rules` file for AI assistant guidelines
- `.gitattributes` for consistent line endings
- Enhanced `.gitignore` for better file exclusion

### Changed
- Reorganized files into logical directories
- Moved test files to `scripts/` directory
- Updated all import paths to reflect new structure
- Updated package.json scripts for new entry point
- Parser.ts now acts as an orchestrator (~200 lines) instead of monolithic file (1,381 lines)

### Fixed
- Race condition with sidebar verification (implemented in previous version)
- Missing LinkedIn URLs with retry logic (implemented in previous version)

### Breaking Changes
- File structure completely reorganized
- Main entry point changed from `dist/index.js` to `dist/core/index.js`
- All import paths updated to new directory structure

## [1.0.0] - 2026-05-08

### Added
- Search-based duplicate tracking to handle dynamic LinkedIn results
- `--no-dedup` flag to disable duplicate detection
- `--fresh` flag to start fresh (ignore previous tracking data)
- Name+company fallback identifier when LinkedIn URL is missing
- Retry logic for LinkedIn URL extraction (up to 3 attempts)
- Sidebar verification to prevent race conditions
- Fuzzy matching for name/company verification

### Fixed
- Empty URL duplicate matching bug
- Cross-search duplicate detection issues
- Race condition where sidebar didn't update before data extraction
- Profile data extraction from wrong profile due to timing issues

### Changed
- Duplicate tracking now uses search URL hash for isolation
- Improved sidebar update detection with fuzzy matching
- Enhanced error messages for debugging

## [0.9.0] - 2026-05-06

### Added
- Initial release of LinkedIn Sales Navigator parser
- Profile data extraction from search results
- CSV export functionality
- Anti-detection features (stealth mode, random delays)
- Rate limiting to avoid detection
- Checkpoint system for resuming interrupted sessions
- Chrome profile detection and usage
- Comprehensive logging system
- Desktop notifications on completion

### Features
- Extract profile data: name, headline, company, location, etc.
- Extract detailed sections: experience, education, skills, languages
- Handle pagination automatically
- Duplicate detection within session
- Configurable delays and limits
- Resume capability with `--resume` flag
- Test mode with `--test` flag

## Version History Summary

- **v1.1.0** (2026-05-09): Major refactoring - split monolithic parser into focused modules
- **v1.0.0** (2026-05-08): Stable release with race condition fix and duplicate tracking
- **v0.9.0** (2026-05-06): Initial release with core functionality
