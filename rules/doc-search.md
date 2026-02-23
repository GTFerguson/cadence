# Documentation Search

When working in a project with a doc-index, use it to find relevant documentation before diving into unfamiliar code.

## Quick Reference

```bash
# Hybrid search (recommended) — handles keywords, concepts, and natural language
python -m tools.doc_index --query "your search terms" --json

# With graph expansion — surfaces linked/related docs
python -m tools.doc_index --query "your search terms" --expand --json

# Browse what's indexed
python -m tools.doc_index --discover --json
```

## When to Search

- Before starting work on an unfamiliar area — find relevant design docs, API refs
- When a task mentions concepts you don't have context for
- When you need to understand how components relate to each other

## Reading the Results

JSON results include `_signals` showing which retrieval methods contributed (fuzzy, tfidf, embedding) and `_score` for overall relevance. Use `--expand` to pull in graph neighbors of top results — useful for discovering related docs that don't directly match the query.

## How to Know If Doc-Index Is Available

Look for `.cade/doc-index.json` or `tools/doc_index/` in the project. If neither exists, the project hasn't been set up for it — skip doc-index.
