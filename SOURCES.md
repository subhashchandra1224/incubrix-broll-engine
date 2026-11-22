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

## AI models and providers

Every external AI capability is behind an adapter chosen by configuration,
each with a mock implementation. The default path uses mocks only (no models,
no keys). Real adapters are listed here as they are added, with the model,
version, and commercial-use status verified and recorded before enabling.

| Capability | Default (no key) | Real adapter (optional) | Status |
|---|---|---|---|
| Speech-to-text | mock (deterministic transcript + timestamps) | TBD (e.g. faster-whisper / Whisper API) - verify terms first | mock implemented (Phase 4); real adapter pending |
| Text-to-speech | mock (duration + synthetic word timeline, no audio file yet) | TBD - must verify commercial-use terms | mock implemented (Phase 4); real adapter pending |
| Scene understanding / visual description | mock (rule-based noun-phrase extraction) | TBD (LLM) - verify terms first | mock implemented (Phase 4); real adapter pending |
| Semantic embeddings | mock (deterministic bag-of-words vector) | sentence-transformers / all-MiniLM-L6-v2 (Apache-2.0) | mock implemented (Phase 4); real adapter pending |
| Footage search | mock (deterministic clips with explicit mock test-data licence) | TBD (e.g. Pexels/Pixabay) - licences verified first | mock implemented (Phase 4); real adapter pending |
| Safety | mock (avoid-term + blocklist rules) | TBD (LLM) - verify terms first | mock implemented (Phase 4); real adapter pending |
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
