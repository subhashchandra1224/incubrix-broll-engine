# Requirements Traceability

This file maps every assignment requirement to where it is implemented, how it
is tested, and where the evidence lives. It is kept honest: items not yet done
are marked **PLANNED**, never "done".

The structure mirrors the IncuBrix Submission Form tabs so the form can be
filled directly from this file.

Legend: **DONE** = implemented and tested in the current phase. **PLANNED** =
not yet built. **PARTIAL** = started but incomplete.

---

## Must-haves (Submission Form tab: `2_Must_haves`)

Every must-have is pass/fail; all eight must pass.

| # | Requirement (from brief) | Implementation modules | API endpoints | Tests | Evidence | Status |
|---|---|---|---|---|---|---|
| 1 | Both inputs work: audio (mp3/wav/m4a, up to 10 min) and text (TTS narration). Also optional scene list. | `audio_service`, `tts_service`, `schemas` (job request), `api/routes/jobs` | `POST /api/v1/broll/jobs` | `tests/test_input_validation.py` (empty script, bad type, silent, >10 min, music-only) | `test_results/input_validation/` | PLANNED (Phase 3/5) |
| 2 | Scenes by meaning, timed to the voice; every second covered; narration sets timing, not clips. | `transcription_service`, `tts_service` (word timings), `scene_service`, `timeline_service` | job-internal | `tests/test_segmentation.py`, `tests/test_timing_coverage.py` | `timeline.json` per job | PLANNED (Phase 5) |
| 3 | Every clip licence-clean: source, licence, attribution, link recorded; commercial use; no watermarks; AI-generated flagged. | `footage_service`, `providers/footage/*`, `manifest_service` | `GET .../manifest`, `.../timeline` | `tests/test_footage_licence.py` | `manifest.json`, clip blocks in `timeline.json` | PLANNED (Phase 4/7) |
| 4 | Correct, consistent video: all requested aspect ratios; normalised resolution/fps/pixel format; no black/frozen frames or audio drift. | `rendering_service`, `utils/ffmpeg` | `GET .../outputs/{filename}` | `tests/test_rendering.py` (FFprobe checks) | `video_*.mp4` + ffprobe reports | PLANNED (Phase 6) |
| 5 | No repeats and no nonsense matches: no clip twice; footage matches meaning, not keywords; relevance score + reason. | `footage_service` scoring, `semantic_service` | job-internal | `tests/test_relevance.py`, `tests/test_no_duplicates.py`, `tests/test_ambiguous_words.py` (value/bank/cloud/mouse/python) | `timeline.json` score+reason | PLANNED (Phase 4/5) |
| 6 | Safe output: no AI realistic faces of real people; no invented brand logos; respectful footage for sensitive topics. | `safety_service` | job-internal | `tests/test_safety.py` (people, brands, sad news, avoid terms) | manifest + timeline warnings | PLANNED (Phase 5) |
| 7 | Resilient jobs: background, progress; if a footage source fails the job still finishes via another source/fallback. | `job_service`, `workers/*`, provider fallback | `POST/GET /api/v1/jobs/{id}` | `tests/test_provider_fallback.py`, `tests/test_concurrent_jobs.py`, `tests/test_retryable_errors.py` | job logs + status transitions | PLANNED (Phase 3/4) |
| 8 | Integration Standard followed and the live demo works for the review period. | `docker-compose.yml`, frontend, `openapi.yaml`, `scripts/batch_runner.py` | all routes | `tests/test_e2e_script.py`, `tests/test_e2e_audio.py` | `docker compose up` + demo | PLANNED (Phase 8/9) |

---

## Integration Standard (Submission Form tab: `4_Integration`) - 2 marks each

