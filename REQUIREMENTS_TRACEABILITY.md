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
| 1 | Both inputs work: audio (mp3/wav/m4a, up to 10 min) and text (TTS narration). Also optional scene list. | `narration_service`, `scene_service`, `schemas/job.py`, `api/routes/jobs.py`, `services/audio_service.py` | `POST /api/v1/broll/jobs`, `POST /api/v1/broll/jobs/upload` | `tests/test_pipeline_phase4.py` (audio, script, scenes), `tests/test_jobs_api.py`, `tests/test_upload.py` | job `result.input_type`, `result.scenes` | PARTIAL (Phase 3–9: script, audio URL, scene-list, and audio file upload all accepted; real STT/TTS pending) |
| 2 | Scenes by meaning, timed to the voice; every second covered; narration sets timing, not clips. | `services/segmentation.py`, `services/narration_service.py`, `services/scene_service.py`, `providers/mocks.py` (MockSceneUnderstanding) | job-internal | `tests/test_segmentation.py` (gap/overlap/coverage, long split, timing flags) | job `result.scenes[].start_time`, `end_time`, `coverage_warnings` | PARTIAL (Phase 5: improved segmentation + timing coverage done; real semantic scene understanding pending) |
| 3 | Every clip licence-clean: source, licence, attribution, link recorded; commercial use; no watermarks; AI-generated flagged. | `footage_service`, `providers/factory.py`, `providers/mocks.py`, `schemas/providers.py`, `timeline_service` | `GET /api/v1/broll/jobs/{id}/timeline` | `tests/test_timeline.py`, `tests/test_pipeline_phase4.py`, `tests/test_footage_service.py` | `timeline.json` (per-clip licence fields) | PARTIAL (Phase 4+7: mock licence metadata recorded per clip in timeline.json; real providers pending) |
| 4 | Correct, consistent video: all requested aspect ratios; normalised resolution/fps/pixel format; no black/frozen frames or audio drift. | `rendering_service`, `caption_service`, `utils/ffmpeg.py`, `utils/fixtures.py` | `GET .../outputs/{filename}` | `tests/test_rendering_service.py`, `tests/test_ffmpeg_utils.py`, `tests/test_pipeline_phase6.py` | sample_render/ (3 MP4s, SRT, FFprobe reports) | PARTIAL (Phase 6: FFmpeg render + FFprobe validation working with fixtures; real footage clips pending Phase 7+; burn-in captions implemented; output download API endpoints pending Phase 7) |
| 5 | No repeats and no nonsense matches: no clip twice; footage matches meaning, not keywords; relevance score + reason. | `footage_service` (no-repeat + relevance), `semantic_service` (embeddings) | job-internal | `tests/test_footage_service.py` (no-repeat, determinism), `tests/test_providers_mock.py` (embeddings similarity) | job `result.scenes[].relevance_score` + `selection_reason` | PARTIAL (Phase 4: mock embeddings relevance + no-repeat done; ambiguous-word real semantics in Phase 5) |
| 6 | Safe output: no AI realistic faces of real people; no invented brand logos; respectful footage for sensitive topics. | `safety_service`, `providers/mocks.py` (MockSafety Phase 5) | job-internal | `tests/test_safety_phase5.py` (avoid terms, named people, brands, sensitive news, alcohol, documented limits) | job `result.scenes[].warnings` | PARTIAL (Phase 5: keyword-based blocklists for people/brands/sensitive/alcohol; real NER + vision face detection pending) |
| 7 | Resilient jobs: background, progress; if a footage source fails the job still finishes via another source/fallback. | `job_service`, `workers/runner.py`, `workers/worker.py`, `footage_service` (fallback chain) | `POST/GET /api/v1/jobs/{id}` | `tests/test_worker.py`, `tests/test_footage_service.py` (fallback on fail/no-results, all-fail error), `tests/test_pipeline_phase4.py` | job logs + status transitions | PARTIAL (Phase 3+4: queue/progress/restart-recovery/retry + footage fallback chain done; real provider fallback pending real adapters) |
| 8 | Integration Standard followed and the live demo works for the review period. | `docker-compose.yml`, frontend, `openapi.yaml`, `scripts/batch_runner.py` | all routes | `tests/test_e2e_script.py`, `tests/test_e2e_audio.py` | `docker compose up` + demo | PLANNED (Phase 8/9) |

