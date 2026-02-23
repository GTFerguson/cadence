"""Fuzzy search and TF-IDF semantic search."""

import json
import math
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

from .parser import strip_frontmatter


STOPWORDS = frozenset({
    'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
    'has', 'have', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
    'should', 'may', 'might', 'this', 'that', 'these', 'those', 'it', 'its',
    'not', 'no', 'if', 'as', 'so', 'up', 'out', 'about', 'into', 'over',
    'after', 'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most',
    'other', 'some', 'such', 'than', 'too', 'very', 'can', 'just', 'also',
    'when', 'where', 'which', 'what', 'who', 'why', 'then', 'here', 'there',
    'only', 'your', 'you', 'we', 'our', 'they', 'them', 'their', 'use',
})


def fuzzy_search(docs: list, query: str, threshold: float = 0.2,
                 top: int = 10) -> list:
    """Rank docs by fuzzy relevance to query across all text fields.

    Searches title, tags, scopes, and description. Returns results
    sorted by score, highest first.
    """
    query_lower = query.lower()
    query_words = query_lower.split()
    scored = []

    for doc in docs:
        best_score = 0.0

        # Title matching
        title = (doc.get('title') or '').lower()
        if title:
            if query_lower in title:
                best_score = max(best_score, 0.95)
            else:
                ratio = SequenceMatcher(None, query_lower, title).ratio()
                best_score = max(best_score, ratio * 0.8)
                # Word-level matching
                for qw in query_words:
                    for tw in title.split():
                        wr = SequenceMatcher(None, qw, tw).ratio()
                        best_score = max(best_score, wr * 0.7)

        # Tag matching
        for tag in (doc.get('tags') or []):
            tag_lower = tag.lower()
            if query_lower == tag_lower:
                best_score = max(best_score, 0.95)
            elif query_lower in tag_lower or tag_lower in query_lower:
                best_score = max(best_score, 0.85)
            else:
                ratio = SequenceMatcher(None, query_lower, tag_lower).ratio()
                best_score = max(best_score, ratio * 0.7)

        # Scope matching
        for scope in (doc.get('scope') or []):
            scope_lower = scope.lower()
            if query_lower == scope_lower:
                best_score = max(best_score, 0.95)
            elif query_lower in scope_lower or scope_lower in query_lower:
                best_score = max(best_score, 0.85)
            else:
                ratio = SequenceMatcher(None, query_lower, scope_lower).ratio()
                best_score = max(best_score, ratio * 0.7)

        # Description matching — word-level hits
        desc = (doc.get('description') or '').lower()
        if desc and query_words:
            word_hits = sum(1 for w in query_words if w in desc)
            if word_hits > 0:
                desc_score = (word_hits / len(query_words)) * 0.75
                best_score = max(best_score, desc_score)

        if best_score >= threshold:
            scored.append({**doc, '_score': round(best_score, 3)})

    scored.sort(key=lambda d: d['_score'], reverse=True)
    return scored[:top]


def format_search_table(docs: list) -> str:
    """Format search results with score column."""
    if not docs:
        return "No matching documents found."

    path_w = max(len(d['path']) for d in docs)
    title_w = max(len(d.get('title') or '') for d in docs)
    path_w = max(path_w, 4)
    title_w = max(title_w, 5)

    header = f"{'Score':<6}  {'Path':<{path_w}}  {'Title':<{title_w}}  {'Scope':<20}"
    sep = '-' * len(header)
    lines = [header, sep]

    for d in docs:
        score = f"{d.get('_score', 0):.3f}"
        path = d['path']
        title = d.get('title') or ''
        scope = ', '.join(d.get('scope') or [])
        lines.append(f"{score:<6}  {path:<{path_w}}  {title:<{title_w}}  {scope:<20}")

    lines.append(f"\n{len(docs)} document(s) found.")
    return '\n'.join(lines)


# ── TF-IDF Semantic Search ─────────────────────────────────────────────────

def tokenize(text: str) -> list[str]:
    """Split text into lowercase tokens, removing stopwords."""
    tokens = re.findall(r'\b[a-z][a-z0-9_-]*\b', text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def build_tfidf(docs: list, project_root: Path) -> dict:
    """Build TF-IDF vectors for all docs.

    Combines title, description, tags, scope, and body text (first 2000 chars)
    for each document. Returns idf dict and per-doc sparse vectors.
    """
    corpus = []
    for doc in docs:
        parts = [doc.get('title', ''), doc.get('description', '')]
        parts.extend(doc.get('tags') or [])
        parts.extend(doc.get('scope') or [])

        doc_path = project_root / doc['path']
        if doc_path.exists():
            try:
                body = doc_path.read_text(encoding='utf-8', errors='replace')
                body = strip_frontmatter(body)[:2000]
                parts.append(body)
            except (OSError, PermissionError):
                pass

        corpus.append(tokenize(' '.join(parts)))

    # IDF: log(N / (1 + df)) + 1
    n = len(corpus)
    if n == 0:
        return {'idf': {}, 'vectors': {}}

    df = Counter()
    for tokens in corpus:
        df.update(set(tokens))

    idf = {word: math.log(n / (1 + count)) + 1 for word, count in df.items()}

    # TF-IDF vectors (sparse)
    vectors = {}
    for doc, tokens in zip(docs, corpus):
        if not tokens:
            continue
        tf = Counter(tokens)
        total = len(tokens)
        vec = {word: (count / total) * idf[word] for word, count in tf.items()}
        vectors[doc['path']] = vec

    return {'idf': idf, 'vectors': vectors}


def save_tfidf(tfidf_data: dict, output_path: Path):
    """Write TF-IDF sidecar file."""
    with open(output_path, 'w') as f:
        json.dump(tfidf_data, f)


def load_tfidf(output_path: Path) -> dict | None:
    """Load TF-IDF sidecar file."""
    if not output_path.exists():
        return None
    with open(output_path) as f:
        return json.load(f)


def cosine_similarity(v1: dict, v2: dict) -> float:
    """Compute cosine similarity between two sparse vectors."""
    common = set(v1) & set(v2)
    if not common:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in common)
    mag1 = math.sqrt(sum(v ** 2 for v in v1.values()))
    mag2 = math.sqrt(sum(v ** 2 for v in v2.values()))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


def semantic_search(query: str, tfidf_data: dict, docs: list,
                    top: int = 10) -> list:
    """Search using TF-IDF cosine similarity."""
    idf = tfidf_data.get('idf', {})
    vectors = tfidf_data.get('vectors', {})

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    query_tf = Counter(query_tokens)
    total = len(query_tokens)
    query_vec = {w: (c / total) * idf.get(w, 1.0) for w, c in query_tf.items()}

    results = []
    for doc in docs:
        vec = vectors.get(doc['path'])
        if not vec:
            continue
        sim = cosine_similarity(query_vec, vec)
        if sim > 0.01:
            results.append({**doc, '_score': round(sim, 4)})

    results.sort(key=lambda d: d['_score'], reverse=True)
    return results[:top]