| # | Requirement | Implementation | Tests / Evidence | Status |
|---|---|---|---|---|
| 1 | One-command start and test; `.env.example` lists every setting. | `docker-compose.yml`, `Makefile`/scripts, `pytest`, `.env.example` | `docker compose up`; one test command; `.env.example` | PLANNED (Phase 9); `.env.example` DONE (Phase 1) |
| 2 | Documented HTTP API: `openapi.yaml` (3.1) matching the running service; routes under `/api/v1/`. | FastAPI OpenAPI metadata, `scripts/export_openapi.py` | `tests/test_openapi.py` (committed file == live schema) | DONE (Phase 2) for current surface; expands as routes are added |
| 3 | Background jobs: >2s work is a job; POST returns 202 + `job_id`; `GET /api/v1/jobs/{id}` returns status/progress/result links; optional callback signed with HMAC-SHA256 in `X-IncuBrix-Signature`. | `job_service`, `workers/*`, `config.JOB_MIN_DURATION_SECONDS`, `CALLBACK_HMAC_SECRET` | `tests/test_jobs.py` | PLANNED (Phase 3) |
| 4 | Safe retries: `Idempotency-Key` on POSTs; same key+request returns the same job and never double-processes. | `api/routes/jobs`, idempotency store | `tests/test_idempotency.py` | PLANNED (Phase 3) |
| 5 | Clear errors: JSON `{"error":{"code","message","retryable","details"}}`; codes `UPPER_SNAKE_CASE`, listed in README. | `api/errors.py`, `schemas/common.py`, README error table | `tests/test_errors.py` | DONE (Phase 2) |
| 6 | Configuration from env vars/config file; no hard-coded paths or keys. | `app/config.py` (pydantic-settings) | `tests/test_config.py` | DONE (Phase 2) |
| 7 | Files in, files out: upload or URL inputs; outputs to S3-compatible (MinIO) and returned as download links. | storage abstraction (`storage/local.py`, `storage/s3.py`), MinIO in compose | `tests/test_storage.py` | PLANNED (Phase 3/9) |
| 8 | Structured JSON logs with timestamp, level, `job_id`, request `X-Correlation-Id`; `/health` and `/ready`. | `logging_config.py`, `api/middleware.py`, `api/routes/health.py` | `tests/test_logging.py`, `tests/test_health.py` | DONE (Phase 2) |
| 9 | Output manifest: models/providers/versions, settings, seed, timings, cost, warnings, licence/rights. | `manifest_service` | `tests/test_manifest.py` | PLANNED (Phase 7) |
| 10 | Batch runner CLI: runs a folder/file of inputs against the API, writes all results to one folder. | `scripts/batch_runner.py` | `tests/test_batch_runner.py` | PLANNED (Phase 9) |

---

## Levels (Submission Form tab: `3_Levels`) - Core 15 / Advanced 15 / Outstanding 10

A level counts only if every item in it is verified and the level before it counts.

### Core (required)
| Item | Implementation | Status |
|---|---|---|
| All must-haves pass. | see Must-haves table | PLANNED |
| 10 varied inputs (tutorial, news summary, product promo, story; different accents; 20s-5min) produce usable videos. | `test_data/` + batch runner | PLANNED |
| Average relevance >= 3.5/5 from reviewers on the 10 test videos. | human evaluation sheet (`docs/EVALUATION.md`) | PLANNED (mark pending until genuinely rated) |

### Advanced
| Item | Implementation | Status |
|---|---|---|
| >=2 footage sources with a written, measurable selection rule; reason stored in timeline.json. | `providers/footage/*` + selection rule | PLANNED |
| Swap a clip: replace one scene's clip and only the affected part re-renders. | `rendering_service` partial re-render | PLANNED |
| Looks like one video: colour/brightness normalised; sensible pacing. | `rendering_service` + pacing rules | PLANNED |
| Accepts IncuBrix scene lists (text + visual_hint per scene). | `scene_service` scene-list input | PLANNED |

### Outstanding
| Item | Implementation | Status |
|---|---|---|
| Independent vision-language model scores each clip vs narration; show agreement with human ratings. | `providers/vision/*` (CLIP) + comparison | PLANNED |
| Multilingual narration: Hindi and Tamil as well as English. | TTS/STT language support | PLANNED |
| Production numbers: time and cost per finished minute; concurrent jobs one server handles. | metrics + `tests/test_concurrency.py` | PLANNED |
| >=85% of scenes rated 4 or 5 by reviewers. | human evaluation | PLANNED |

---

## Hard cases (Submission Form tab: `6_Hard_cases`)

For each: record input, expected behaviour, actual behaviour, result
(PASS/PARTIAL/FAIL), evidence location, warnings/errors. Never hide failures.

