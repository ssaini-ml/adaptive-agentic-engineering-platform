# Adaptive Agentic Engineering Platform

An evidence-first repository intelligence platform. The initial implementation
focuses on safe, reproducible Python repository scanning before adding reasoning
or code-modification capabilities.

## Documents

- [North-star specification](docs/NORTH_STAR_SPECIFICATION.md)
- [V0.1 outcomes](docs/V0_1_OUTCOMES.md)

## Current implementation

The first foundation includes:

- immutable scan and file-record domain models,
- safe local Git repository validation,
- deterministic file discovery and classification,
- content hashing and Git commit/dirty-state capture,
- a minimal FastAPI health endpoint, and
- scanner unit tests that require no external services.

## Local development

Requires Python 3.12 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
uvicorn adaptive_platform.main:app --app-dir backend --reload
```

PostgreSQL persistence, AST extraction, and API ingestion are the next vertical
slice. No repository code is imported or executed by the scanner.