---

## Integration Standard (Submission Form tab: `4_Integration`) - 2 marks each

| # | Requirement | Implementation | Tests / Evidence | Status |
|---|---|---|---|---|
| 1 | One-command start and test; `.env.example` lists every setting. | `docker-compose.yml`, `pytest`, `.env.example` | `docker compose up --build`; `python -m pytest -q` (174+ passed, no keys); batch runner one-command | PARTIAL (Phase 9: Compose file and images built cleanly; MinIO stack requires Docker Hub access to pull images — blocked in sandbox; documented in README) |
| 2 | Documented HTTP API: `openapi.yaml` (3.1) matching the running service; routes under `/api/v1/`. | FastAPI OpenAPI metadata, `scripts/export_openapi.py` | `tests/test_openapi.py` (committed file == live schema) | DONE (Phase 2) for current surface; expands as routes are added |
| 3 | Background jobs: >2s work is a job; POST returns 202 + `job_id`; `GET /api/v1/jobs/{id}` returns status/progress/result links; optional callback signed with HMAC-SHA256 in `X-IncuBrix-Signature`. | `job_service`, `workers/runner.py`, `workers/worker.py`, `utils/callbacks.py`, `config` | `tests/test_jobs_api.py`, `tests/test_worker.py`, `tests/test_callbacks.py` | PARTIAL (Phase 3): queue/status/progress/idempotency/restart-recovery/HMAC callback done; output download links arrive in Phase 6/7 |
| 4 | Safe retries: `Idempotency-Key` on POSTs; same key+request returns the same job and never double-processes. | `job_service.create_or_get_job`, unique constraint + race fallback | `tests/test_jobs_api.py`, `tests/test_idempotency_concurrency.py` | DONE (Phase 3) |
| 5 | Clear errors: JSON `{"error":{"code","message","retryable","details"}}`; codes `UPPER_SNAKE_CASE`, listed in README. | `api/errors.py`, `schemas/common.py`, README error table | `tests/test_errors.py` | DONE (Phase 2) |
| 6 | Configuration from env vars/config file; no hard-coded paths or keys. | `app/config.py` (pydantic-settings) | `tests/test_config.py` | DONE (Phase 2) |
| 7 | Files in, files out: upload or URL inputs; outputs to S3-compatible (MinIO) and returned as download links. | `api/routes/jobs.py` (download endpoints), `services/job_service.py` (links), storage abstraction (MinIO in Phase 9) | `tests/test_outputs_api.py` (completed/unfinished/failed/scoping) | PARTIAL (Phase 7: local download links working via HTTP; MinIO storage pending Phase 9) |
| 8 | Structured JSON logs with timestamp, level, `job_id`, request `X-Correlation-Id`; `/health` and `/ready`. | `logging_config.py`, `api/middleware.py`, `api/routes/health.py` | `tests/test_logging.py`, `tests/test_health.py` | DONE (Phase 2) |
| 9 | Output manifest: models/providers/versions, settings, seed, timings, cost, warnings, licence/rights. | `manifest_service`, `timeline_service`, `workers/pipeline.py` | `tests/test_manifest.py`, `tests/test_timeline.py` | DONE (Phase 7) |
| 10 | Batch runner CLI: runs a folder/file of inputs against the API, writes all results to one folder. | `scripts/batch_runner.py`, `test_data/batch_inputs/` | `tests/test_batch_runner.py` | DONE (Phase 9) |

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
