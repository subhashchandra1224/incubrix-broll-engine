# SOURCES.md

Every dependency, AI model, API, dataset and media source used by this project,
with versions and licences. The default execution path and everything it
outputs must be licensed for commercial use. No research-only / non-commercial
licences (e.g. CC BY-NC) and no AGPL code in the shipped service.

The authoritative dependency list is generated with `pip-licenses` before
submission:

```bash
python -m pip install pip-licenses
pip-licenses --format=markdown --with-urls > docs/licenses.md
```

This file is the human-curated overview; `docs/licenses.md` will be the
machine-generated proof.

---

## Python dependencies (backend)

| Package | Version | Licence | Purpose | Commercial use |
|---|---|---|---|---|
| fastapi | >=0.110 | MIT | Web framework / API | yes |
| uvicorn | >=0.27 | BSD-3-Clause | ASGI server | yes |
| pydantic | >=2.6 | MIT | Data validation / schemas | yes |
| pydantic-settings | >=2.2 | MIT | Env-driven configuration | yes |
| sqlalchemy | >=2.0 | MIT | ORM / SQLite access | yes |
| pyyaml | >=6.0 | MIT | OpenAPI YAML export | yes |
| python-multipart | >=0.0.9 | MIT | Multipart file uploads | yes |
| imageio-ffmpeg | 0.8.1 | BSD-2-Clause | Bundled FFmpeg binary (dev fallback) | yes |

> Licence values above are from each project's published metadata and will be
> confirmed with `pip-licenses` before submission. If any licence is found to
> be non-commercial or AGPL, the package is replaced before it ships.

## Python dependencies (test/dev)

| Package | Version | Licence | Purpose |
|---|---|---|---|
| pytest | >=8.0 | MIT | Test runner |
| httpx | >=0.27 | BSD-3-Clause | TestClient for FastAPI |
| pypdf | (transient) | BSD-3-Clause | Used only to read the assignment brief; not a runtime dependency |
| openpyxl | (transient) | MIT | Used only to read the submission form; not a runtime dependency |

## JavaScript dependencies (frontend - Phase 8)

To be added when the frontend is built (React + Vite). Will list `react`,
`vite`, `axios`/`fetch` and their licences.

## FFmpeg

FFmpeg is used as the video rendering engine (Must-have 4). It is invoked as
an external subprocess — the binary is not linked into the application code.

| Item | Details |
|---|---|
| Package | FFmpeg 9.1 (Gyan.dev full build, Windows); 9.0.2 (imageio-ffmpeg bundled) |
| Binary licence | LGPL 2.1+ for the core; compiled with `--enable-gpl` → GPL 2.0+ for the full build; we invoke it as an external binary and do not distribute our own modified build, so this does not affect our application's licence |
| Usage | Normalise, scale+pad, concat, mix narration, encode H.264/AAC, generate SRT burn-in, run blackdetect/freezedetect |
| Docker | Bundled in the application Docker image (Phase 9: `apt-get install ffmpeg`) |
| Commercial use | Permitted when used as an external tool; full-build GPL libraries are not linked into our application |
| FFprobe | Ships with FFmpeg; used for codec/resolution/fps/duration/drift validation |
| imageio-ffmpeg | 0.8.1, BSD-2-Clause — Python package that bundles a static FFmpeg binary; used as a fallback when system FFmpeg is not in PATH |

## TTS candidates evaluated for the live demo

The live demo requires a real TTS adapter with verified commercial-use terms.
The following options were evaluated. **None has been enabled yet** — the default
test path remains mock TTS only.

