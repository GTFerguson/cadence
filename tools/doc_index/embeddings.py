"""Local embeddings via FastEmbed for semantic search.

Uses BAAI/bge-small-en-v1.5 (384 dims, ~30MB) for real semantic matching.
Falls back gracefully when fastembed is not installed.
"""

import hashlib
import json
import math
from pathlib import Path

from .parser import strip_frontmatter

try:
    from fastembed import TextEmbedding
    FASTEMBED_AVAILABLE = True
except ImportError:
    FASTEMBED_AVAILABLE = False


def _doc_text(doc: dict, project_root: Path) -> str:
    """Combine doc metadata + body into a single string for embedding."""
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

    return ' '.join(parts)


def _content_hash(text: str) -> str:
    """Fast hash of doc content for change detection."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def build_embeddings(docs: list, project_root: Path,
                     model_name: str = 'BAAI/bge-small-en-v1.5',
                     existing: dict | None = None) -> dict:
    """Build embedding vectors for docs, reusing cached vectors for unchanged files.

    Each entry is {vector: [float, ...], hash: str}. When existing data is
    provided, only docs whose content hash changed get re-embedded.
    Returns the count of newly embedded docs as a second value.
    """
    if not FASTEMBED_AVAILABLE:
        raise RuntimeError(
            "fastembed is not installed. Install it with: pip install fastembed"
        )

    existing = existing or {}
    doc_paths = {doc['path'] for doc in docs}

    # Compute text + hash for every doc, figure out which need embedding
    to_embed = []  # (path, text)
    result = {}
    for doc in docs:
        text = _doc_text(doc, project_root)
        h = _content_hash(text)
        cached = existing.get(doc['path'])
        if isinstance(cached, dict) and cached.get('hash') == h:
            result[doc['path']] = cached
        else:
            to_embed.append((doc['path'], text, h))

    if to_embed:
        model = TextEmbedding(model_name=model_name)
        texts = [t[1] for t in to_embed]
        for (path, _, h), embedding in zip(to_embed, model.embed(texts)):
            result[path] = {'vector': embedding.tolist(), 'hash': h}

    return result, len(to_embed)


def save_embeddings(data: dict, output_path: Path):
    """Write embeddings sidecar file."""
    with open(output_path, 'w') as f:
        json.dump(data, f)


def load_embeddings(output_path: Path) -> dict | None:
    """Load embeddings sidecar file."""
    if not output_path.exists():
        return None
    with open(output_path) as f:
        return json.load(f)


def cosine_similarity_dense(v1: list, v2: list) -> float:
    """Cosine similarity between two dense vectors (lists of floats)."""
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)


def embedding_search(query: str, embeddings: dict, docs: list,
                     model_name: str = 'BAAI/bge-small-en-v1.5',
                     top: int = 10, use_importance: bool = True) -> list:
    """Search using embedding cosine similarity, blended with importance."""
    if not FASTEMBED_AVAILABLE:
        raise RuntimeError(
            "fastembed is not installed. Install it with: pip install fastembed"
        )

    model = TextEmbedding(model_name=model_name)
    query_vec = list(model.embed([query]))[0].tolist()

    results = []
    for doc in docs:
        entry = embeddings.get(doc['path'])
        if not entry:
            continue
        vec = entry.get('vector', entry) if isinstance(entry, dict) else entry
        sim = cosine_similarity_dense(query_vec, vec)
        if sim > 0.01:
            importance = doc.get('_importance', 0.0)
            if use_importance and importance:
                final = sim * 0.7 + importance * 0.3
            else:
                final = sim
            results.append({**doc, '_score': round(final, 4),
                            '_match': round(sim, 4)})

    results.sort(key=lambda d: d['_score'], reverse=True)
    return results[:top]
