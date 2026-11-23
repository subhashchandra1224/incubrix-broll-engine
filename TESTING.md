# TESTING.md

How to run every test level in this project, what is verified at each level,
and an honest record of what could and could not be run in this environment.

---

## One-command test run (no API keys, no model downloads)

```bash
# From the backend/ folder with the venv active:
cd backend
python -m pytest -q
```

Expected: **189 passed, 8 skipped, 1 warning** (skipped = MiniLM model not cached).

All providers default to `mock`. No API keys, no paid calls, no network, no
Docker required.

---

## Test levels and what they verify

### Unit tests (Phases 2–5)

| File | Tests | What is verified |
|---|---|---|
| test_health.py | 3 | /health, /ready, correlation-ID echo |
| test_errors.py | 8 | JSON error envelope; all UPPER_SNAKE codes; retryable flag |
| test_logging.py | 5 | JSON formatter; correlation_id and job_id propagated via contextvars |
| test_openapi.py | 3 | OpenAPI 3.1; committed YAML matches live schema |
| test_segmentation.py | 13 | Sentence splitting; gap/overlap coverage; long-sentence phrase split; timing flags |
| test_disambiguation_mock.py | 12 | Ambiguous-word ranking with mock bag-of-words; actual ranking outcomes recorded |
| test_safety_phase5.py | 19 | Avoid terms; named-people/brand/sensitive/alcohol blocklists; documented limits |
| test_providers_mock.py | 6 | Mock STT/TTS/embeddings/footage/safety: determinism + test_data labels |
| test_factory.py | 6 | Provider selection by name; unknown → PROVIDER_NOT_CONFIGURED; chain dedup |
| test_storage.py | 5 | LocalStorage available/store/url/idempotent; S3Storage via mock-boto3 |

### Integration tests (Phases 3–4)

| File | Tests | What is verified |
|---|---|---|
| test_jobs_api.py | 14 | POST/GET; all idempotency cases; input validation; HTTP contract |
| test_idempotency_concurrency.py | 1 | 6 simultaneous same-key requests → exactly one job in DB |
| test_callbacks.py | 4 | HMAC-SHA256 signing; X-IncuBrix-Signature header; callback on success |
| test_worker.py | 5 | Worker processing; no-queue; restart recovery; retryable/non-retryable errors |
| test_footage_service.py | 8 | Fallback on provider fail/empty; all-fail → FOOTAGE_UNAVAILABLE; no-repeat; safety |
| test_pipeline_phase4.py | 7 | Full pipeline (all input types, fallback, API contract) |

### Rendering tests (Phase 6)

| File | Tests | What is verified |
|---|---|---|
| test_ffmpeg_utils.py | 12 | FFprobe reads codec/resolution/fps; normalise to all 3 ratios; concat; validate; black/frozen frame detection; silent audio generation |
| test_rendering_service.py | 11 | All 3 ratios via render_job; SRT created with ≥1 entry; AV drift < 0.1s; missing clip → warning |
| test_pipeline_phase6.py | 7 | E2E render: script+audio+scenes; FFprobe codec/resolution checks; coverage warnings |

### Output metadata and download tests (Phase 7)

| File | Tests | What is verified |
|---|---|---|
| test_timeline.py | 4 | timeline.json structure; per-clip licence fields; timing coverage; fallbacks list |
| test_manifest.py | 8 | manifest.json all top-level fields; cost=0 for mocks; timings measured; seed hex |
| test_outputs_api.py | 13 | Download endpoints; unfinished/failed jobs return 404; job scoping; path traversal blocked |
| test_e2e_artifacts.py | 5 | SRT first cue at 00:00:00; output duration = narration duration; burn-in; video shorter/longer than narration |

### Upload and batch tests (Phase 9)

| File | Tests | What is verified |
|---|---|---|
| test_upload.py | 7 | JSON endpoint unaffected; bad extension rejected; empty file rejected; valid WAV accepted; idempotency; full upload→process flow |
| test_batch_runner.py | 3 | Single input E2E; multi-input folder load; stable idempotency keys |

---

## Skipped tests

| File | Skipped | Reason |
|---|---|---|
| test_disambiguation_real_embeddings.py | 8 | MiniLM model ONNX files not downloaded (HuggingFace connection failed in sandbox). Tests use `pytest.mark.skipif(not _is_model_cached())`. They will run green once the ~90 MB model is cached. |
| test_ffmpeg_utils.py, test_rendering_service.py, test_pipeline_phase6.py, test_e2e_artifacts.py, test_upload.py (some) | 0 | All pass when ffmpeg + ffprobe are in PATH or imageio-ffmpeg is installed. |

---

## Hard-case test results

Automated hard cases from the brief:

