#!/usr/bin/env python3
"""
doc-index: Build and query a frontmatter-based documentation index.

Scans markdown files for YAML frontmatter, extracts metadata (title, scope,
status, tags, dates), and writes a static JSON index. Supports filtering by
scope, tag, and status for quick discovery by humans and agents alike.

Zero external dependencies — uses only Python stdlib.

Usage:
    python tools/doc-index.py --build
    python tools/doc-index.py --scope perspective --tag homography
    python tools/doc-index.py --build --scope all --json
    python tools/doc-index.py --status draft
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# ── Frontmatter parser (no PyYAML dependency) ──────────────────────────────

FRONTMATTER_FENCE = re.compile(r'^---\s*$')

# Matches: key: value (with optional quotes)
KV_PATTERN = re.compile(r'^(\w[\w-]*)\s*:\s*(.*)$')

# Matches: [item1, item2, "item 3"] — bracket list on a single line
BRACKET_LIST = re.compile(r'^\[(.+)\]$')


def parse_bracket_list(raw: str) -> list:
    """Parse a YAML-style bracket list into Python list of strings."""
    items = []
    for item in re.split(r',\s*', raw):
        item = item.strip().strip('"').strip("'")
        if item:
            items.append(item)
    return items


def parse_frontmatter(text: str) -> dict | None:
    """Extract YAML frontmatter from markdown text.

    Handles:
      - Bare values: status: in-progress
      - Bracket lists: scope: [perspective, shot-detection]
      - Quoted strings: title: "006: Goal Decomposition"
      - Missing frontmatter: returns None
    """
    lines = text.split('\n')

    if not lines or not FRONTMATTER_FENCE.match(lines[0]):
        return None

    meta = {}
    for line in lines[1:]:
        if FRONTMATTER_FENCE.match(line):
            break

        match = KV_PATTERN.match(line)
        if not match:
            continue

        key = match.group(1)
        value = match.group(2).strip()

        # Strip surrounding quotes
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        # Check for bracket list
        bracket = BRACKET_LIST.match(value)
        if bracket:
            meta[key] = parse_bracket_list(bracket.group(1))
        else:
            meta[key] = value

    return meta if meta else None


# ── Config loader (simple line-based, no YAML dependency) ──────────────────

DEFAULT_CONFIG = {
    'scan': ['docs/', 'lib/docs/'],
    'exclude': ['node_modules/', '.git/'],
    'output': '.doc-index.json',
}


def load_config(project_root: Path) -> dict:
    """Load .doc-index.yaml config using line-based parsing."""
    config_path = project_root / '.doc-index.yaml'
    if not config_path.exists():
        return DEFAULT_CONFIG

    config = {}
    current_key = None
    current_list = None

    with open(config_path) as f:
        for line in f:
            line = line.rstrip('\n')

            # Skip empty lines and comments
            if not line.strip() or line.strip().startswith('#'):
                if current_key and current_list is not None:
                    config[current_key] = current_list
                    current_key = None
                    current_list = None
                continue

            # List item under a key
            if line.startswith('  - ') and current_key:
                current_list.append(line.strip()[2:].strip())
                continue

            # Key-value pair
            if ':' in line and not line.startswith(' '):
                # Save previous list if any
                if current_key and current_list is not None:
                    config[current_key] = current_list

                key, _, value = line.partition(':')
                key = key.strip()
                value = value.strip()

                if value:
                    config[key] = value
                    current_key = None
                    current_list = None
                else:
                    current_key = key
                    current_list = []

    # Final list
    if current_key and current_list is not None:
        config[current_key] = current_list

    # Apply defaults for missing keys
    for k, v in DEFAULT_CONFIG.items():
        if k not in config:
            config[k] = v

    return config


# ── Index builder ──────────────────────────────────────────────────────────

def should_exclude(path: Path, excludes: list) -> bool:
    """Check if a path matches any exclusion pattern."""
    path_str = str(path)
    return any(exc in path_str for exc in excludes)


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

            docs.append({
                'path': rel_path,
                'title': title,
                'scope': scope,
                'status': status,
                'tags': tags,
                'updated': updated or created,
            })

    return docs


def build_index(project_root: Path, config: dict) -> dict:
    """Build the full index and write to output file."""
    docs = scan_docs(project_root, config)
    index = {
        'generated': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'count': len(docs),
        'docs': docs,
    }

    output_path = project_root / config.get('output', '.doc-index.json')
    with open(output_path, 'w') as f:
        json.dump(index, f, indent=2)

    return index


# ── Query engine ───────────────────────────────────────────────────────────

def load_index(project_root: Path, config: dict) -> dict | None:
    """Load existing index from disk."""
    output_path = project_root / config.get('output', '.doc-index.json')
    if not output_path.exists():
        return None
    with open(output_path) as f:
        return json.load(f)


def filter_docs(docs: list, scope: str = None, tag: str = None,
                status: str = None) -> list:
    """Filter docs by scope, tag, and/or status."""
    results = docs

    if scope:
        results = [
            d for d in results
            if d.get('scope') and scope in d['scope']
        ]

    if tag:
        results = [
            d for d in results
            if d.get('tags') and tag in d['tags']
        ]

    if status:
        results = [
            d for d in results
            if d.get('status') == status
        ]

    return results


def format_table(docs: list) -> str:
    """Format docs as a human-readable table."""
    if not docs:
        return "No matching documents found."

    # Column widths
    path_w = max(len(d['path']) for d in docs)
    title_w = max(len(d.get('title') or '') for d in docs)
    path_w = max(path_w, 4)
    title_w = max(title_w, 5)

    # Cap widths for readability
    path_w = min(path_w, 60)
    title_w = min(title_w, 40)

    header = f"{'Path':<{path_w}}  {'Title':<{title_w}}  {'Scope':<20}  {'Status':<12}"
    sep = '-' * len(header)
    lines = [header, sep]

    for d in docs:
        path = d['path'][:path_w]
        title = (d.get('title') or '')[:title_w]
        scope = ', '.join(d.get('scope') or [])[:20]
        status = (d.get('status') or '')[:12]
        lines.append(f"{path:<{path_w}}  {title:<{title_w}}  {scope:<20}  {status:<12}")

    lines.append(f"\n{len(docs)} document(s) found.")
    return '\n'.join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────

def find_project_root() -> Path:
    """Walk up from CWD to find a directory containing .doc-index.yaml or .git."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / '.doc-index.yaml').exists():
            return parent
        if (parent / '.git').exists():
            return parent
    return cwd


