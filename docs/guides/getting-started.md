---
title: Getting Started with Cadence
scope: [all]
created: 2026-02-07
status: published
tags: [setup, guide]
---

# Getting Started with Cadence

This guide walks through setting up Cadence in a new or existing project.

## Prerequisites

- Python 3.10+
- Git
- Claude Code CLI

## Installation

### Option A: Git Submodule (Recommended)

Adding as a submodule keeps Cadence updatable and version-tracked:

```bash
cd your-project
git submodule add https://github.com/GTFerguson/cadence.git
./cadence/setup.sh
```

The setup script auto-detects submodule mode and resolves paths accordingly.

### Option B: Standalone Clone

For trying it out or using across multiple local projects:

```bash
git clone https://github.com/GTFerguson/cadence.git ~/tools/cadence
~/tools/cadence/setup.sh --project-dir /path/to/your/project
```

## What Setup Does

Running `setup.sh` performs these steps (all idempotent):

### 1. Documentation Structure

Creates the standard directory layout:

```
docs/
├── architecture/    ← system design + decision rationale
├── reference/       ← knowledge base (domain, techniques, foundations)
├── guides/          ← how-to documentation
│   └── tools/      ← tool index pointing to co-located docs
└── plans/           ← forward-looking ideas and roadmaps
```

### 2. CLAUDE.md Generation

Generates a `CLAUDE.md` from the template with your project name substituted. This file configures Claude Code's behavior for your project: commit conventions, documentation rules, workspace ownership, and scope tags.

Skipped if `CLAUDE.md` already exists (use `--force` to overwrite).

### 3. Rules Symlinks

Symlinks the three rules files into `~/.claude/rules/`:
- `markdown-formatting.md` — Obsidian compatibility
- `test-driven-debugging.md` — test-first bug investigation
- `code-comments.md` — meaningful comment conventions

These apply globally to all Claude Code sessions. Skip with `--no-rules` if you already have them or want to manage rules separately.

### 4. Doc-Index Tool

Symlinks `doc-index.py` into your project's `tools/` directory. This tool scans markdown files for YAML frontmatter and builds a queryable JSON index.

### 5. Configuration

Creates `.doc-index.yaml` with default scan directories and adds `.doc-index.json` to `.gitignore`.

## Customizing CLAUDE.md

After setup, edit `CLAUDE.md` to match your project:

1. **Project Structure** — Replace the template tree with your actual layout
2. **Ownership Table** — Add project-specific owned areas (feature dirs, pipeline dirs)
3. **Module Lifecycle** — Adjust if your project uses different maturity stages
4. **Additional Sections** — Add data paths, import conventions, training patterns as needed

## Using the Doc Index

### Adding Frontmatter

Add YAML frontmatter to your markdown docs:

```yaml
---
title: Authentication Architecture
scope: [auth, api]
created: 2026-02-07
status: published
tags: [jwt, oauth, security]
---
```

### Building the Index

```bash
python tools/doc-index.py --build
```

This scans all directories listed in `.doc-index.yaml` and writes `.doc-index.json`.

### Querying

```bash
# Hybrid fusion search (recommended — combines all signals automatically)
python -m tools.doc_index --query "how does authentication work" --json

# Filter by scope, tag, status
python -m tools.doc_index --scope auth
python -m tools.doc_index --tag security
python -m tools.doc_index --scope api --tag jwt --status published

# JSON output for piping
python -m tools.doc_index --scope all --json
```

### Agent Usage

Agents should default to `--query` with `--json` for search. It handles exact terms, partial names, and natural language questions through a single flag — no need to choose between fuzzy and semantic search.

For the full search mode reference, signal breakdown, and advanced features (graph expansion, reading order, RRF tuning), see [Doc Index Reference](doc-index.md).

## Setup Flags Reference

| Flag | Description |
|------|-------------|
| `--project-dir PATH` | Explicit project root (auto-detected if omitted) |
| `--project-name NAME` | Project name for CLAUDE.md (defaults to dir name) |
| `--yes` | Accept all defaults without prompting |
| `--force` | Overwrite existing CLAUDE.md |
| `--no-rules` | Skip rules symlink installation |
| `--dry-run` | Preview actions without making changes |