| Option | Licence / Terms | Commercial use | API key required | Cost | Decision |
|---|---|---|---|---|---|
| `edge-tts` (Python wrapper for Microsoft Edge Read Aloud) | MIT wrapper licence; **Microsoft Service Agreement** governs the underlying service. Section 3 ("Your Content") and prohibited uses must be reviewed. The service is not authorised for commercial production use without a Microsoft Azure Text-to-Speech subscription. **Verdict: do not use the edge-tts wrapper for commercial production.** Use Azure TTS directly with a subscription. | Needs Azure TTS subscription for commercial use | Azure key required (not keyless as the wrapper appears) | Azure TTS ~$4/1M chars (Neural); free tier 500K chars/month | **Pending** — not enabled; commercial-use terms require Azure subscription |
| `gTTS` (Python wrapper for Google Translate TTS) | MIT wrapper licence; uses Google Translate's **internal** TTS endpoint (NOT Google Cloud Text-to-Speech). Google's ToS for Google Translate does not authorise commercial use of this endpoint. | **NOT for commercial use** | No key (unofficial endpoint) | Free | **Rejected** — not for commercial use; do not enable |
| Google Cloud Text-to-Speech (official API) | Google Cloud Platform ToS permits commercial use with an API key. Neural voices ~$4–16/1M chars; free tier 500K chars/month. | Permitted with a Google Cloud API key | Yes (Google Cloud API key) | ~$4–$16/1M chars | **Pending verification** — accepted in principle; wire as `google-cloud-tts` adapter when key is configured and terms confirmed |
| Coqui TTS (open-source, local) | Mozilla Public License 2.0 (MPL-2.0) for the library. Some model weights are CC BY-SA 4.0 (non-commercial for derivatives). **Verify model licence before using any specific model.** | MPL-2.0 permits commercial use of the library; model licence is per-model | No key required (local) | Compute cost only | **Pending verification** — accepted in principle for local/offline use; must verify model licence per-model before enabling |
| `pyttsx3` (offline, OS TTS) | MIT; uses OS-bundled TTS (SAPI5 on Windows, espeak on Linux) | Permitted; quality is low | No | Free | **Pending** — low-quality fallback; not suitable for production demo |

**Recommendation:** Coqui TTS (MPL-2.0, `tts_models/en/vctk/vits`, CC BY 3.0 — commercial use permitted) is the strongest candidate for a real TTS option. **Status: pending verification.** Model licence and commercial-use terms must be confirmed in this table before any adapter is enabled. No real TTS is wired yet.



## AI models and providers

Every external AI capability is behind an adapter chosen by configuration,
each with a mock implementation. The default path uses mocks only (no models,
no keys). Real adapters are listed here as they are added, with the model,
version, and commercial-use status verified and recorded before enabling.

| Capability | Default (no key) | Real adapter (optional) | Status |
|---|---|---|---|
| Speech-to-text | mock (deterministic transcript + timestamps) | TBD (e.g. faster-whisper / Whisper API) - verify terms first | mock implemented (Phase 4); real adapter pending |
| Text-to-speech | mock (duration + synthetic word timeline, no audio file yet) | TBD - must verify commercial-use terms | mock implemented (Phase 4); real adapter pending |
| Scene understanding / visual description | mock (rule-based noun-phrase extraction + Phase 5 segmentation) | TBD (LLM) - verify terms first | mock implemented (Phase 5); real adapter pending |
| Semantic embeddings | mock (deterministic bag-of-words) **OR** `local-minilm` (fastembed/MiniLM-L6-v2, Apache-2.0) | sentence-transformers/all-MiniLM-L6-v2 via fastembed | mock default (Phase 4); `local-minilm` optional adapter implemented (Phase 5); **MiniLM ranking pending verification** (model download failed in sandbox; 8 disambiguation tests skipped) |
| Footage search | mock (deterministic clips with explicit mock test-data licence) | TBD (e.g. Pexels/Pixabay) - licences verified first | mock implemented (Phase 4); real adapter pending |
| Safety | mock (avoid-term + hardcoded blocklists for people/brands/sensitive/alcohol) | TBD (LLM + NER) - verify terms first | mock implemented (Phase 5); real NER/vision pending |
| Vision-language relevance (Outstanding) | - | TBD (e.g. CLIP, MIT) | not started |

Phase 4 implements the interfaces (`app/providers/base.py`), a deterministic mock
for each (`app/providers/mocks.py`), and config-selected wiring
(`app/providers/factory.py`). This satisfies the brief's "swappable providers"
rule: every external AI service sits behind a small adapter chosen by
configuration, with a mock so tests run with no API keys. No API keys or paid
calls are used in Phase 4; selecting a real adapter that is not wired raises
`PROVIDER_NOT_CONFIGURED`.

## Footage providers

Currently only the mock provider, which returns synthetic clips generated with
FFmpeg and labelled `internal-test-asset / mock-licence`. No real footage
provider is wired until its commercial-use terms are verified and recorded
here. For every selected clip the system records: provider name, asset id,
source URL, download URL / stored reference, licence name, licence URL,
attribution, commercial-use permission, AI-generated flag, and selection reason.

## Datasets and media sources

None used in the default path. Any test media used (e.g. CC0 clips) will be
listed here with source URL and licence before use.

## AI coding tools

See [AI_USE.md](./AI_USE.md).
