# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MoviePilot is a media automation platform (FastAPI + Vue3) for managing movie/TV show libraries. Based on NAStool, focused on automated media recognition, scraping, and transfer. Docker-deployed, typically on NAS devices.

## Build & Test Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run a single test
python -m pytest tests/test_mediascrape.py -v

# Run specific test class
python -m pytest tests/test_fanart_rate_limiter.py::TestFanartRateLimiter -v

# Verify config changes
python -c "from app.core.config import settings; print(settings.MY_SETTING)"

# Verify module imports
python -c "from app.modules.fanart import FanartModule; print('OK')"

# Build Docker image
docker build -f docker/Dockerfile -t moviepilot-v2:custom .

# Cython compile (for distribution)
python setup.py build_ext -j8 --inplace
```

Tests use `unittest` with `unittest.mock` (MagicMock, patch, AsyncMock). Test files mock heavy dependencies (`app.helper.sites`) before importing modules.

## Architecture

**Entry point:** `app/main.py` → uvicorn server → `app/factory.py` (FastAPI app with lifespan)

**Core systems:**

| Layer | Path | Purpose |
|---|---|---|
| API | `app/api/endpoints/` | REST endpoints (system, media, download, etc.) |
| Chain | `app/chain/` | Business logic singletons (MediaChain, TransferChain, SubscribeChain, etc.) |
| Modules | `app/modules/` | Pluggable modules (fanart, themoviedb, discord, jellyfin, etc.) |
| DB | `app/db/` | SQLAlchemy models + database operations |
| Schemas | `app/schemas/` | Pydantic models, enums (MediaType, ScrapingTarget, etc.) |
| Core | `app/core/` | Config (Pydantic BaseSettings), cache, context (MediaInfo) |
| Utils | `app/utils/` | HTTP clients (RequestUtils, AsyncRequestUtils), string helpers |
| Scheduler | `app/scheduler.py` | Background tasks |
| Events | `app/core/event.py` | Event-driven dispatch between chains and modules |

**Key pattern — Module dispatch (`run_module`):** Chains call `self.run_module("method_name", ...)` to invoke all registered modules implementing that method. Modules are sorted by priority (lower = first). If a module returns a non-None, non-list result, subsequent modules may be short-circuited. Both sync (`obtain_images`) and async (`async_obtain_images`) variants exist.

**Key pattern — Singleton chains:** MediaChain, TransferChain, etc. use `Singleton` metaclass. They watch config changes via `ConfigReloadMixin`.

## Media Scraping Flow

```
scrape_metadata(fileitem)
  ├── Phase 1: recognize_by_meta() → MetaInfo → MediaInfo (tmdb_id, type, etc.)
  ├── Phase 2: obtain_images() → fills mediainfo.backdrop_path/poster_path/logo_path
  │     Both FanartModule (pri 0) and TmdbModule (pri 1) run sequentially
  └── Phase 3: file output
        ├── _scrape_nfo_generic() → tvshow.nfo / season.nfo / {name}.nfo
        └── _scrape_images_generic() → metadata_img() → downloads images
              Fanart (pri 0) returns dict → short-circuits TMDB
              Fanart returns None → TMDB runs (requires SCRAP_SOURCE="themoviedb")
```

**Image sources (Fanart vs TMDB):** Fanart (priority 0) runs first in `metadata_img`. If it has results, TMDB never runs. Fanart produces `background.jpg`; TMDB produces `backdrop.jpg`. Fanart has banner/thumb/disc; TMDB doesn't. TMDB provides episode thumbnails; Fanart doesn't.

**Kodi compatibility:** `_kodi_alternative_path()` adds `fanart.jpg` (from backdrop) and `{ep}-thumb.jpg` independently from primary images.

**Scraping policies:** `SKIP` / `MISSINGONLY` (default) / `OVERWRITE`. Per-type config via `ScrapingConfig` from `SystemConfigKey.ScrapingSwitchs`.

## Configuration

`app/core/config.py` — `ConfigModel(BaseModel)` with `BaseSettings`-style fields. Settings can be overridden by env vars.

## Docker

Multi-stage build in `docker/Dockerfile`. Update mechanism in `docker/update.sh` checks `MOVIEPILOT_AUTO_UPDATE` env var. Backend repo configurable via `MOVIEPILOT_REPO` env var (default: `lilde90/MoviePilot`).

## This Fork

This is a fork of `jxxghp/MoviePilot` with custom modifications:
- `FANART_RATE_LIMIT` — rate limit fanart API calls (default 1/sec)
- Kodi-compatible image naming (`fanart.jpg`, `{ep}-thumb.jpg`)
- Custom Docker build workflow (`.github/workflows/custom-build.yml`)
- Custom auto-update target (`MOVIEPILOT_REPO` = `lilde90/MoviePilot`)
