# B-roll Engine

Turn a voiceover or a written script into a finished, licence-clean B-roll
video, scene by scene: relevant footage for every line, timed to the narration,
with captions and a full record of where every clip came from and under what
licence.

> IncuBrix Engineering Assessment 3. Built phase by phase. This README records
> what is implemented now and what is planned. Honest status is kept in
> [REQUIREMENTS_TRACEABILITY.md](./REQUIREMENTS_TRACEABILITY.md).

## Current status

**Phase 3 - job system - is implemented and tested. Phases 1-2 (foundation) are also done.**

| Area | Status |
|---|---|
| Project scaffold + planning docs | done (Phase 1) |
| FastAPI app + env-driven config | done (Phase 2) |
| `/health` + `/ready` endpoints | done (Phase 2) |
| Structured JSON logging + correlation IDs | done (Phase 2) |
| Standard JSON error envelope | done (Phase 2) |
| OpenAPI 3.1 contract (`openapi.yaml`) | done (Phase 2) |
| Job system (queue, progress, idempotency, separate worker, restart recovery, HMAC callback) | done (Phase 3) |
| Provider adapters (STT/TTS/footage/embeddings) | planned (Phase 4) |
| Scene understanding + safety | planned (Phase 5) |
| FFmpeg video engine | planned (Phase 6) |
| Output metadata (timeline/manifest) | planned (Phase 7) |
| Frontend | planned (Phase 8) |
| Docker Compose + MinIO + batch runner + E2E tests | planned (Phase 9) |

## Architecture

Two services share one SQLite database and one storage volume. The API never
blocks on long work: it accepts jobs and the worker processes them in the
background. Every external AI capability sits behind a small adapter chosen by
configuration, each with a mock implementation so tests run with no API keys.

```
                  HTTP /api/v1
        +-----------------------------------+
        |                                   |
+-------v--------+   shared SQLite  +-------v--------+
|  api (FastAPI) |  <-------------> |  worker        |
| /health /ready |   shared volume  |  poll job queue|
| POST /broll/jobs|                 |  STT/TTS scenes |
| GET  /jobs/{id} |                 |  footage+safety |
| outputs download|                 |  FFmpeg render  |
+-------+--------+                  |  timeline/manifest
        |                           +-------+--------+
        |                                   |
        +-> MinIO (S3) <- stored outputs <---+
```

A more detailed architecture note is in [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md).

## Requirements

- Python 3.11+ (developed on 3.12)
- Node.js 18+ (frontend only, Phase 8)
- Docker + Docker Compose (Phase 9)
- FFmpeg / FFprobe - bundled in the Docker image (Phase 6); not required on the
  host for the current phase.

## Setup (under 10 commands)

Run from the project root.

```bash
# 1. Create a Python virtual environment
python -m venv .venv

# 2. Activate it (Windows PowerShell)
.venv\Scripts\Activate.ps1
#    (Windows cmd)  .venv\Scripts\activate.bat
#    (Linux/macOS)  source .venv/bin/activate

# 3. Install backend dependencies (runtime + test)
python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt

# 4. Copy the example env (defaults run with no API keys)
copy .env.example .env      # Windows
# cp .env.example .env       # Linux/macOS

# 5. Start the API in dev mode (from the backend folder)
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 6. In a second terminal, start the worker (from the backend folder)
#    The worker polls the jobs table and processes queued jobs.
cd backend
python -m app.workers.worker
```

Open http://localhost:8000/docs for the interactive API docs.

## Configuration

All settings come from environment variables (or a `.env` file). Every
variable is listed in [.env.example](./.env.example) with a safe default. No
secrets are hard-coded; provider credentials are optional and blank by
default. See `backend/app/config.py` for the authoritative list.

## Running the tests

```bash
# from the backend folder, with the venv active
cd backend
python -m pytest -q
```

The default suite uses mock providers only - no API keys are required. Tests
fail loudly if a real (paid) provider would be used in the test environment.

## Error codes

Errors are returned as JSON: `{"error": {"code", "message", "retryable", "details"}}`.
Codes are `UPPER_SNAKE_CASE`.

| Code | HTTP | Retryable | Meaning |
|---|---|---|---|
| `INVALID_INPUT` | 400 | no | Malformed or semantically invalid request, including schema validation failures. |
| `NOT_FOUND` | 404 | no | Requested resource does not exist. |
| `CONFLICT` | 409 | no | Idempotency / identity conflict. |
| `RATE_LIMITED` | 429 | yes | Too many requests in a window. |
| `UPSTREAM_PROVIDER_ERROR` | 502 | yes | A configured AI/footage provider failed; another provider is tried or the job retries. |
| `INTERNAL_ERROR` | 500 | no | Unexpected internal failure. |

## API surface

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET | `/health` | Liveness probe (app is up). | done |
| GET | `/ready` | Readiness probe (DB + storage reachable). | done |
| POST | `/api/v1/broll/jobs` | Create a job (script / audio URL / scenes); returns 202 + `job_id` + status URL; `Idempotency-Key` supported. | done (Phase 3) |
| GET | `/api/v1/jobs/{job_id}` | Job status + progress (0-100) + result/error. | done (Phase 3) |
| GET | `/api/v1/broll/jobs/{job_id}/timeline`, `/manifest`, `/outputs` | Outputs download. | planned (Phase 6/7) |
| GET | `/openapi.json` | Live OpenAPI 3.1 schema. | done |
| GET | `/docs` | Interactive API docs. | done |

The worker (`python -m app.workers.worker`, run from the `backend/` folder) polls
the jobs table and processes queued jobs. The current pipeline is an explicitly
labelled placeholder (see `app/workers/pipeline.py`); the real pipeline is
Phases 4-7.

## Batch runner

Planned (Phase 9): `python scripts/batch_runner.py <inputs_dir> <out_dir>`
submits a folder of test inputs, polls until done, and downloads all results
into one folder with a summary report.

## Troubleshooting

- **`ModuleNotFoundError: app`** when running tests - run pytest from the
  `backend/` folder (the `pytest.ini` adds `.` to the Python path).
- **Port 8000 in use** - set `API_PORT` in `.env` or pass `--port` to uvicorn.
- **Tests try to hit a real provider** - the test conftest forces all providers
  to `mock`; if you see a real call, check that `ENVIRONMENT` is `test`.

## Disclosure

- [SOURCES.md](./SOURCES.md) - every dependency, model, API, dataset and media
  source, with versions and licences.
- [AI_USE.md](./AI_USE.md) - every AI coding tool used and what it was used for.
