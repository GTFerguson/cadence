"""Filter engine and output formatters."""

import json


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

    path_w = max(len(d['path']) for d in docs)
    title_w = max(len(d.get('title') or '') for d in docs)
    path_w = max(path_w, 4)
    title_w = max(title_w, 5)

    header = f"{'Path':<{path_w}}  {'Title':<{title_w}}  {'Scope':<20}  {'Status':<12}"
    sep = '-' * len(header)
    lines = [header, sep]

    for d in docs:
        path = d['path']
        title = d.get('title') or ''
        scope = ', '.join(d.get('scope') or [])
        status = d.get('status') or ''
        lines.append(f"{path:<{path_w}}  {title:<{title_w}}  {scope:<20}  {status:<12}")

    lines.append(f"\n{len(docs)} document(s) found.")
    return '\n'.join(lines)


def format_discover(index: dict) -> str:
    """Format index metadata as a human-readable summary."""
    meta = index.get('meta', {})
    count = index.get('count', 0)
    generated = index.get('generated', 'unknown')

    lines = [
        'Documentation Index Summary',
        '=' * 28,
        f'  Documents: {count}',
        f'  Generated: {generated}',
        '',
    ]

    scopes = meta.get('scopes', [])
    if scopes:
        lines.append(f'  Scopes ({len(scopes)}): {", ".join(scopes)}')

    tags = meta.get('tags', [])
    if tags:
        lines.append(f'  Tags ({len(tags)}):   {", ".join(tags)}')

    statuses = meta.get('statuses', [])
    if statuses:
        lines.append(f'  Statuses: {", ".join(statuses)}')

    if not scopes and not tags and not statuses:
        lines.append('  No metadata found. Add frontmatter to your docs.')

    return '\n'.join(lines)
