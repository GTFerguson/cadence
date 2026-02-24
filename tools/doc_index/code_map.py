"""Code-to-doc mapping — reverse index from code files to relevant documentation.

Scans doc bodies for references to project code files (markdown links, backtick
paths, bare path mentions) and builds a reverse map: code_file → [doc_paths].
"""

import re
from pathlib import Path, PurePosixPath

from .parser import strip_frontmatter

# Patterns for extracting file references from doc content
# Markdown links: [text](path/to/file.ext) or [text](../../path/to/file.ext:42)
MD_LINK_PATH_RE = re.compile(
    r'\[[^\]]*\]\(([^)]+?\.[\w]+)(?::\d+)?\)'
)

# Backtick-wrapped paths: `path/to/file.ext` or `file.ext`
BACKTICK_PATH_RE = re.compile(
    r'`([^`]*?/[^`]*?\.[\w]+)`'
    r'|'
    r'`([^`\s]+\.(?:py|js|ts|tsx|jsx|rs|go|cpp|hpp|c|h|java|rb|sh|toml|yaml|yml|json|css|scss|html|vue|svelte))`'
)

# Bare paths in prose: word boundaries around path-like strings with slashes
# Requires at least one / to avoid matching bare words
BARE_PATH_RE = re.compile(
    r'(?<![(\[`])(\b[\w][\w.-]*/[\w./-]+\.[\w]+)\b(?![\])`])'
)

# @see references (common in C++/Java doc comments)
SEE_REF_RE = re.compile(
    r'@see\s+([^\s,]+\.[\w]+)'
)

# Code fence detection (to handle differently, not skip)
CODE_FENCE_RE = re.compile(r'^```', re.MULTILINE)

# Strip line numbers from paths: file.ext:42 → file.ext
LINE_NUM_RE = re.compile(r':(\d+)(?:-\d+)?$')

# Common non-code extensions to ignore
IGNORE_EXTENSIONS = {
    '.md', '.txt', '.csv', '.svg', '.png', '.jpg', '.jpeg', '.gif',
    '.ico', '.pdf', '.lock', '.map', '.min', '.log', '.env',
}

# Common false-positive filenames
IGNORE_NAMES = {
    'package.json', 'package-lock.json', 'tsconfig.json',
    'Cargo.toml', 'Cargo.lock', 'Makefile', 'CMakeLists.txt',
    '.gitignore', '.gitmodules', '.editorconfig',
}


def _should_exclude(path: Path, excludes: list) -> bool:
    """Check if any path component matches an exclusion pattern."""
    parts = set(path.parts)
    for exc in excludes:
        dirname = exc.rstrip('/')
        if dirname in parts:
            return True
    return False


def collect_project_files(project_root: Path, excludes: list) -> dict:
    """Walk project and collect all non-markdown files.

    Returns:
        by_path: {relative_path: True} for exact matching
        by_name: {filename: [relative_paths]} for bare name matching
    """
    by_path = {}
    by_name = {}

    for path in project_root.rglob('*'):
        if not path.is_file():
            continue
        if _should_exclude(path, excludes):
            continue

        rel = str(path.relative_to(project_root))
        ext = path.suffix.lower()

        if ext in IGNORE_EXTENSIONS:
            continue
        if path.name in IGNORE_NAMES:
            continue

        by_path[rel] = True
        by_name.setdefault(path.name, []).append(rel)

    return by_path, by_name


def _strip_line_number(ref: str) -> str:
    """Remove trailing :line_number from a reference."""
    return LINE_NUM_RE.sub('', ref)


def _normalise_path(ref: str) -> str:
    """Normalise a path reference: strip line numbers, resolve ../ segments."""
    ref = _strip_line_number(ref)
    # Use PurePosixPath to handle ../  resolution
    try:
        parts = PurePosixPath(ref).parts
        # Rebuild without redundant segments
        resolved = []
        for p in parts:
            if p == '..':
                if resolved:
                    resolved.pop()
            elif p != '.':
                resolved.append(p)
        return '/'.join(resolved) if resolved else ref
    except (ValueError, TypeError):
        return ref


def extract_code_refs(text: str, doc_path: str) -> list[dict]:
    """Extract code file references from a document's body text.

    Returns list of {ref: str, type: str} where type is one of:
    'md_link', 'backtick', 'bare_path', 'see_ref'
    """
    body = strip_frontmatter(text)
    refs = []
    seen = set()

    def _add(raw_ref: str, ref_type: str):
        cleaned = _strip_line_number(raw_ref.strip())
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            refs.append({'ref': cleaned, 'type': ref_type})

    # Markdown links
    for m in MD_LINK_PATH_RE.finditer(body):
        path = m.group(1)
        # Skip URLs
        if path.startswith(('http://', 'https://', '#', 'mailto:')):
            continue
        # Skip other .md files (those are doc-to-doc links, handled by graph)
        if path.endswith('.md'):
            continue
        _add(path, 'md_link')

    # Backtick-wrapped paths
    for m in BACKTICK_PATH_RE.finditer(body):
        path = m.group(1) or m.group(2)
        if not path or path.endswith('.md'):
            continue
        _add(path, 'backtick')

    # @see references
    for m in SEE_REF_RE.finditer(body):
        path = m.group(1)
        if path.endswith('.md'):
            continue
        _add(path, 'see_ref')

    # Bare paths (lowest confidence, only those with slashes)
    for m in BARE_PATH_RE.finditer(body):
        path = m.group(1)
        if path.endswith('.md'):
            continue
        # Skip things that look like URLs or version strings
        if '://' in path or path.startswith('v') and '.' in path[:4]:
            continue
        _add(path, 'bare_path')

    return refs


