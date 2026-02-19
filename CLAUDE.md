# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Photo pipeline for Fujifilm X-S20: Import → Cull (rate 1-5 via XMP) → Capture One processing → Google Photos upload. Two main modules: `photo_cull/` (photo culling/rating) and `photo_export/` (Google Photos uploader).

## Commands

```bash
# Activate venv (shared for both modules)
source .venv/bin/activate

# Install all dependencies
pip install -r photo_cull/requirements.txt -r photo_export/requirements.txt

# Run tests
python3 -m pytest photo_cull/tests/
python3 -m pytest photo_export/tests/
python3 -m pytest photo_cull/tests/test_rating.py                        # single module
python3 -m pytest photo_cull/tests/test_rating.py::TestApplyRating::test_hard_rule_5  # single test

# Run cull (algorithmic)
python3 photo_cull/cull.py ~/Pictures/Import/25-01_Event --dry-run

# Run cull (AI via Ollama llava)
python3 photo_cull/cull.py ~/Pictures/Import/25-01_Event --ai-cull --dry-run
python3 photo_cull/cull.py ~/Pictures/Import/25-01_Event --ai-cull --ollama-model llava:13b --dry-run

# Run uploader
python3 photo_export/google_photos_upload.py ~/Pictures/Export --dry-run
```

## Architecture

### photo_cull/ — Automated photo culling (analysis → rating → XMP)

- `cull.py` — CLI entry point, `process_folder()` orchestrates 8-step pipeline; `--ai-cull` flag switches to AI analysis
- `config.py` — constants, thresholds, `PhotoInfo` dataclass (flows through entire pipeline), AI weight constants
- `analyzer.py` — sharpness (Laplacian variance), brightness, exposure scoring, image loading (OpenCV + rawpy RAF)
- `ai_analyzer.py` — Ollama vision integration (llava): sends base64 images to `/api/chat`, parses JSON scores (sharpness, exposure, face_quality, composition)
- `faces.py` — MediaPipe FaceMesh, Eye Aspect Ratio for closed-eye detection
- `duplicates.py` — dHash perceptual hashing, Hamming distance, Union-Find grouping
- `series.py` — EXIF timestamp reading, burst detection (≤3s gap)
- `rating.py` — composite scoring (5/6 weighted components), `compute_composite_score_ai()` adds composition weight; hard rules (rating 1/5), soft rules (score → 2-4); `eyes_closed` hard rule skipped in AI mode (unreliable)
- `xmp.py` — XMP sidecar generation (`xml.etree`), Capture One compatible

### photo_export/ — Google Photos uploader (folder → album mapping)

- `google_photos_upload.py` — CLI entry point, `process_folder()` orchestrates upload pipeline
- `auth.py` — OAuth2 flow (credentials.json → token.json)
- `client.py` — `GooglePhotosClient`: album CRUD, file upload (two-step: upload token → batch add), pagination, token refresh
- `files.py` — media file discovery, EXIF reading, interactive duplicate prompts
- `config.py` — API constants, supported extensions (photo/RAW/video), limits
- `log.py` — `.gphotos_uploaded.json` persistence for idempotent uploads

### Key patterns

- Shared `.venv/` at project root for both modules
- `from __future__ import annotations` in all modules (Python 3.9 compat)
- `pathlib.Path` throughout, type hints on all functions
- All tests use pytest with `tmp_path` fixtures and mock patching at module import level
- Tests must be run separately per module (namespace isolation)
- Two-step upload: get upload token first, then batch-add to album (max 50 items/batch)
- Rate limiting: 2s sleep every 20 files, 1s between batches
- Graceful degradation: if library read forbidden (403), skip duplicate detection and cache albums locally
