# Architecture

A short, honest note on how the system is structured and why. Expands the
diagram in [../README.md](../README.md). Kept lightweight; avoids unnecessary
abstraction.

## Services

Two processes share one SQLite database file and one storage volume:

- **api (FastAPI)** - accepts requests, validates input, creates job records,
  returns job status and output download links. It never runs long work inline:
  anything expected to take longer than `JOB_MIN_DURATION_SECONDS` (2s) is
  queued for the worker.
- **worker** - polls the `jobs` table for queued jobs and runs the pipeline
  (audio prep -> scene segmentation -> footage -> safety -> rendering ->
  outputs -> manifest). One job at a time by default
  (`JOB_MAX_CONCURRENCY`), so two users submitting at once are handled as two
  queued/running jobs without double-processing.

Sharing a single SQLite file between two processes is fine for a local demo when
WAL mode is enabled (better concurrent read/write). For higher concurrency,
`DATABASE_URL` can be pointed at PostgreSQL without code changes.

## Why two services instead of in-process tasks

- The API never blocks on rendering, so it stays responsive and can serve
  health/status while a job renders.
- The worker can be restarted independently; a job left "running" when a worker
  died is re-queued on startup (recoverable).
- It models how IncuBrix runs services as separate containers talking over a
  shared store.

A single-container embedded worker is a fallback if fewer moving parts are
preferred later.

## Provider adapters

Every external AI capability (STT, TTS, embeddings, scene understanding,
footage search, safety) sits behind a small interface with a **mock**
implementation. Configuration (`*_PROVIDER` env vars) selects which adapter
runs. The default is `mock` for all, so the whole pipeline and the test suite
run with **zero API keys and zero paid calls**. Real adapters are added behind
the same interface only after their commercial-use terms are verified and
recorded in [../SOURCES.md](../SOURCES.md).

## Storage

A `StorageBackend` abstraction with two implementations:
- `LocalStorage` - the local filesystem (development).
- `S3Storage` - MinIO (S3-compatible) in Docker Compose.

Selected by `STORAGE_BACKEND`. Inputs are accepted as an upload or a URL;
outputs are saved to the configured backend and returned as download links.

## Pipeline (planned)

1. Input validation + job record
2. Audio prep (transcribe uploaded audio, or TTS-generate narration from script)
3. Scene segmentation (semantic; preserves narration text + timing)
4. Footage retrieval (provider search, licence filter, avoid rules, relevance
   scoring, no repeats)
5. Footage fallback (try another provider; else a clearly-labelled relevant
   fallback; else explicit scene-level failure)
6. Timing + editing (match clip duration to narration; trim/loop as needed;
   no black/frozen frames; no drift)
7. Captions (SRT + optional burn-in)
8. Rendering (FFmpeg; 16:9 / 9:16 / 1:1; H.264/AAC, 30fps, 1080p-class)
9. Output (videos, `captions.srt`, `timeline.json`, `manifest.json`)
10. Validation (FFprobe: codec, resolution, fps, audio, duration, black-frame,
    frozen-frame, A/V drift; scene coverage; duplicate clips; licence metadata)

## Logging

Structured JSON logs with timestamp, level, logger, message, and (when in
scope) `correlation_id` and `job_id`. A middleware assigns/propagates
`X-Correlation-Id` per request; the worker sets `job_id` in the log context
when processing a job.

## Errors

A single JSON envelope: `{"error":{"code","message","retryable","details"}}`.
Codes are `UPPER_SNAKE_CASE` and listed in the README. Retryable errors
(`UPSTREAM_PROVIDER_ERROR`, `RATE_LIMITED`) drive the worker's retry/fallback
logic; non-retryable errors fail the job with a clear message.
