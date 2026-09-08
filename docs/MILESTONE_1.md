# Milestone 1 — Safe Persistent Immutable Scans

## Delivered

- PostgreSQL Docker service and environment template
- SQLAlchemy repository, scan, file, and trace models
- Alembic initial migration
- database and ORM immutability guards
- repository registration and lookup APIs
- asynchronous scan request, status, listing, and file APIs
- allowed-root enforcement
- Git-root and valid-HEAD validation
- dirty-tree CAPTURE and REJECT policies
- file-size, count, total-byte, binary, encoding, symlink, and timeout policies
- per-file SHA-256 and scan working-tree fingerprint
- secret finding counts without persisting secret values
- scan execution, decision, failure, and verification traces
- provider-neutral retrieval interface for future Milvus support

## Run PostgreSQL

```bash
docker compose up -d postgres
cp .env.example .env
alembic upgrade head
```

The host port defaults to `5432`. When that port is occupied, set
`AAEP_POSTGRES_PORT` and use the same port in `AAEP_DATABASE_URL`.

Set `AAEP_ALLOWED_REPOSITORY_ROOTS` to the narrowest directory containing the
repositories the platform may inspect.

The file-count and total-byte budgets include artifacts that are subsequently
excluded as binary or undecodable, so exclusions cannot bypass resource limits.

## Run API

```bash
uvicorn adaptive_platform.main:app --app-dir backend --reload
```

## Example

```bash
curl -X POST http://127.0.0.1:8000/repositories \
  -H 'Content-Type: application/json' \
  -d '{"path":"/allowed/path/example"}'
```

Use the returned repository ID:

```bash
curl -X POST http://127.0.0.1:8000/repositories/REPOSITORY_ID/scans \
  -H 'Content-Type: application/json' \
  -d '{"dirty_tree_policy":"CAPTURE"}'
```

The scan request returns `202 Accepted`. Poll the returned scan resource and then
request its files.

## Exit condition

An unfamiliar allowed Git repository can be registered and scanned without
executing its code. The inventory survives restart, is bound to Git and content
identity, cannot be mutated after completion, and produces append-only traces.