def main():
    parser = argparse.ArgumentParser(
        description='Build and query a frontmatter-based documentation index.',
        prog='doc-index',
    )
    parser.add_argument('--build', action='store_true',
                        help='Scan docs and rebuild the index')
    parser.add_argument('--scope', type=str,
                        help='Filter by scope (e.g., perspective, all)')
    parser.add_argument('--tag', type=str,
                        help='Filter by tag')
    parser.add_argument('--status', type=str,
                        help='Filter by status (e.g., draft, completed)')
    parser.add_argument('--json', action='store_true',
                        help='Output as JSON instead of table')
    parser.add_argument('--project-dir', type=str,
                        help='Project root directory (auto-detected if omitted)')

    args = parser.parse_args()

    if not args.build and not args.scope and not args.tag and not args.status:
        parser.print_help()
        sys.exit(1)

    project_root = Path(args.project_dir) if args.project_dir else find_project_root()
    config = load_config(project_root)

    if args.build:
        index = build_index(project_root, config)
        output_path = project_root / config.get('output', '.doc-index.json')
        print(f"Indexed {index['count']} documents → {output_path}")

        if not (args.scope or args.tag or args.status):
            return

    # Load index for querying
    index = load_index(project_root, config)
    if not index:
        print("No index found. Run with --build first.", file=sys.stderr)
        sys.exit(1)

    results = filter_docs(index['docs'],
                          scope=args.scope, tag=args.tag, status=args.status)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(format_table(results))


if __name__ == '__main__':
    main()
