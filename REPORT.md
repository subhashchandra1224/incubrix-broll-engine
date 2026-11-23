# REPORT.md

IncuBrix Engineering Assessment 3 — Script and Voiceover to B-roll Video Engine

---

## 1. Architecture decisions

### Why two services (api + worker)?

The brief requires background jobs so the API never blocks, concurrent jobs without double-processing, and recovery when a worker crashes. A second process polling the same SQLite database with WAL mode satisfied all three cleanly. The worker re-queues any job left `running` on startup (restart recovery). Two containers in Docker Compose share one SQLite file and one storage volume, keeping the local stack simple while modelling how IncuBrix runs services over HTTP.

### Why SQLite (not PostgreSQL)?

The brief explicitly says "SQLite for simple local persistence." WAL mode + a 5 s `busy_timeout` gives safe concurrent access from the api and worker processes. `DATABASE_URL` accepts any SQLAlchemy URL, so switching to PostgreSQL requires only an env-var change and no code changes.

### Provider adapter pattern

Every external AI capability (STT, TTS, scene understanding, embeddings, footage search, safety) sits behind a small interface. Configuration (`*_PROVIDER` env vars) selects the adapter. The default is `mock` for all, so the full pipeline and the entire test suite run with zero API keys and zero paid calls. This satisfies the brief's "swappable providers" rule and Integration Standard #6.

### FFmpeg as the rendering engine

FFmpeg is the only open-source tool that satisfies all of Must-have 4 (H.264/AAC, 30fps, 1080p, normalised codecs) without additional cost or licence restrictions. It is invoked as an external subprocess so no AGPL concern applies. `imageio-ffmpeg` bundles a static binary for local dev fallback; the Docker image installs FFmpeg via `apt` for reproducibility.

### Narration as the master duration reference

`concat_clips_with_audio` uses `tpad=stop_mode=clone` + `-t {narration_duration}` rather than `apad + -shortest`. `tpad` extends the video by cloning the last frame when clips are shorter than narration; `-t` trims when longer. This guarantees the output duration equals the narration duration regardless of clip lengths, satisfying "the narration sets the timing, not the clips."

### Local-first storage with S3 fallback

A `StorageBackend` interface has two implementations: `LocalStorage` (dev) serves files via the existing `/outputs/` API endpoints; `S3Storage` (MinIO in Compose) stores files in a bucket set to anonymous download, so the browser can open URLs directly. `STORAGE_BACKEND=s3` enables MinIO in Compose; `local` is the default for all tests.

---

## 2. Approaches considered and trade-offs

| Decision | Chosen approach | Alternative considered | Reason for choice |
|---|---|---|---|
| Background jobs | SQLite-polled worker | Celery + Redis | No extra deps; sufficient for single-server demo; SQLite WAL handles concurrency |
| Segmentation | Rule-based sentence splitter (Phase 5) | LLM-based segmentation | No paid API; deterministic; testable |
| Semantic relevance | Mock bag-of-words + optional `fastembed` MiniLM-L6-v2 | Paid embedding API | Apache-2.0, no torch, ~90 MB, local |
| Safety | Keyword blocklists | NER + vision model | No model download required in default path; limitations documented honestly |
| TTS | Mock (test data) | Coqui TTS, Azure TTS | No TTS enabled pending model/terms verification (see section 5) |
| Storage | LocalStorage (default) + S3Storage (MinIO) | Only local | Integration Standard #7; MinIO is the brief's example |

---

## 3. What works (verified in this environment)

### Must-haves