| Case | Test | Expected | Actual | Result |
|---|---|---|---|---|
| Abstract line ("trust is earned slowly") | test_disambiguation_mock.py::TestAbstractLines::test_trust_abstract_query | Returns a clip; records ranking | Bag-of-words shares "trust" token with handshake clip; ranks it first | PASS (structural) |
| Numbers / statistics ("sales grew 40%") | test_disambiguation_mock.py::TestAbstractLines::test_statistics_query | Analytics clip ranks higher | "sales" token shared; analytics clip ranks first | PASS |
| Ambiguous: bank | test_disambiguation_mock.py::TestBankDisambiguation | Financial clip higher for financial context | Deterministic; documented limitation of bag-of-words | PASS (structural); real semantics PENDING (MiniLM) |
| Ambiguous: cloud | test_disambiguation_mock.py::TestCloudDisambiguation | Computing clip higher for computing context | "computing server" tokens help; documented | PASS |
| Ambiguous: python | test_disambiguation_mock.py::TestPythonDisambiguation | Programming clip higher for code context | "programming language software" tokens help | PASS |
| Ambiguous: value, mouse | test_disambiguation_mock.py | Clips ranked | Deterministic ranking recorded | PASS |
| Named person in narration | test_safety_phase5.py::test_named_person_in_narration_produces_warning_not_block | Warning produced; not blocked | Warning recorded | PASS |
| Brand in narration | test_safety_phase5.py::test_brand_in_narration_warns_not_blocks | Warning produced | Warning recorded | PASS |
| Sad/sensitive news | test_safety_phase5.py::test_sensitive_topic_warns_not_blocks | Warning produced | Warning recorded | PASS |
| Alcohol | test_safety_phase5.py::test_alcohol_in_narration_blocked_by_default | Blocked | Blocked | PASS |
| Empty script | test_jobs_api.py::test_empty_script_rejected | 400 INVALID_INPUT | 400 | PASS |
| Bad file type upload | test_upload.py::test_upload_unsupported_extension_rejected | 400/422 | 400 | PASS |
| Provider down | test_footage_service.py::test_fallback_when_primary_fails | Fallback used | Fallback used | PASS |
| All providers down | test_footage_service.py::test_all_providers_fail_raises | FOOTAGE_UNAVAILABLE | FOOTAGE_UNAVAILABLE | PASS |
| Two simultaneous jobs | test_idempotency_concurrency.py | One job created | One job created | PASS |
| 5-min voiceover | Not automated | Accepted (≤10 min) | Validated by duration check | PASS (validation) |
| Silent audio | Not automated (requires real file) | INVALID_INPUT | Validation logic implemented | PENDING (real audio) |
| Cannot detect unnamed person | test_safety_phase5.py::test_cannot_detect_unnamed_real_person | Limitation documented | Allowed, no warning | PASS (documented limit) |

---

## End-to-end tests (automated)

Two automated E2E flows run in `test_e2e_artifacts.py` and `test_pipeline_phase6.py`:

**E2E 1 — script input:**
1. POST `/api/v1/broll/jobs` with script.
2. Worker runs pipeline with mock TTS + mock footage + fixture render.
3. GET `/api/v1/jobs/{id}` → `succeeded`.
4. Download `video_16_9.mp4` → verify H.264/AAC/30fps/1920×1080.
5. Download `captions.srt` → verify first cue at 00:00:00.
6. Verify output duration ≈ narration duration.
7. Download `timeline.json` → verify per-clip licence fields.
8. Download `manifest.json` → verify providers, cost, seed.

**E2E 2 — audio upload:**
1. POST `/api/v1/broll/jobs/upload` with a 2s WAV file.
2. Worker runs pipeline with mock STT + mock footage + fixture render.
3. GET `/api/v1/jobs/{id}` → `succeeded`, `input_type == "audio"`.

Both tests pass in the automated suite with no API keys.

---

## Docker Compose verification

**What passed:**
- `docker compose build` — all three application images built cleanly (`inc-api`, `inc-worker`, `inc-frontend`).
- Backend image includes FFmpeg, FFprobe, and fonts-noto via apt.
- Frontend image uses nginx with `/api` reverse-proxy.

**What could not be verified:**
- `docker compose up` — MinIO image pull (`minio/minio`, `minio/mc`) blocked by Docker Hub auth in this sandbox.
- Live browser workflow — requires running Compose stack.
- Live MinIO artifact storage — S3Storage tested with mock-boto3; real MinIO pending.

**To verify on a machine with Docker Hub access:**
```bash
docker compose up --build
# Then:
curl http://localhost:8000/health        # → {"status":"ok"}
curl http://localhost:8000/ready         # → {"status":"ready","checks":{...}}
# Open http://localhost:3000 in a browser
# Submit a script job, wait for completion, preview and download the MP4
```

---

## Human evaluation

Relevance ratings are **PENDING** — a human reviewer must rate each scene's
footage 1–5 before these scores can be reported. No scores have been invented.
The evaluation template is in `docs/EVALUATION.md` (to be created before
submission). Average target for Core: ≥ 3.5/5.

---

## Batch runner one-command test

```bash
# terminal 1
cd backend && python -m uvicorn app.main:app --reload --port 8000
# terminal 2
cd backend && python -m app.workers.worker
# terminal 3
python scripts/batch_runner.py test_data/batch_inputs test_results/batch_run
```

Expected output: 3 jobs submitted, all succeeded, `summary.json` written.
No API keys required (all mock providers).
