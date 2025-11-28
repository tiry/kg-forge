# KG Forge – Copilot Instructions

## Project context
- This repo builds a CLI “KG Forge” as described in `docs/seed_product.md`.
- All technical design and constraints are in `docs/seed_architecture.md`.

## When generating code
- Follow the CLI shape: `ingest`, `query`, `render` (and helper commands) as defined in `seed_architecture.md`.
- Respect the Neo4j schema (`:Doc`, `:Entity`, `MENTIONS`, typed relations, namespace).
- Prefer adding tests under `tests/` that exercise the behaviours described in `seed_architecture.md`.

## When creating new features
- First check whether they fit within the v1 scope from `seed_product.md`.
- If something conflicts, prefer the product scope over new features.
