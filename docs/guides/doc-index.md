---
title: Doc Index Reference
scope: [all]
created: 2026-02-23
status: published
tags: [doc-index, search, guide, reference]
description: Complete reference for the doc-index tool — building indexes, search modes, hybrid fusion search, graph traversal, and agent integration patterns.
---

# Doc Index Reference

`doc-index` scans markdown files for YAML frontmatter, builds a queryable JSON index, and provides multiple search modes from simple filtering to hybrid fusion search that combines all available retrieval signals automatically.

## Building the Index

```bash
# Build base index + TF-IDF (always, no dependencies)
python -m tools.doc_index --build --project-dir /path/to/project

# Build with local embeddings (requires fastembed)
python -m tools.doc_index --build --embeddings --project-dir /path/to/project
```

`--build` scans directories listed in `.doc-index.yaml`, extracts frontmatter metadata (title, scope, status, tags, description, links), computes a document graph and importance scores, and writes:

| Output | Contents |
|--------|----------|
| `.cade/doc-index.json` | Full index with docs, graph, and metadata |
| `.cade/doc-index-tfidf.json` | TF-IDF vectors for semantic search |
| `.cade/doc-index-embeddings.json` | Dense embeddings (only with `--embeddings`) |

All output files are stored in `.cade/` to keep the project root clean. Add `.cade/` to `.gitignore` — these are generated artifacts.

TF-IDF is always built — it's fast and uses only stdlib. Embeddings require `pip install fastembed` and provide stronger semantic matching but take longer on first build (subsequent builds cache unchanged docs).

## Search Modes

### Filtering — `--scope`, `--tag`, `--status`

Exact-match filtering on frontmatter fields. Fast, deterministic, no ranking.

```bash
python -m tools.doc_index --scope auth --tag jwt
python -m tools.doc_index --status draft --json
```

### Fuzzy Search — `--search`

Ranks docs by fuzzy string similarity across title, tags, scope, and description. Good for known terms and partial matches.

```bash
python -m tools.doc_index --search "creature prefab"
```

### Semantic Search — `--semantic`

