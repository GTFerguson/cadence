# Cadence

Documentation indexing and hybrid search for AI-assisted development. Cadence scans your project's markdown files, builds a searchable index with frontmatter metadata, and gives agents the tools to find the right docs before writing code.

Zero external dependencies. Pure stdlib Python 3.10+. Optional local embeddings via FastEmbed.

Works standalone with Claude Code or as the methodology layer for [CADE](https://github.com/GTFerguson/cade).

## Quick Start

```bash
cd your-project
git submodule add https://github.com/GTFerguson/cadence.git
./cadence/setup.sh
```

Build and search immediately:

```bash
python -m tools.doc_index --build
python -m tools.doc_index --query "how does authentication work"
```

No config file needed. The scanner walks your entire project for `.md` files, skipping `.git/`, `node_modules/`, `build/`, and 20+ other noise directories automatically.

## Doc Index

### Building

```bash
# Scan all markdown, extract frontmatter, build TF-IDF vectors
python -m tools.doc_index --build

# Also build local embeddings (requires: pip install fastembed)
python -m tools.doc_index --build --embeddings
```

Produces three files in `.cade/`:
- `doc-index.json` — full index with metadata, document graph, and code-to-doc mapping
- `doc-index-tfidf.json` — sparse TF-IDF vectors for semantic search
- `doc-index-embeddings.json` — dense vectors via BAAI/bge-small-en-v1.5 (optional)

### Hybrid Fusion Search

`--query` is the recommended search mode. It fuses all available retrieval signals via Reciprocal Rank Fusion (RRF) and returns ranked results:

```bash
python -m tools.doc_index --query "creature genetics system"
```

What happens under the hood:
1. **Fuzzy search** — SequenceMatcher on title, tags, scope, description
2. **TF-IDF search** — cosine similarity on sparse term vectors
3. **Embedding search** — cosine similarity on dense vectors (if built)
4. **RRF fusion** — combines per-signal rankings into a single score
5. **Importance blending** — weights results by document graph importance

If embeddings aren't built, fusion gracefully degrades to fuzzy + TF-IDF. Results include per-signal score breakdowns:

```json
{
  "path": "docs/auth.md",
  "title": "Authentication Guide",
  "_score": 0.82,
  "_signals": {"fuzzy": 0.95, "tfidf": 0.67, "embedding": 0.81}
}
```

### Code-to-Doc Mapping

Find documentation relevant to any code file:

```bash
python -m tools.doc_index --context src/auth.py
```

The indexer scans doc bodies for code references — markdown links, backtick paths, `@see` annotations, bare file paths — and builds a reverse mapping from code files to the docs that discuss them. References are resolved against actual project files with confidence scoring based on match type (exact path vs. filename) and reference type (markdown link vs. inline mention).

### Document Graph

Docs are automatically connected via three edge types:
- **Explicit links** — frontmatter `links:` field, `[[wiki-links]]`, `[text](path.md)`
- **Shared scope** — docs in the same scope (e.g., `scope: [backend]`)
- **Shared tags** — docs sharing 2+ tags

Graph features:

```bash
# Find related docs via BFS traversal
python -m tools.doc_index --related docs/design/architecture.md --depth 2

# Expand search results with 1-hop graph neighbors
python -m tools.doc_index --query "authentication" --expand

# Sort results by topological dependency (prerequisites first)
python -m tools.doc_index --query "getting started" --reading-order

# Dump the full adjacency graph
python -m tools.doc_index --graph
```

### Importance Scoring

Every document gets an importance score (0.0-1.0) that influences search ranking. It's a weighted combination of:

- **Inbound links (50%)** — how many other docs reference this one
- **Path signals (30%)** — depth in directory tree, hub bonuses for README/index files
- **Metadata (20%)** — status (`published` > `draft`), presence of description

### Filtering

```bash
python -m tools.doc_index --scope backend --tag security
python -m tools.doc_index --status draft
python -m tools.doc_index --discover   # list all scopes, tags, statuses
```

### Frontmatter

Cadence reads standard YAML frontmatter without requiring PyYAML:

```markdown
---
title: Authentication Guide
scope: [backend, api]
tags: [auth, security, jwt]
status: published
description: How the auth system works.
links: [docs/api/tokens.md]
---
```

All fields are optional. Missing titles default to the filename. Missing descriptions are auto-extracted from the first paragraph.

### CLI Reference

| Flag | Description |
|------|-------------|
| `--build` | Build index + TF-IDF vectors |
| `--embeddings` | Also build dense embeddings (with `--build`) |
| `--query TERM` | Hybrid fusion search (recommended) |
| `--search TERM` | Fuzzy search only |
| `--semantic TERM` | Embedding search with TF-IDF fallback |
| `--context PATH` | Find docs for a code file |
| `--related PATH` | BFS graph traversal from a doc |
| `--discover` | Show index summary and available metadata |
| `--graph` | Dump full document graph |
| `--scope SCOPE` | Filter by scope |
| `--tag TAG` | Filter by tag |
| `--status STATUS` | Filter by status |
| `--expand` | Include 1-hop graph neighbors in results |
| `--reading-order` | Sort by topological dependency |
| `--top N` | Max results (default: 10) |
| `--rrf-k N` | RRF constant (default: 60) |
| `--depth N` | Max hops for `--related` (default: 1) |
| `--json` | Force JSON output |
| `--table` | Force table output |
| `--project-dir PATH` | Override project root |

Output is JSON when piped (agents get structured data automatically), tables when interactive.

## Configuration

Optional `.doc-index.yaml` in project root:

```yaml
scan:
  - docs/
  - guides/
exclude:
  - .git/
  - node_modules/
  - vendor/
embedding_model: BAAI/bge-small-en-v1.5
```

When `scan` is omitted, the entire project is scanned. The [default exclusion list](tools/doc_index/config.py) covers 20+ common noise directories.

## Rules

Claude Code rules that install to `~/.claude/rules/`:

| Rule | Purpose |
|------|---------|
| `doc-search.md` | Teaches agents to use `--query`, `--context`, `--discover` |
| `markdown-formatting.md` | Obsidian.md compatibility (tables, callouts, frontmatter) |
| `test-driven-debugging.md` | Debug by writing tests, not guessing |
| `code-comments.md` | WHY not WHAT — meaningful, self-contained comments |

## Setup Script

`setup.sh` handles full project scaffolding:

1. Creates `docs/` directory structure
2. Generates `CLAUDE.md` from template
3. Symlinks rules to `~/.claude/rules/`
4. Links the doc-index tool into your project
5. Creates `.doc-index.yaml` config
6. Updates `.gitignore`

Idempotent — safe to re-run. Use `--yes --no-rules` for existing projects.

## Documentation

- [Getting Started Guide](docs/guides/getting-started.md) — full walkthrough
- [Doc Index Reference](docs/guides/doc-index.md) — search modes, fusion, graph traversal, agent patterns
- [Migration Guide](docs/guides/migration.md) — adopting in existing projects
