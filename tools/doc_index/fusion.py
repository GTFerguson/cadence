"""Reciprocal Rank Fusion and graph expansion for hybrid search."""


def reciprocal_rank_fusion(signal_lists: dict, docs_by_path: dict,
                           k: int = 60, top: int = 10,
                           use_importance: bool = True) -> list:
    """Fuse multiple ranked signal lists via Reciprocal Rank Fusion.

    Args:
        signal_lists: {'fuzzy': [...], 'tfidf': [...], 'embedding': [...]}
            Each list contains doc dicts with '_score' and '_match' keys,
            produced by the individual search functions with use_importance=False.
        docs_by_path: {path: doc} lookup for enriching results.
        k: RRF constant (default 60). Higher = less weight to top ranks.
        top: Number of results to return.
        use_importance: Blend importance into final score.

    Returns:
        Enriched doc dicts with _score, _match, _rrf_raw, _signals, _expanded.
    """
    # Collect per-signal scores and RRF contributions
    rrf_scores = {}   # path -> raw RRF score
    signal_scores = {}  # path -> {signal_name: match_score}

    for signal_name, results in signal_lists.items():
        for rank, doc in enumerate(results, start=1):
            path = doc['path']
            rrf_scores[path] = rrf_scores.get(path, 0.0) + 1.0 / (k + rank)
            if path not in signal_scores:
                signal_scores[path] = {}
            signal_scores[path][signal_name] = doc.get('_match', doc.get('_score', 0.0))

    if not rrf_scores:
        return []

    # Normalize RRF scores to 0-1 range
    max_rrf = max(rrf_scores.values())
    if max_rrf == 0:
        return []

    fused = []
    for path, rrf_raw in rrf_scores.items():
        doc = docs_by_path.get(path)
        if not doc:
            continue

        rrf_norm = rrf_raw / max_rrf
        signals = signal_scores.get(path, {})
        best_match = max(signals.values()) if signals else 0.0

        if use_importance:
            importance = doc.get('_importance', 0.0)
            final = rrf_norm * 0.7 + importance * 0.3
        else:
            final = rrf_norm

        fused.append({
            **doc,
            '_score': round(final, 4),
            '_match': round(best_match, 4),
            '_rrf_raw': round(rrf_raw, 6),
            '_signals': {s: round(v, 4) for s, v in signals.items()},
            '_expanded': False,
        })

    fused.sort(key=lambda d: d['_score'], reverse=True)
    return fused[:top]


def expand_with_graph(results: list, graph: dict, docs_by_path: dict,
                      damping: float = 0.5, top_k_seeds: int = 5) -> list:
    """Expand fused results with 1-hop explicit graph neighbors.

    Takes the top seeds from fused results and pulls in their explicit
    neighbors (not already in results) with a damped score.
    """
    result_paths = {d['path'] for d in results}
    seeds = results[:top_k_seeds]

    expanded = []
    for seed in seeds:
        edges = graph.get(seed['path'], {})
        for neighbor_path in edges.get('explicit', []):
            if neighbor_path in result_paths:
                continue
            neighbor_doc = docs_by_path.get(neighbor_path)
            if not neighbor_doc:
                continue
            result_paths.add(neighbor_path)
            expanded.append({
                **neighbor_doc,
                '_score': round(seed['_score'] * damping, 4),
                '_match': 0.0,
                '_rrf_raw': 0.0,
                '_signals': {},
                '_expanded': True,
                '_via': seed['path'],
            })

    merged = results + expanded
    merged.sort(key=lambda d: d['_score'], reverse=True)
    return merged