def resolve_ref(ref: str, doc_path: str, by_path: dict,
                by_name: dict) -> tuple[str | None, str]:
    """Resolve a code reference to an actual project file.

    Tries in order:
    1. Exact path match
    2. Relative path resolution from doc's directory
    3. Bare filename match (only if unambiguous)

    Returns (resolved_path, match_type) or (None, 'unresolved').
    """
    cleaned = _strip_line_number(ref)

    # 1. Exact match
    if cleaned in by_path:
        return cleaned, 'exact'

    # 2. Relative resolution from doc's directory
    doc_dir = str(PurePosixPath(doc_path).parent)
    resolved = _normalise_path(str(PurePosixPath(doc_dir) / cleaned))
    if resolved in by_path:
        return resolved, 'relative'

    # 3. Bare filename match
    name = PurePosixPath(cleaned).name
    matches = by_name.get(name, [])
    if len(matches) == 1:
        return matches[0], 'filename'

    return None, 'unresolved'


# Confidence scores by match quality
_MATCH_SCORES = {
    'exact': 1.0,
    'relative': 1.0,
    'filename': 0.6,
}

# Boost by reference type
_REF_SCORES = {
    'md_link': 1.0,
    'see_ref': 0.9,
    'backtick': 0.7,
    'bare_path': 0.5,
}


def build_code_map(docs: list, project_root: Path, config: dict) -> dict:
    """Build reverse index from code files to docs that reference them.

    Returns {code_path: [{doc: str, score: float, refs: int}]}
    sorted by score descending within each code file.
    """
    excludes = config.get('exclude', [])
    by_path, by_name = collect_project_files(project_root, excludes)

    # Forward map: doc → [(code_path, score)]
    # Then invert to: code → [doc entries]
    code_to_docs = {}

    for doc in docs:
        doc_path = doc['path']
        file_path = project_root / doc_path

        try:
            text = file_path.read_text(encoding='utf-8', errors='replace')
        except (OSError, PermissionError):
            continue

        refs = extract_code_refs(text, doc_path)
        if not refs:
            continue

        # Resolve and score each reference
        resolved_refs = {}  # code_path → best_score
        for ref_info in refs:
            resolved, match_type = resolve_ref(
                ref_info['ref'], doc_path, by_path, by_name
            )
            if resolved is None:
                continue

            score = _MATCH_SCORES.get(match_type, 0.5) * _REF_SCORES.get(ref_info['type'], 0.5)
            if resolved in resolved_refs:
                resolved_refs[resolved] = max(resolved_refs[resolved], score)
            else:
                resolved_refs[resolved] = score

        # Add to reverse index
        for code_path, score in resolved_refs.items():
            if code_path not in code_to_docs:
                code_to_docs[code_path] = []
            code_to_docs[code_path].append({
                'doc': doc_path,
                'score': round(score, 2),
            })

    # Sort each code file's docs by score
    for code_path in code_to_docs:
        code_to_docs[code_path].sort(key=lambda x: x['score'], reverse=True)

    return code_to_docs


def context_search(code_path: str, code_map: dict, docs_by_path: dict,
                   top: int = 10) -> list:
    """Find docs relevant to a code file path.

    Supports partial path matching — 'auth.py' will match
    'backend/auth.py' if it's the only match.
    """
    # Exact match first
    entries = code_map.get(code_path)

    # Partial match: try suffix matching
    if entries is None:
        matches = [k for k in code_map if k.endswith(code_path) or k.endswith('/' + code_path)]
        if len(matches) == 1:
            entries = code_map[matches[0]]
        elif len(matches) > 1:
            # Merge results from all matches, deduplicate
            seen = {}
            for m in matches:
                for entry in code_map[m]:
                    doc = entry['doc']
                    if doc not in seen or entry['score'] > seen[doc]['score']:
                        seen[doc] = entry
            entries = sorted(seen.values(), key=lambda x: x['score'], reverse=True)

    if not entries:
        return []

    results = []
    for entry in entries[:top]:
        doc = docs_by_path.get(entry['doc'])
        if doc:
            results.append({
                **doc,
                '_score': entry['score'],
                '_match': 'code_map',
            })

    return results
