#!/usr/bin/env python3
"""
doc-index: Build and query a frontmatter-based documentation index.

Scans markdown files for YAML frontmatter, extracts metadata (title, scope,
status, tags, dates, descriptions), and writes a static JSON index. Supports
filtering, fuzzy search, semantic search, and document graph traversal.

Zero external dependencies — uses only Python stdlib.

Usage:
    python tools/doc_index --build
    python tools/doc_index --discover
    python tools/doc_index --scope perspective --tag homography
    python tools/doc_index --build --scope all --json
    python tools/doc_index --status draft
"""

import argparse
import json
import sys
from pathlib import Path

from .builder import build_index, load_index
from .config import load_config
from .query import filter_docs, format_table, format_discover
from .search import (fuzzy_search, format_search_table,
                     build_tfidf, save_tfidf, load_tfidf, semantic_search)
from .embeddings import (FASTEMBED_AVAILABLE, build_embeddings,
                         save_embeddings, load_embeddings, embedding_search)
from .graph import find_related, format_related_table, topological_sort
from .fusion import reciprocal_rank_fusion, expand_with_graph
from .code_map import context_search


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
    parser.add_argument('--discover', action='store_true',
                        help='Show index summary: available scopes, tags, statuses')
    parser.add_argument('--scope', type=str,
                        help='Filter by scope (e.g., perspective, all)')
    parser.add_argument('--tag', type=str,
                        help='Filter by tag')
    parser.add_argument('--status', type=str,
                        help='Filter by status (e.g., draft, completed)')
    parser.add_argument('--search', type=str, metavar='QUERY',
                        help='Fuzzy search across title, tags, scope, description')
    parser.add_argument('--top', type=int, default=10,
                        help='Max results for search (default: 10)')
    parser.add_argument('--semantic', type=str, metavar='QUERY',
                        help='Semantic search (embeddings if available, TF-IDF fallback)')
    parser.add_argument('--tfidf', action='store_true',
                        help='(Deprecated) TF-IDF is now always built with --build')
    parser.add_argument('--embeddings', action='store_true',
                        help='Build local embeddings via FastEmbed (use with --build)')
    parser.add_argument('--query', type=str, metavar='QUERY',
                        help='Hybrid fusion search (combines fuzzy + TF-IDF + embeddings)')
    parser.add_argument('--expand', action='store_true',
                        help='Include 1-hop graph neighbors (use with --query)')
    parser.add_argument('--rrf-k', type=int, default=60,
                        help='RRF k constant (default: 60)')
    parser.add_argument('--context', type=str, metavar='PATH',
                        help='Find docs relevant to a code file (reverse code-to-doc map)')
    parser.add_argument('--related', type=str, metavar='PATH',
                        help='Show docs related to a file (graph traversal)')
    parser.add_argument('--depth', type=int, default=1,
                        help='Max hops for --related traversal (default: 1)')
    parser.add_argument('--graph', action='store_true',
                        help='Dump full document graph as JSON')
    parser.add_argument('--reading-order', action='store_true',
                        help='Sort results by dependency order (read these first)')
    parser.add_argument('--json', action='store_true',
                        help='Output as JSON instead of table')
    parser.add_argument('--project-dir', type=str,
                        help='Project root directory (auto-detected if omitted)')

    args = parser.parse_args()

    has_action = (args.build or args.discover or args.query or args.search
                  or args.semantic or args.related or args.graph or args.context)
    has_filter = args.scope or args.tag or args.status
    if not has_action and not has_filter:
        parser.print_help()
        sys.exit(1)

    project_root = Path(args.project_dir).resolve() if args.project_dir else find_project_root()
    config = load_config(project_root)

    # Build
    if args.build:
        index = build_index(project_root, config)
        output_path = project_root / config.get('output', '.doc-index.json')
        code_map_size = len(index.get('code_map', {}))
        print(f"Indexed {index['count']} documents, {code_map_size} code files mapped → {output_path}")

        # Always build TF-IDF (fast, no dependencies)
        tfidf_path = project_root / config.get('tfidf_output', '.doc-index-tfidf.json')
        tfidf_data = build_tfidf(index['docs'], project_root)
        save_tfidf(tfidf_data, tfidf_path)
        print(f"Built TF-IDF index → {tfidf_path}")

        # Optionally build embeddings (requires fastembed)
        if args.embeddings:
            if not FASTEMBED_AVAILABLE:
                print("fastembed not installed — skipping embeddings.", file=sys.stderr)
                print("Install with: pip install fastembed", file=sys.stderr)
            else:
                emb_path = project_root / config.get('embeddings_output', '.doc-index-embeddings.json')
                model = config.get('embedding_model', 'BAAI/bge-small-en-v1.5')
                existing = load_embeddings(emb_path)
                emb_data, embedded_count = build_embeddings(
                    index['docs'], project_root, model_name=model, existing=existing)
                save_embeddings(emb_data, emb_path)
                total = len(emb_data)
                if embedded_count == 0:
                    print(f"Embeddings up to date ({total} docs) → {emb_path}")
                else:
                    cached = total - embedded_count
                    print(f"Embedded {embedded_count} docs ({cached} cached) → {emb_path}")

        if not has_filter and not args.discover and not args.query \
                and not args.search and not args.semantic \
                and not args.related and not args.graph and not args.context:
            return

    # Load index for querying
    index = load_index(project_root, config)
    if not index:
        print("No index found. Run with --build first.", file=sys.stderr)
        sys.exit(1)

    # Discover
    if args.discover:
        if args.json:
            output = {
                'count': index.get('count', 0),
                'generated': index.get('generated'),
                'meta': index.get('meta', {}),
            }
            print(json.dumps(output, indent=2))
        else:
            print(format_discover(index))
        if not has_filter:
            return

    # Graph dump
    if args.graph:
        graph = index.get('graph', {})
        print(json.dumps(graph, indent=2))
        return

    # Context: docs relevant to a code file
    if args.context:
        code_map = index.get('code_map', {})
        if not code_map:
            print("No code map in index. Rebuild with --build.", file=sys.stderr)
            sys.exit(1)
        docs_by_path = {d['path']: d for d in index['docs']}
        results = context_search(args.context, code_map, docs_by_path, top=args.top)
        if not results:
            print(f"No docs found referencing {args.context}", file=sys.stderr)
            sys.exit(0)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(format_search_table(results))
        return

    # Related docs
    if args.related:
        graph = index.get('graph', {})
        if not graph:
            print("No graph data in index. Rebuild with --build.", file=sys.stderr)
            sys.exit(1)
        results = find_related(graph, args.related, depth=args.depth)
        docs_by_path = {d['path']: d for d in index['docs']}
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(format_related_table(results, args.related, docs_by_path))
        return

    graph = index.get('graph', {})
    importance = {d['path']: d.get('_importance', 0) for d in index['docs']}

    # Hybrid fusion search
    if args.query:
        docs_by_path = {d['path']: d for d in index['docs']}
        n_docs = len(index['docs'])
        signal_lists = {}

        # Always have fuzzy
        fuzzy_results = fuzzy_search(index['docs'], args.query,
                                     top=n_docs, use_importance=False)
        if fuzzy_results:
            signal_lists['fuzzy'] = fuzzy_results

        # TF-IDF
        tfidf_path = project_root / config.get('tfidf_output', '.doc-index-tfidf.json')
        tfidf_data = load_tfidf(tfidf_path)
        if tfidf_data:
            tfidf_results = semantic_search(args.query, tfidf_data, index['docs'],
                                            top=n_docs, use_importance=False)
            if tfidf_results:
                signal_lists['tfidf'] = tfidf_results

        # Embeddings (if available)
        emb_path = project_root / config.get('embeddings_output', '.doc-index-embeddings.json')
        emb_data = load_embeddings(emb_path)
        if emb_data and FASTEMBED_AVAILABLE:
            model = config.get('embedding_model', 'BAAI/bge-small-en-v1.5')
            emb_results = embedding_search(args.query, emb_data, index['docs'],
                                           model_name=model, top=n_docs,
                                           use_importance=False)
            if emb_results:
                signal_lists['embedding'] = emb_results
        elif not emb_data or not FASTEMBED_AVAILABLE:
            print("Note: embeddings not available, fusing fuzzy + TF-IDF only.",
                  file=sys.stderr)

        if not signal_lists:
            print("No results found.", file=sys.stderr)
            sys.exit(1)

        results = reciprocal_rank_fusion(signal_lists, docs_by_path,
                                         k=args.rrf_k, top=args.top)
        if args.expand:
            results = expand_with_graph(results, graph, docs_by_path)
        if args.reading_order:
            results = topological_sort(results, graph, importance)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(format_search_table(results))
        return

    # Semantic search (embeddings → TF-IDF fallback)
    if args.semantic:
        emb_path = project_root / config.get('embeddings_output', '.doc-index-embeddings.json')
        emb_data = load_embeddings(emb_path)

        if emb_data and FASTEMBED_AVAILABLE:
            model = config.get('embedding_model', 'BAAI/bge-small-en-v1.5')
            results = embedding_search(args.semantic, emb_data, index['docs'],
                                       model_name=model, top=args.top)
        else:
            if emb_data and not FASTEMBED_AVAILABLE:
                print("Note: fastembed not installed, falling back to TF-IDF.", file=sys.stderr)
            tfidf_path = project_root / config.get('tfidf_output', '.doc-index-tfidf.json')
            tfidf_data = load_tfidf(tfidf_path)
            if not tfidf_data:
                print("No search index found. Run with --build first.", file=sys.stderr)
                sys.exit(1)
            results = semantic_search(args.semantic, tfidf_data, index['docs'], top=args.top)

        if args.reading_order:
            results = topological_sort(results, graph, importance)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(format_search_table(results))
        return

    # Search
    if args.search:
        results = fuzzy_search(index['docs'], args.search, top=args.top)
        if args.reading_order:
            results = topological_sort(results, graph, importance)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(format_search_table(results))
        return

    # Filter
    results = filter_docs(index['docs'],
                          scope=args.scope, tag=args.tag, status=args.status)
    if args.reading_order:
        results = topological_sort(results, graph, importance)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(format_table(results))


if __name__ == '__main__':
    main()
