# CADE Brain

Reusable agent workflow conventions for Claude Code projects. The cognitive core that connects [CADE](https://github.com/GTFerguson/cade) (Agentic Development Environment) across projects.

CADE Brain provides the foundational patterns that make AI agents effective collaborators: discoverable documentation, ownership boundaries, frontmatter-based indexing, and battle-tested rules for code quality.

## Quick Start

### New Project

```bash
git clone https://github.com/GTFerguson/cade-brain.git
cd cade-brain
./setup.sh --project-dir /path/to/your/project
```

### As a Git Submodule

```bash
cd your-project
git submodule add https://github.com/GTFerguson/cade-brain.git
./cade-brain/setup.sh
```

### Existing Project (Migration)

```bash
cd your-project
git submodule add https://github.com/GTFerguson/cade-brain.git
./cade-brain/setup.sh --yes --no-rules
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

### Doc Index Tool (`tools/doc_index.py`)

Zero-dependency frontmatter indexer for documentation discovery:

```bash
# Build index from all docs
python tools/doc-index.py --build

# Query by scope, tag, or status
python tools/doc-index.py --scope auth --tag jwt
python tools/doc-index.py --status draft --json
```

Outputs `.doc-index.json` — a single file that gives any agent instant visibility into all project documentation.

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
- **Zero dependencies** — drops into any Python 3.10+ project without installs

## Documentation

- [Getting Started Guide](docs/guides/getting-started.md) — full walkthrough
- [Migration Guide](docs/guides/migration.md) — adopting in existing projects
