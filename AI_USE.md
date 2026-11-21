# AI_USE.md

Honest disclosure of AI tools used to build this project, and what each was
used for. Per the IncuBrix brief, the design and core logic are the
candidate's; AI tools assist with implementation, explanation and review. The
candidate can explain and modify all submitted code in a live session.

---

## Tools used

| Tool | Used for |
|---|---|
| Kiro (Anthropic-based assistant) | Architecture and phase planning; writing the FastAPI backend foundation (config, logging, errors, health endpoints, OpenAPI export); writing tests; explaining FFmpeg and design decisions; generating documentation (README, traceability, SOURCES, this file). |
| `pypdf` / `openpyxl` (transient) | Reading the assignment brief PDF and submission form XLSX so requirements could be verified against the plan. Not part of the shipped service. |

> Update this table if other tools (ChatGPT, Claude, Copilot, Cursor, etc.) are
> used as the project progresses. List the model/API where known and be
> specific about what it was used for.

## What is AI-assisted vs. written by hand

- **AI-assisted:** scaffolding code, boilerplate (config, logging, error
  handlers, health routes, OpenAPI export script), test authoring, and
  documentation prose.
- **Decisions owned by the candidate:** overall architecture (two-service
  design, provider-adapter pattern, mock-default policy), provider/licence
  choices, and the phase-by-phase plan. These are reviewed and approved phase
  by phase before implementation.

## What AI did NOT do

- No AI tool was given the confidential assignment files to publish.
- No API keys, secrets, or personal data were shared with any AI tool.
- No fabricated test results, metrics or licences were generated. Where a value
  is not yet measured, it is marked pending.
