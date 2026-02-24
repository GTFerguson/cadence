# Documentation Search

When working in a project with a doc-index, use it to find relevant documentation before diving into unfamiliar code.

## Quick Reference

```bash
# Find docs relevant to a code file you're working on
python -m tools.doc_index --context path/to/file.py --json

# Hybrid search — handles keywords, concepts, and natural language
python -m tools.doc_index --query "your search terms" --json

# With graph expansion — surfaces linked/related docs
python -m tools.doc_index --query "your search terms" --expand --json

# Browse what's indexed
python -m tools.doc_index --discover --json
```

## When to Search

- When opening or editing a code file — use `--context` to find relevant design docs, specs, and guides
- Before starting work on an unfamiliar area — use `--query` to search by concept
- When a task mentions concepts you don't have context for
- When you need to understand how components relate to each other

## Reading the Results

JSON results include `_signals` showing which retrieval methods contributed (fuzzy, tfidf, embedding) and `_score` for overall relevance. Use `--expand` to pull in graph neighbors of top results — useful for discovering related docs that don't directly match the query.

## How to Know If Doc-Index Is Available

Look for `.cade/doc-index.json` or `tools/doc_index/` in the project. If neither exists, try running `python -m tools.doc_index --build` first. If that fails, the project hasn't been set up for doc-index.
