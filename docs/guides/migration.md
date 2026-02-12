---
title: Migrating Existing Projects to CADE Brain
scope: [all]
created: 2026-02-07
status: published
tags: [migration, setup]
---

# Migration Guide

How to adopt CADE Brain in a project that already has its own conventions.

## Assessment

Before migrating, check what you already have:

| If you have... | Action |
|----------------|--------|
| `CLAUDE.md` | Setup skips it automatically (use `--force` to replace) |
| `~/.claude/rules/*.md` | Use `--no-rules` to keep yours |
| `docs/` structure | Setup only creates missing directories |
| `tools/doc-index.py` | Setup skips if file exists |
| `.doc-index.yaml` | Setup skips if file exists |

## Minimal Migration

For projects that already have mature conventions (like an established CLAUDE.md and rules), the minimal migration adds just the doc-index tooling:

```bash
git submodule add https://github.com/GTFerguson/cade-brain.git
./cade-brain/setup.sh --yes --no-rules
```

This gives you:
- `tools/doc-index.py` symlinked from cade-brain
- `.doc-index.yaml` config
- `.doc-index.json` added to `.gitignore`
- Any missing `docs/` subdirectories created

Your existing `CLAUDE.md` and rules are untouched.

## Full Migration

For projects adopting CADE Brain conventions from scratch:

```bash
git submodule add https://github.com/GTFerguson/cade-brain.git
./cade-brain/setup.sh
```

Then customize the generated `CLAUDE.md` — see the [Getting Started Guide](getting-started.md).

## Replacing Rules with Symlinks

If you have rules files that originated from CADE Brain (or a predecessor project) and want to switch to symlinks for automatic updates:

```bash
# Check current rules
ls -la ~/.claude/rules/

# Remove the regular files
rm ~/.claude/rules/markdown-formatting.md
rm ~/.claude/rules/test-driven-debugging.md
rm ~/.claude/rules/code-comments.md

# Re-run setup to create symlinks
./cade-brain/setup.sh --no-rules  # skip if you only want to relink rules
# OR manually:
ln -s /path/to/cade-brain/rules/markdown-formatting.md ~/.claude/rules/
ln -s /path/to/cade-brain/rules/test-driven-debugging.md ~/.claude/rules/
ln -s /path/to/cade-brain/rules/code-comments.md ~/.claude/rules/
```

## Adding Frontmatter to Existing Docs

The doc-index tool only indexes files with YAML frontmatter. To add frontmatter to existing docs:

```yaml
---
title: Your Document Title
scope: [relevant-scope]
created: 2026-02-07
status: published
tags: [relevant, tags]
---
```

Required fields: `title`, `scope`. Recommended: `created` or `updated`, `status`, `tags`.

You can add frontmatter incrementally — the index simply skips files without it.

## Updating the Doc-Index Config

If your docs live in non-standard directories, edit `.doc-index.yaml`:

```yaml
scan:
  - docs/
  - lib/docs/
  - wiki/           # add custom directories
  - src/docs/

exclude:
  - node_modules/
  - .git/
  - vendor/          # add custom exclusions

output: .doc-index.json
```

## Submodule Maintenance

Update CADE Brain to the latest version:

```bash
cd cade-brain
git pull origin main
cd ..
git add cade-brain
git commit -m "chore: update cade-brain submodule"
```

Since rules and doc-index are symlinked, updates take effect immediately.
