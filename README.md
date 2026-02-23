# Cadence

Agent workflow conventions and tools for Claude Code projects. The rules, indexing, and search that set the rhythm for effective AI-assisted development.

Cadence provides the foundational patterns that make AI agents effective collaborators: discoverable documentation, ownership boundaries, frontmatter-based indexing with hybrid fusion search, and battle-tested rules for code quality. Works standalone with Claude Code or as the methodology layer for [CADE](https://github.com/GTFerguson/cade).

## Quick Start

### New Project

```bash
git clone https://github.com/GTFerguson/cadence.git
cd cadence
./setup.sh --project-dir /path/to/your/project
```

### As a Git Submodule

```bash
cd your-project
git submodule add https://github.com/GTFerguson/cadence.git
./cadence/setup.sh
```

### Existing Project (Migration)

```bash
cd your-project
git submodule add https://github.com/GTFerguson/cadence.git
./cadence/setup.sh --yes --no-rules
```

See [Migration Guide](docs/guides/migration.md) for details on adopting in established projects.

## What You Get

### Rules (`rules/`)

Claude Code rules that install to `~/.claude/rules/` and apply across all projects:

| Rule | Purpose |
|------|---------|
| `markdown-formatting.md` | Obsidian.md compatibility (tables, callouts, frontmatter) |
| `test-driven-debugging.md` | Debug by writing tests, not guessing |
| `code-comments.md` | WHY not WHAT — meaningful, self-contained comments |

### CLAUDE.md Template (`templates/`)

A parameterized project configuration template covering:
- Git commit conventions
- Documentation structure and rules
- Workspace ownership boundaries
- Module lifecycle (prototype → stabilise → graduate)
- Scope tags for agent discovery

### Doc Index Tool (`tools/doc_index`)

Zero-dependency frontmatter indexer with hybrid fusion search:

```bash
# Build index (+ TF-IDF, optionally embeddings)
python -m tools.doc_index --build
python -m tools.doc_index --build --embeddings

# Hybrid fusion search — combines fuzzy + TF-IDF + embeddings via RRF
python -m tools.doc_index --query "how does authentication work" --json

# Filter by scope, tag, or status
python -m tools.doc_index --scope auth --tag jwt
python -m tools.doc_index --status draft --json
```

`--query` is the recommended search mode for agents — it automatically fuses all available retrieval signals, removing the guesswork of choosing between fuzzy and semantic search. See [Doc Index Reference](docs/guides/doc-index.md) for the full guide.

### Setup Script (`setup.sh`)

Idempotent scaffolding that:
1. Creates `docs/` directory structure
2. Generates `CLAUDE.md` from template
3. Symlinks rules to `~/.claude/rules/`
4. Links the doc-index tool into your project
5. Creates `.doc-index.yaml` config
6. Updates `.gitignore`

Safe to re-run — skips existing files, warns on conflicts.

## Philosophy

- **Docs are first-class** — agents need discoverable knowledge, not just code
- **Ownership prevents conflicts** — clear boundaries between shared and owned areas
- **Frontmatter enables tooling** — structured metadata makes docs queryable
- **Rules are universal** — coding principles that improve any codebase
- **Zero dependencies** — pure stdlib Python, drops into any 3.10+ project without installs

## Documentation

- [Getting Started Guide](docs/guides/getting-started.md) — full walkthrough
- [Doc Index Reference](docs/guides/doc-index.md) — search modes, fusion, graph traversal, agent patterns
- [Migration Guide](docs/guides/migration.md) — adopting in existing projects