| # | Case | Expected behaviour | Tests | Status |
|---|---|---|---|---|
| 1 | Abstract line ("trust is earned slowly") | Semantic visual, not keyword; warning if abstract | `test_ambiguous_words.py` | PLANNED |
| 2 | Numbers/statistics ("sales grew 40% in 2025") | Visual for growth/finance concept; no fabricated data chart | `test_segmentation.py` | PLANNED |
| 3 | Named real person | Block AI realistic faces; respectful/generic visuals; warning | `test_safety.py` | PLANNED |
| 4 | Named brand | No invented logos; safe generic visuals; warning | `test_safety.py` | PLANNED |
| 5 | Ambiguous words: value, bank, cloud, mouse, python | Disambiguate by sentence context; pick relevant footage | `test_ambiguous_words.py` | PLANNED |
| 6 | Sad/sensitive news | Respectful, context-appropriate visuals; warning | `test_safety.py` | PLANNED |
| 7 | 9:16 with subject at edge of 16:9 clip | Preserve subject (smart crop/scale+pad); no cut-off | `test_rendering.py` | PLANNED |
| 8 | 5-minute voiceover | Handle long input within 10-min limit | `test_long_audio.py` | PLANNED |
| 9 | Silent audio | Detect and fail with `INVALID_INPUT`; warning | `test_input_validation.py` | PLANNED |
| 10 | Music-only audio | Detect (no speech) and report; do not fabricate transcript | `test_input_validation.py` | PLANNED |
| 11 | Unsupported file type | Reject with `INVALID_INPUT` | `test_input_validation.py` | PLANNED |
| 12 | Empty script | Reject with `INVALID_INPUT` | `test_input_validation.py` | PLANNED |
| 13 | Footage provider down | Fallback to another provider; job finishes | `test_provider_fallback.py` | PLANNED |
| 14 | Provider returns zero results | Fallback; scene-level warning if none relevant | `test_provider_fallback.py` | PLANNED |
| 15 | Corrupted footage download | Detect, retry/fallback; never use broken clip | `test_provider_fallback.py` | PLANNED |
| 16 | Two users submitting simultaneously | Concurrent jobs handled; no double-processing | `test_concurrent_jobs.py` | PLANNED |

---

## Metrics to report (Submission Form tab: `5_Metrics`)

Real measurements only. "Not measured" is acceptable; a guessed number is not.

| Metric | How measured | Where recorded | Status |
|---|---|---|---|
| Turnaround | Time upload -> finished video for 60s narration, cold and warm. | `manifest.json` timings + `REPORT.md` | PLANNED |
| Cost | Cost per finished minute (footage, generation, TTS, compute); measured vs estimated distinguished. | `manifest.json` cost + `REPORT.md` | PLANNED |
| Coverage | Share of narration time covered by a clip rated >=3/5. | timeline + evaluation | PLANNED |
| Relevance | 1-5 per scene (and independent model score for Outstanding). | `docs/EVALUATION.md` | PLANNED (pending real ratings) |
| Reliability | Render success rate across tests; repeat-clip rate (must be 0). | `test_results/` summary | PLANNED |
| Resources | Peak memory and GPU time (if a GPU was used). | `manifest.json` resources | PLANNED |

---

## Risk register (highest-risk must-haves first)

1. **#4 Correct video output (FFmpeg).** Black/frozen frames, audio drift,
   9:16/1:1 crops cutting off subjects. Mitigation: reusable FFmpeg utils,
   scale+pad (never stretch), `apad`/`-shortest` for drift, FFprobe validator
   that fails the build on black-frame/frozen-frame/duration mismatch. FFmpeg
   is bundled in the Docker image (Phase 6).
2. **#3 + #5 Licence honesty + relevance.** Fabricating licences/scores or
   keyword-only matching. Mitigation: mock provider only emits synthetic
   FFmpeg-generated clips with explicit mock licence metadata; no real asset
   is selected unless its licence fields are complete; relevance uses real
   embeddings with an explainable score; never claims an unimplemented vision
   model is used.
3. **#2 Honest timing from TTS.** Pretending estimated timings are exact.
   Mitigation: mock TTS emits a real synthetic word timeline; real TTS gives
   true word boundaries; `timeline.json` records measured vs estimated.
4. **#6 Safety calibration.** Over-blocking (no footage) or under-blocking
   (unsafe). Mitigation: rule-based allow/deny with explicit per-scene warnings;
   conservative by default; never silently substitutes unsafe footage.

---

## Open questions (raised during planning)

- **Git repository for submission.** The IncuBrix brief requires a private
  GitHub repo with real commit history. The current workspace's parent
  (`C:/Users/subha`) is already a git repo and is being left untouched per the
  candidate's instruction. Decision pending: `git init` inside this project
  folder to create a dedicated repo with phase-by-phase commits.
- **Real TTS provider for the live demo.** Mock TTS is used for automated
  tests (zero keys). The live demo must use a real TTS adapter with verified
  commercial-use terms. Provider selection remains open; candidates and their
  licences will be recorded in `SOURCES.md` before lock-in.