Uses embedding cosine similarity (with TF-IDF fallback if embeddings aren't built). Good for conceptual queries in natural language.

```bash
python -m tools.doc_index --semantic "how does the genetics system work"
```

### Hybrid Fusion Search — `--query` (Recommended)

Runs all available signals simultaneously and fuses them via Reciprocal Rank Fusion (RRF). This is the recommended search mode for agents — it removes the guesswork of choosing between fuzzy and semantic search.

```bash
# Basic fusion search
python -m tools.doc_index --query "how creatures breed" --project-dir ../EcoSim

# With JSON output (recommended for agents)
python -m tools.doc_index --query "resource allocation" --json

# With graph expansion — pull in linked neighbors
python -m tools.doc_index --query "CreatureManager" --expand --json

# Tuning
python -m tools.doc_index --query "genetics" --top 20 --rrf-k 40
```

#### How It Works

1. **Fuzzy signal** — string similarity on title, tags, scope, description
2. **TF-IDF signal** — cosine similarity on tokenised document content
3. **Embedding signal** — dense vector cosine similarity (if embeddings are built)

Each signal ranks the full corpus independently. RRF assigns each doc a score based on its rank position across all signals:

```
rrf_score = sum(1 / (k + rank)) for each signal where the doc appears
```

The `k` constant (default 60) controls how much top-rank positions are amplified. Scores are normalised to 0-1, then blended with document importance: `final = rrf_norm * 0.7 + importance * 0.3`.

#### Graceful Degradation

| Embeddings built? | Signals fused |
|---|---|
| Yes (fastembed installed + `--build --embeddings` run) | fuzzy + TF-IDF + embedding |
| No | fuzzy + TF-IDF (stderr note about missing embeddings) |
| Nothing built | Error: "No index found. Run with --build first." |

#### JSON Output Shape

```json
{
  "path": "docs/technical/design/coevolution.md",
  "title": "Creature-Plant Coevolution Design",
  "description": "...",
  "tags": ["genetics", "design"],
  "scope": [],
  "_importance": 0.45,
  "_score": 0.641,
  "_match": 0.81,
  "_rrf_raw": 0.047123,
  "_signals": {"embedding": 0.81, "tfidf": 0.27, "fuzzy": 0.15},
  "_expanded": false
}
```

| Field | Meaning |
|-------|---------|
| `_score` | Final ranked score (0-1), importance-blended |
| `_match` | Best raw match score from any single signal |
| `_rrf_raw` | Raw RRF score before normalisation |
| `_signals` | Per-signal match scores — shows which signals contributed |
| `_expanded` | `true` if this doc was pulled in via `--expand` graph traversal |
| `_via` | (Expanded docs only) Path of the seed doc that linked to this one |

#### Graph Expansion — `--expand`

When used with `--query`, `--expand` takes the top 5 fused results and pulls in their 1-hop explicit graph neighbors. Expanded docs get a damped score (`seed_score * 0.5`) and are marked with `_expanded: true` and `_via: seed_path`.

This is useful for discovery — if a search finds a design doc, `--expand` will surface the API reference and implementation docs that the design doc links to.

## Graph & Reading Order

### Related Docs — `--related`

BFS traversal from a starting document through the graph:

```bash
python -m tools.doc_index --related docs/technical/design/coevolution.md --depth 2
```

### Graph Dump — `--graph`

Full adjacency graph as JSON (explicit links, shared scope, shared tags):

```bash
python -m tools.doc_index --graph --json
```

### Reading Order — `--reading-order`

Topological sort on explicit links — linked-to docs appear before docs that link to them. Works with any search mode:

```bash
python -m tools.doc_index --query "genetics system" --reading-order
```

## CLI Reference

| Flag | Description |
|------|-------------|
| `--build` | Scan docs and rebuild the index |
| `--embeddings` | Build local embeddings via FastEmbed (use with `--build`) |
| `--discover` | Show index summary: scopes, tags, statuses |
| `--scope SCOPE` | Filter by scope |
| `--tag TAG` | Filter by tag |
| `--status STATUS` | Filter by status |
| `--search QUERY` | Fuzzy search |
| `--semantic QUERY` | Semantic search (embeddings or TF-IDF fallback) |
| `--query QUERY` | Hybrid fusion search (recommended) |
| `--expand` | Include 1-hop graph neighbors (use with `--query`) |
| `--rrf-k INT` | RRF k constant (default: 60) |
| `--related PATH` | Show docs related to a file |
| `--depth INT` | Max hops for `--related` (default: 1) |
| `--graph` | Dump full document graph as JSON |
| `--reading-order` | Sort results by dependency order |
| `--top INT` | Max results (default: 10) |
| `--json` | Output as JSON instead of table |
| `--project-dir PATH` | Project root (auto-detected if omitted) |

## Agent Integration Patterns

### Recommended: `--query` for All Search

Agents should default to `--query` with `--json` for search tasks. It handles every query shape — exact terms, partial names, natural language questions — without needing to choose a search mode:

```bash
# Agent doesn't need to decide: is this a keyword or a concept?
python -m tools.doc_index --query "CreatureManager" --json
python -m tools.doc_index --query "how does breeding work" --json
python -m tools.doc_index --query "resource allocation framework" --json
```

The `_signals` dict in the response tells the agent which signals contributed, which can inform follow-up searches.

### Discovery Workflow

```bash
# 1. What's in this project?
python -m tools.doc_index --discover --json

# 2. Find relevant docs
python -m tools.doc_index --query "authentication" --expand --json

# 3. Get reading order for the results
python -m tools.doc_index --query "authentication" --reading-order --json
```

### Filtering for Known Categories

When the agent knows the exact scope or tag, filtering is faster and more precise than search:

```bash
python -m tools.doc_index --scope api --tag security --json
```

## Benchmarks: Fusion vs Individual Signals

The following comparisons were run against the [EcoSim](https://github.com/GTFerguson/EcoSim) documentation corpus (30+ docs covering game design, technical architecture, API references, and user guides).

### Query: "how creatures breed"

| Rank | Fusion | Fuzzy only | Semantic only |
|------|--------|------------|---------------|
| 1 | Creature-Plant Coevolution Design (0.791) | Organisms API Reference (0.797) | Creature-Plant Coevolution Design (0.707) |
| 2 | Understanding Creatures (0.766) | Creature Behavior State System (0.716) | Organisms API Reference (0.682) |
| 3 | The Ark - Creature Collection RPG (0.719) | Ecosystem & Creature Behavior Improvements (0.705) | Genetics System Architecture (0.676) |

Fusion surfaced **4 docs that neither signal found in its top 10 alone**: `creatures/needs.md`, `environmental-adaptation.md`, `dominion-tribal.md`, and `getting-started.md`. These ranked okay-but-not-top-10 in multiple signals individually — RRF's cross-signal agreement boosted them above single-signal favorites.

### Query: "resource allocation"

| Mode | #1 Result | Score |
|------|-----------|-------|
| **Fusion** | Universal Resource Allocation Framework | **0.856** |
| Fuzzy | Universal Resource Allocation Framework | 0.821 |
| Semantic | Universal Resource Allocation Framework | 0.662 |

All three agree on the top result, but fusion scores it higher (0.856) than either signal alone. Fusion's #2 is Expression API Reference — a doc that fuzzy ranked #8 and semantic ranked #7. Cross-signal agreement promoted it.

### Query: "getting started tutorial"

| Mode | #1 Result | Score |
|------|-----------|-------|
| **Fusion** | Getting Started with the Genetics System | **0.906** |
| Fuzzy | Extending the Genetics System | 0.815 |
| Semantic | Getting Started with the Genetics System | 0.677 |

Fuzzy got the wrong #1 (it matched "Extending" over "Getting Started" due to similar character overlap). Semantic got it right but scored it low. Fusion combined both signals and confidently put the right doc at #1 with the highest score of any mode.

### Signal Contribution Analysis: "what happens when an organism dies"

```
Score  embedding  fuzzy  tfidf  Title
0.815  0.619      0.659  0.013  Organisms API Reference
0.775  0.621      0.700  0.063  Organism System Design
0.774  0.575      0.400  0.052  Extending the Genetics System
0.765  0.558      0.350  0.065  Genetics System Architecture
0.762  0.646      0.625  0.111  Environmental Adaptation
```

No single signal dominates. Fuzzy leads on some docs (catching "organism" in titles), embeddings lead on others (understanding the death/lifecycle concept), and TF-IDF provides tiebreaker signal from body text. This is the core value of fusion — each signal compensates for the others' blind spots.

### Why Fusion Wins

1. **No mode selection needed** — agents don't have to guess whether a query is a keyword lookup or a conceptual question
2. **Cross-signal agreement** — docs that rank well in multiple signals get promoted, surfacing results no single signal would prioritize
3. **Robust to query style** — exact terms, partial matches, and natural language all work through a single flag
4. **Transparent** — `_signals` shows exactly which signals contributed and how much, supporting agent reasoning about result quality