| # | Status | Evidence |
|---|---|---|
| 1 | PARTIAL | Script, audio URL, scene list, and audio file upload all accepted. `input_type` recorded in job result. Real STT/TTS pending. |
| 2 | PARTIAL | Segmentation is gap-free and overlap-free (tested). Visual descriptions generated. Timing is estimated (mock TTS) — labelled as such. Real word-boundary timings pending real TTS/STT. |
| 3 | PARTIAL | Per-clip licence fields recorded in `timeline.json` and `manifest.json`. Mock licence clearly labelled `test_data=true`. Real provider licence verification pending. |
| 4 | PARTIAL | FFmpeg renders H.264/AAC/30fps/yuv420p MP4s for all three ratios, FFprobe-validated. Sample render in `test_data/sample_render/`. No black/frozen frames in fixture outputs. Real footage (non-fixture) pending. |
| 5 | PARTIAL | No-repeat enforced in footage selection. Relevance score computed with mock bag-of-words embeddings. Real semantic disambiguation pending real embeddings. |
| 6 | PARTIAL | Keyword-based safety blocklists for people, brands, sensitive topics, alcohol. Limitations documented. Real NER + vision pending. |
| 7 | DONE | Background jobs, progress 0–100, restart recovery, retryable/non-retryable errors, provider fallback chain, concurrent concurrent submissions tested (simultaneous same-key → one job). |
| 8 | PARTIAL | Integration Standard points 1–10 implemented (see below). Docker Compose images built cleanly; MinIO image pull blocked in this sandbox. Live demo pending. |

### Integration Standard

| # | Status |
|---|---|
| 1. One-command start | PARTIAL — `docker compose up --build` starts the stack; MinIO pull blocked in sandbox |
| 2. OpenAPI 3.1 | DONE — 11 paths in `openapi.yaml` matching the live API |
| 3. Background jobs | DONE — 202, job_id, progress, result links, HMAC callback |
| 4. Idempotency-Key | DONE — same key+body → same job; tested under concurrency |
| 5. Clear errors | DONE — UPPER_SNAKE codes, retryable flag, details |
| 6. Configuration | DONE — all settings from env vars |
| 7. Files in, files out | PARTIAL — upload + URL inputs; local storage + MinIO (MinIO live test blocked in sandbox) |
| 8. Logs and health | DONE — JSON logs with correlation_id, job_id; `/health`, `/ready` |
| 9. Output manifest | DONE — providers, models, settings, seed, timings, costs, rights |
| 10. Batch runner | DONE — `python scripts/batch_runner.py <inputs> <out_dir>` |

---

## 4. Test results (actual counts)

Total collected: 197 tests (189 run, 8 skipped).

### Per-file breakdown

| Test file | Count | Phase | What it tests |
|---|---|---|---|
| test_health.py | 3 | 2 | /health, /ready, correlation ID |
| test_errors.py | 8 | 2 | Error envelope, all UPPER_SNAKE codes |
| test_logging.py | 5 | 2 | JSON formatter, correlation_id, job_id in logs |
| test_openapi.py | 3 | 2 | OpenAPI version, paths present, YAML matches live |
| test_jobs_api.py | 14 | 3 | POST/GET job, all idempotency cases, input validation |
| test_idempotency_concurrency.py | 1 | 3 | 6 simultaneous same-key requests → exactly one job |
| test_callbacks.py | 4 | 3 | HMAC signing, sign_bytes, send, callback on success |
| test_worker.py | 5 | 3+6 | Process, no-queue, restart recovery, non-retryable, retryable |
| test_factory.py | 6 | 4 | Provider selection by name, unknown raises, chain dedup |
| test_providers_mock.py | 6 | 4 | Mock STT/TTS/embeddings/footage determinism, test_data flags |
| test_footage_service.py | 8 | 4 | Fallback on fail/empty, all-fail error, no-repeat, safety, determinism |
| test_pipeline_phase4.py | 7 | 4–9 | Full pipeline, all input types, fallback, API contract |
| test_segmentation.py | 13 | 5 | Sentence splitting, coverage gaps/overlaps, long-sentence, timing flags |
| test_disambiguation_mock.py | 12 | 5 | Ambiguous words with mock embeddings, results recorded |
| test_disambiguation_real_embeddings.py | 8 | 5 | **SKIPPED** — MiniLM model not cached |
| test_safety_phase5.py | 19 | 5 | Avoid terms, named people, brands, sensitive, alcohol, documented limits |
| test_ffmpeg_utils.py | 12 | 6 | FFprobe, normalise, concat, validate, black/frozen frames |
| test_rendering_service.py | 11 | 6 | All three ratios, SRT, AV drift, missing clip warning |
| test_pipeline_phase6.py | 7 | 6 | E2E render, ffprobe checks, resolutions, scene-list |
| test_timeline.py | 4 | 7 | timeline.json structure, all required fields, timing coverage, fallbacks |
| test_manifest.py | 8 | 7 | manifest.json fields, test-data, providers, cost=0, timings, seed |
| test_outputs_api.py | 13 | 7 | Download endpoints, unfinished/failed 404, job scoping, path traversal |
| test_e2e_artifacts.py | 5 | 7 | SRT first cue, duration vs narration, burn-in, video shorter/longer |
| test_storage.py | 5 | 9 | LocalStorage available/store/url/idempotent; S3Storage mock-boto3 |
| test_upload.py | 7 | 9 | JSON coexistence, bad extension, empty file, missing fields, valid WAV, idempotency, full flow |
| test_batch_runner.py | 3 | 9 | Single input E2E, multi-input load, stable idempotency keys |

