# Documentation Search

When working in a project with a doc-index, use it to find relevant documentation before diving into unfamiliar code.

## Commands

```bash
# Find docs relevant to a code file
python -m tools.doc_index --context path/to/file.py --json

# Search docs by concept or keyword
python -m tools.doc_index --query "authentication flow" --json

# See what's indexed
python -m tools.doc_index --discover --json
```

## When to Use

- **Opening a code file** — run `--context` to get design docs, specs, and guides for that file
- **Unfamiliar area** — run `--query` to search by concept before reading code
- **Orientation** — run `--discover` to see what scopes, tags, and topics exist

## Availability

Look for `.cade/doc-index.json` or `tools/doc_index/` in the project. If neither exists, run `python -m tools.doc_index --build` first.
