# AGENTS.md

Notes for AI coding agents working in this repository.

## What this is

PromptCoach Reference, the reference implementation of the five-layer framework in
*Learning to Prompt: A Design Framework for Middle School AI Literacy* (Lim, UTPB,
2026), plus a developer kit: an MCP server (`promptcoach_ref/mcp_server.py`), a
design checklist (`promptcoach_ref/devkit.py`), an Agent Skill
(`skills/prompt-tutor-design-review/`), and `DEVELOPER_GUIDE.md`.

## Commands

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev,mcp]"
.venv/Scripts/python -m pytest              # all tests, offline, no key
.venv/Scripts/python -m pytest -m devkit    # the developer kit and MCP server
.venv/Scripts/promptcoach-mcp               # the MCP server over stdio
```

Use the project venv. A global FastAPI and Starlette mismatch on some machines
fails at import.

## Rules

- `promptcoach_ref/framework/` holds only what the thesis states, each value with a
  section citation and an evidence grade. Never add a value there without a thesis
  citation. Choices the thesis leaves open go in `promptcoach_ref/policy/`.
- `framework` never imports `policy`; a test enforces it.
- `tests/test_grades.py` pins the grade counts (4 Direct, 10 Transferred, 10
  Argued). If it fails, something promoted a proposition to a finding. Fix the
  code, not the test.
- The look-up and checking tools only read `framework`; the demo tools also use
  `policy` and the offline engine. Their text may
  paraphrase a component for a developer, but never add a number, a result, or a
  claim of learning; `tests/test_devkit.py` checks this.
- No tool writes files or calls the network. `coach_attempt` keeps up to 32 demo
  sessions in memory only.
- Do not commit `.env` files or any study data. Student survey data contains names
  and never enters this repository.