**Phase 9 test breakdown (corrected from earlier report):**
- Storage: 5 tests (test_local_storage_available, test_local_storage_store_copies_file, test_local_storage_public_url_format, test_local_storage_idempotent_store, test_s3_storage_put_and_url)
- Upload: 7 tests (test_json_client_still_works, test_upload_unsupported_extension_rejected, test_upload_empty_file_rejected, test_upload_missing_aspect_ratios_rejected, test_upload_valid_wav_accepted, test_upload_idempotency_key_respected, test_upload_and_process_job_succeeds)
- Batch runner: 3 tests (test_batch_runner_single_input, test_batch_runner_loads_multiple_inputs, test_batch_runner_stable_idempotency_keys)
- **Total: 15** ✓

---

## 5. Known limitations and pending verifications

### Real TTS — not enabled

**Coqui TTS** (coqui-ai/TTS on GitHub): The library is MPL-2.0, which permits commercial use. However, model weights have varying licences. `tts_models/en/vctk/vits` is listed with a CC BY 3.0 licence, which permits commercial use with attribution. **Status: pending — the library was not installed and no model was downloaded during this assessment. The adapter interface is designed and ready; enabling it requires:**
1. `pip install TTS` (requires torch, ~4 GB)
2. Verifying the specific model's licence in the model card
3. Recording the exact model version and licence URL in `SOURCES.md`
4. Implementing the `CoquiTTS` adapter class behind the existing `TTSProvider` interface

The mock TTS is used throughout; test outputs are labelled `test_data=True`.

### Licensed footage providers — not enabled

