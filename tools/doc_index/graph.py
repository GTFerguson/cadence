"""Document graph — explicit links, implicit edges, importance, reading order."""

import re
from collections import deque
from pathlib import Path

# Link patterns for body text detection
WIKI_LINK_RE = re.compile(r'\[\[([^\]|#]+)(?:[#|][^\]]+)?\]\]')
MD_LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+\.md(?:#[^)]*)?)\)')
CODE_BLOCK_RE = re.compile(r'```[\s\S]*?```')
INLINE_CODE_RE = re.compile(r'`[^`]+`')


def extract_links(text: str, frontmatter: dict | None) -> list[str]:
    """Extract document references from frontmatter and body text.

    Detects:
      - frontmatter `links:` field
      - [[wiki-links]] in body
      - [text](path.md) links in body
    Skips links inside code blocks.
    """
    links = []

    # From frontmatter
    if frontmatter and 'links' in frontmatter:
        fm_links = frontmatter['links']
        if isinstance(fm_links, str):
            fm_links = [fm_links]
        links.extend(fm_links)

    # Strip code blocks before scanning body
    body = CODE_BLOCK_RE.sub('', text)
    body = INLINE_CODE_RE.sub('', body)

    for match in WIKI_LINK_RE.finditer(body):
        links.append(match.group(1).strip())

    for match in MD_LINK_RE.finditer(body):
        links.append(match.group(2).split('#')[0].strip())

    return links


def resolve_link(target: str, source_path: str, by_path: dict,
                 by_stem: dict) -> str | None:
    """Resolve a link target to an indexed doc path.

    Tries in order:
      1. Exact path match
      2. Relative path resolution from source doc's directory
      3. Bare name match against doc stems
    """
    # Exact match
    if target in by_path:
        return target

    # Relative path from source doc's directory
    source_dir = str(Path(source_path).parent)
    resolved = str(Path(source_dir) / target)
    # Normalise (handles ../ etc)
    resolved = str(Path(resolved))
    if resolved in by_path:
        return resolved

    # Bare stem match
    stem = Path(target).stem
    matches = by_stem.get(stem, [])
    if len(matches) == 1:
        return matches[0]

    return None


def build_graph(docs: list, exclude_scopes: set = None,
                shared_tag_threshold: int = 2) -> dict:
    """Build adjacency graph from explicit links and implicit edges.

    Edge types:
      - explicit: from frontmatter links field or detected body links
      - shared_scope: docs sharing scope values (excluding broad scopes like 'all')
      - shared_tags: docs sharing N+ tags (default 2, to avoid noise)
    """
    if exclude_scopes is None:
        exclude_scopes = {'all'}

    by_path = {d['path']: d for d in docs}
    by_stem = {}
    for d in docs:
        stem = Path(d['path']).stem
        by_stem.setdefault(stem, []).append(d['path'])

    graph = {}

    for doc in docs:
        path = doc['path']
        edges = {'explicit': [], 'shared_scope': [], 'shared_tags': []}

        # Explicit links (resolved from raw links stored during scan)
        for link_target in (doc.get('_raw_links') or []):
            resolved = resolve_link(link_target, path, by_path, by_stem)
            if resolved and resolved != path:
                edges['explicit'].append(resolved)

        # Shared scope
        doc_scopes = set(doc.get('scope') or []) - exclude_scopes
        if doc_scopes:
            for other in docs:
                if other['path'] == path:
                    continue
                other_scopes = set(other.get('scope') or []) - exclude_scopes
                if doc_scopes & other_scopes:
                    edges['shared_scope'].append(other['path'])

        # Shared tags (require threshold overlap to avoid noise)
        doc_tags = set(doc.get('tags') or [])
        if doc_tags:
            for other in docs:
                if other['path'] == path:
                    continue
                other_tags = set(other.get('tags') or [])
                if len(doc_tags & other_tags) >= shared_tag_threshold:
                    edges['shared_tags'].append(other['path'])

        # Deduplicate — higher-signal edge types take precedence
        explicit_set = set(edges['explicit'])
        scope_set = set(edges['shared_scope']) - explicit_set
        tag_set = set(edges['shared_tags']) - explicit_set - scope_set

        edges['explicit'] = sorted(explicit_set)
        edges['shared_scope'] = sorted(scope_set)
        edges['shared_tags'] = sorted(tag_set)

        graph[path] = edges

    return graph


NUMBERED_PREFIX = re.compile(r'^\d+[-_]')


def compute_importance(docs: list, graph: dict, config: dict = None) -> dict:
    """Score each doc 0.0–1.0 by combining inbound links, path signals, and metadata.

    Weights: inbound links 0.5, path signals 0.3, metadata 0.2.
    Returns {path: score} dict.
    """
    path_weights = {}
    if config and isinstance(config.get('path_weights'), dict):
        path_weights = config['path_weights']

    # Count inbound links per doc (weighted by edge type)
    inbound = {d['path']: 0.0 for d in docs}
    for path, edges in graph.items():
        for target in edges.get('explicit', []):
            if target in inbound:
                inbound[target] += 3.0
        for target in edges.get('shared_scope', []):
            if target in inbound:
                inbound[target] += 2.0
        for target in edges.get('shared_tags', []):
            if target in inbound:
                inbound[target] += 1.0

    max_inbound = max(inbound.values()) if inbound else 1.0
    if max_inbound == 0:
        max_inbound = 1.0

    scores = {}
    for doc in docs:
        path = doc['path']
        p = Path(path)

        # Inbound link score (0–1)
        link_score = inbound.get(path, 0) / max_inbound

        # Path signals (0–1)
        parts = p.parts
        # Depth: fewer segments = more foundational
        depth = max(len(parts) - 1, 0)  # subtract filename
        depth_score = 1.0 / (1 + depth)

        # README / index bonus
        stem = p.stem.lower()
        hub_bonus = 0.2 if stem in ('readme', 'index', 'overview') else 0.0

        # Numbered prefix bonus (01-architecture, 02-getting-started)
        numbered_bonus = 0.1 if NUMBERED_PREFIX.match(p.stem) else 0.0

        # Config-based path weights
        config_score = 0.0
        for pattern, weight in path_weights.items():
            if pattern in str(p):
                config_score = max(config_score, float(weight))

        path_score = min(depth_score + hub_bonus + numbered_bonus + config_score, 1.0)

        # Metadata signals (0–1)
        status = doc.get('status', '')
        status_score = 0.0
        if status in ('published', 'complete', 'implemented'):
            status_score = 1.0
        elif status in ('active', 'reference'):
            status_score = 0.8
        elif status in ('draft', 'proposed', 'planned'):
            status_score = 0.4
        elif status:
            status_score = 0.2

        desc_bonus = 0.3 if doc.get('description') else 0.0
        meta_score = min(status_score * 0.7 + desc_bonus, 1.0)

        # Weighted combination
        scores[path] = round(
            link_score * 0.5 + path_score * 0.3 + meta_score * 0.2,
            4
        )

    return scores


def topological_sort(docs: list, graph: dict, importance: dict) -> list:
    """Order docs by dependency: linked-to docs come before docs that link to them.

    Uses Kahn's algorithm on explicit links within the given doc subset.
    Breaks ties by importance (higher first). Handles cycles by falling
    back to importance ordering for cycle members.
    """
    paths = {d['path'] for d in docs}
    by_path = {d['path']: d for d in docs}

    # Build in-degree map and adjacency (only for docs in the subset)
    in_degree = {p: 0 for p in paths}
    forward = {p: [] for p in paths}  # p -> docs that p links to

    for p in paths:
        edges = graph.get(p, {})
        for target in edges.get('explicit', []):
            if target in paths:
                forward[p].append(target)
                in_degree[target] += 1

    # Kahn's algorithm with importance-ordered tie-breaking
    queue = sorted(
        [p for p in paths if in_degree[p] == 0],
        key=lambda p: importance.get(p, 0),
        reverse=True
    )
    result = []

    while queue:
        node = queue.pop(0)
        result.append(by_path[node])

        for target in forward[node]:
            in_degree[target] -= 1
            if in_degree[target] == 0:
                # Insert sorted by importance
                inserted = False
                for i, q in enumerate(queue):
                    if importance.get(target, 0) > importance.get(q, 0):
                        queue.insert(i, target)
                        inserted = True
                        break
                if not inserted:
                    queue.append(target)

    # Cycle members: any docs not yet in result, sorted by importance
    remaining = [by_path[p] for p in paths if p not in {d['path'] for d in result}]
    remaining.sort(key=lambda d: importance.get(d['path'], 0), reverse=True)
    result.extend(remaining)

    return result


def find_related(graph: dict, start_path: str, depth: int = 1) -> list[dict]:
    """BFS traversal from a starting doc, up to N hops."""
    visited = {start_path}
    current_level = [start_path]
    results = []

    for hop in range(1, depth + 1):
        next_level = []
        for path in current_level:
            edges = graph.get(path, {})
            for edge_type in ('explicit', 'shared_scope', 'shared_tags'):
                for target in edges.get(edge_type, []):
                    if target not in visited:
                        visited.add(target)
                        next_level.append(target)
                        results.append({
                            'path': target,
                            'relation': edge_type,
                            'hops': hop,
                            'via': path,
                        })
        current_level = next_level
        if not current_level:
            break

    return results


def format_related_table(results: list, start_path: str,
                         docs_by_path: dict) -> str:
    """Format related docs as a human-readable table."""
    if not results:
        return f"No related documents found for {start_path}."

    path_w = max(len(r['path']) for r in results)
    path_w = max(path_w, 4)

    lines = [
        f"Related to: {start_path}",
        '=' * (len(start_path) + 12),
        '',
    ]

    header = f"{'Hops':<5}  {'Relation':<14}  {'Path':<{path_w}}  {'Title'}"
    sep = '-' * len(header)
    lines.extend([header, sep])

    for r in results:
        hops = str(r['hops'])
        relation = r['relation']
        path = r['path']
        doc = docs_by_path.get(path, {})
        title = doc.get('title', '')
        lines.append(f"{hops:<5}  {relation:<14}  {path:<{path_w}}  {title}")

    lines.append(f"\n{len(results)} related document(s) found.")
    return '\n'.join(lines)
