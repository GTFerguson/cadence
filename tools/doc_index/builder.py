"""Index builder — scans docs, extracts frontmatter and descriptions."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .parser import parse_frontmatter, strip_frontmatter, FRONTMATTER_FENCE
from .graph import extract_links, build_graph


def should_exclude(path: Path, excludes: list) -> bool:
    """Check if a path matches any exclusion pattern."""
    path_str = str(path)
    return any(exc in path_str for exc in excludes)


def extract_description(text: str, max_len: int = 200) -> str | None:
    """Extract first meaningful paragraph from markdown body as description.

    Skips headings, code fences, and blank lines. Returns None if no
    suitable paragraph found.
    """
    body = strip_frontmatter(text)
    lines = body.split('\n')

    paragraph_lines = []
    for line in lines:
        stripped = line.strip()

        if not stripped:
            if paragraph_lines:
                break
            continue

        # Skip headings and code fences
        if stripped.startswith('#') or stripped.startswith('```'):
            if paragraph_lines:
                break
            continue

        # Skip images, HTML comments, frontmatter-like lines
        if stripped.startswith('![') or stripped.startswith('<!--'):
            if paragraph_lines:
                break
            continue

        paragraph_lines.append(stripped)

    if not paragraph_lines:
        return None

    desc = ' '.join(paragraph_lines)
    if len(desc) > max_len:
        desc = desc[:max_len].rsplit(' ', 1)[0] + '...'
    return desc


def compute_meta(docs: list) -> dict:
    """Aggregate unique scopes, tags, and statuses from all docs."""
    scopes = sorted({s for d in docs for s in (d.get('scope') or [])})
    tags = sorted({t for d in docs for t in (d.get('tags') or [])})
    statuses = sorted({d['status'] for d in docs if d.get('status')})
    return {'scopes': scopes, 'tags': tags, 'statuses': statuses}


def scan_docs(project_root: Path, config: dict) -> list:
    """Walk configured directories and extract frontmatter from .md files."""
    docs = []
    excludes = config.get('exclude', [])

    for scan_dir in config.get('scan', []):
        root = project_root / scan_dir
        if not root.exists():
            continue

        for md_path in sorted(root.rglob('*.md')):
            if should_exclude(md_path, excludes):
                continue

            rel_path = str(md_path.relative_to(project_root))

            try:
                text = md_path.read_text(encoding='utf-8', errors='replace')
            except (OSError, PermissionError):
                continue

            meta = parse_frontmatter(text)

            # Normalise scope/tags to lists
            scope = meta.get('scope') if meta else None
            if isinstance(scope, str):
                scope = [scope]

            tags = meta.get('tags') if meta else None
            if isinstance(tags, str):
                tags = [tags]

            title = (meta.get('title') if meta else None) or md_path.stem
            status = meta.get('status') if meta else None
            updated = meta.get('updated') if meta else None
            created = meta.get('created') if meta else None
            description = (meta.get('description') if meta else None) \
                or extract_description(text)
            raw_links = extract_links(text, meta)

            docs.append({
                'path': rel_path,
                'title': title,
                'description': description,
                'scope': scope,
                'status': status,
                'tags': tags,
                'updated': updated or created,
                '_raw_links': raw_links,
            })

    return docs


def build_index(project_root: Path, config: dict) -> dict:
    """Build the full index and write to output file."""
    docs = scan_docs(project_root, config)
    meta = compute_meta(docs)
    graph = build_graph(docs)

    # Add resolved links to each doc, strip internal _raw_links
    for doc in docs:
        doc['links'] = graph.get(doc['path'], {})
        doc.pop('_raw_links', None)

    index = {
        'version': 2,
        'generated': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'count': len(docs),
        'meta': meta,
        'docs': docs,
        'graph': graph,
    }

    output_path = project_root / config.get('output', '.doc-index.json')
    with open(output_path, 'w') as f:
        json.dump(index, f, indent=2)

    return index


def load_index(project_root: Path, config: dict) -> dict | None:
    """Load existing index from disk."""
    output_path = project_root / config.get('output', '.doc-index.json')
    if not output_path.exists():
        return None
    with open(output_path) as f:
        return json.load(f)