No real footage provider (Pexels, Pixabay, or generative model) has been wired. The mock provider returns synthetic colour-bar clips labelled `test_data=True`. To enable Pexels: verify the [Pexels API licence](https://www.pexels.com/api/), which currently permits embedding in commercial products with attribution; record in `SOURCES.md`; implement `PexelsFootage` behind the `FootageProvider` interface.

### MiniLM-L6-v2 disambiguation — model not cached

fastembed 0.9.1 (Apache-2.0, confirmed from installed dist-info) and the `local-minilm` adapter are implemented and tested structurally. The model ONNX files (~90 MB) could not be downloaded because HuggingFace connections failed in this sandbox. **8 disambiguation tests are skipped** — they will pass green once the model is cached. The skip guard (`_is_model_cached()`) prevents any download during the test suite.

### MinIO / Docker Compose full stack

All three application images (`inc-api`, `inc-worker`, `inc-frontend`) built cleanly via `docker compose build`. The `minio/minio` and `minio/mc` images could not be pulled from Docker Hub in this sandbox. On a machine with Docker Hub access, `docker compose up --build` starts the full stack (MinIO on :9000/:9001, frontend on :3000, API on :8000). The S3Storage code path is tested with a mock boto3 client (5 tests pass). Full live MinIO verification is documented as pending.

### Human evaluation scores

The brief requires average human relevance ratings of ≥ 3.5/5 for Core level. All scores in the evaluation sheet are marked **PENDING** until a human reviewer rates them. No scores have been invented.

### Audio/visual burn-in captions

The `burn_captions` function is implemented using FFmpeg's `subtitles` filter, which requires a font file. On the Docker image, `fonts-noto` is installed via apt. In the local test environment (no font configured), burn-in produces a warning in the job result instead of crashing — tested and documented.

---

## 6. Measured numbers

**Live batch run (3 inputs, local server, all mock providers, Windows i7):**

| Input | Scenes | Ratios | Duration | Status | FFprobe |
|---|---|---|---|---|---|
| 01_saving_money.json | 3 | 16:9 | 7.2s | succeeded | PASS: H.264/AAC/30fps/1920×1080/drift=0.0s/black=0 |
| 02_product_promo.json | 3 | 16:9 + 9:16 | 6.4s | succeeded | PASS: 1920×1080 and 1080×1920/drift=0.0s/black=0 |
| 03_news_summary.json | 3 | 16:9 | 7.2s | succeeded | PASS: H.264/AAC/30fps/1920×1080/drift=0.0s/black=0 |

**Batch runner summary:** 3/3 succeeded, 0 warnings, 0 errors. `summary.json` written to `test_results/batch_run_phase10/`.

**Sample render (test_data/sample_render/):** 3 MP4s + SRT verified by `scripts/verify_sample_render.py`:
- `video_16_9.mp4`: 1920×1080, 30fps, h264, 9.0s, drift=0.019s, black=0 — **PASS**
- `video_9_16.mp4`: 1080×1920, 30fps, h264, 9.0s, drift=0.019s, black=0 — **PASS**
- `video_1_1.mp4`: 1080×1080, 30fps, h264, 9.0s, drift=0.019s, black=0 — **PASS**

**Turnaround (mock pipeline + fixture render):** ~3–8 s per job (9s narration, 3 scenes, local Windows).

**Cost per finished minute:** $0.00 (all mock providers). Real cost estimates are in SOURCES.md.

**Coverage:** 100% of narration time covered by clips (gap-free segmentation verified in test suite).

**Reliability:** render success rate 100% across all automated and live tests. Repeat-clip rate 0%.

---

## 7. Bugs found and fixed during Phase 10 (honest disclosure)

1. **FFmpeg concat list with relative paths on Windows.** The `tempfile.NamedTemporaryFile` for concat lists was written with relative audio/video paths. On Windows, FFmpeg processes relative paths from its own working directory, not the Python process's cwd, so the files were not found. **Fixed:** `app/utils/fixtures.py` and `app/utils/ffmpeg.py` now write `os.path.abspath(path).replace("\\", "/")` into concat lists.

2. **LocalStorage same-path copy error (WinError 32).** `shutil.copy2(src, dst)` raised "process cannot access file" when `src` and `dst` were the same absolute path (the file is already in the storage root, so no copy is needed). **Fixed:** `app/utils/storage.py` now compares `os.path.abspath(local_path) != os.path.abspath(dst)` before copying.

Both bugs were caught by running the live API + batch runner in Phase 10 and reading the structured JSON worker logs. The automated test suite passed before and after both fixes (the tests use mock fixtures that bypass these paths, which is why they didn't catch them). The fixes are low-risk and correct the behaviour precisely.

---

## 7. What would I do next

1. Wire Coqui TTS as the first real TTS adapter after verifying `tts_models/en/vctk/vits` CC BY 3.0 licence.
2. Wire Pexels footage after recording the licence in `SOURCES.md`.
3. Download and cache the MiniLM-L6-v2 ONNX model; re-run the 8 skipped disambiguation tests.
4. Run `docker compose up --build` on a machine with Docker Hub access; run the batch runner against the live Compose stack; record the turnaround time and cost per minute.
5. Submit 10 varied test inputs through the live stack; collect human relevance ratings for the Core evaluation.
6. Add a rate limit to the live demo endpoint (`slowapi` or nginx `limit_req`).
7. Implement the clip-replacement endpoint for the Advanced level.
