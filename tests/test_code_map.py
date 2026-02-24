"""Tests for code_map: extraction, resolution, and reverse index building."""

import json
import tempfile
from pathlib import Path

import pytest

from tools.doc_index.code_map import (
    extract_code_refs,
    resolve_ref,
    build_code_map,
    context_search,
    collect_project_files,
    _strip_line_number,
    _normalise_path,
    _should_exclude,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_project(tmp_path, files: dict) -> Path:
    """Create a temp project with given file structure.

    files: {relative_path: content} — empty string for code files,
    markdown content for docs.
    """
    for rel_path, content in files.items():
        p = tmp_path / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return tmp_path


# ── Unit: _strip_line_number ─────────────────────────────────────────────

class TestStripLineNumber:
    def test_no_line_number(self):
        assert _strip_line_number('src/auth.py') == 'src/auth.py'

    def test_single_line(self):
        assert _strip_line_number('src/auth.py:42') == 'src/auth.py'

    def test_line_range(self):
        assert _strip_line_number('src/auth.py:42-58') == 'src/auth.py'

    def test_no_false_positive_on_colon_in_path(self):
        # Windows-style paths shouldn't happen but be safe
        assert _strip_line_number('src/auth.py') == 'src/auth.py'


# ── Unit: _normalise_path ────────────────────────────────────────────────

class TestNormalisePath:
    def test_simple_path(self):
        assert _normalise_path('src/auth.py') == 'src/auth.py'

    def test_relative_parent(self):
        assert _normalise_path('../../../include/Gene.hpp') == 'include/Gene.hpp'

    def test_dot_segments(self):
        assert _normalise_path('./src/../lib/utils.py') == 'lib/utils.py'

    def test_with_line_number(self):
        assert _normalise_path('src/auth.py:42') == 'src/auth.py'


# ── Unit: extract_code_refs ──────────────────────────────────────────────

class TestExtractCodeRefs:
    def test_markdown_link(self):
        text = 'See [`AuthService`](src/auth/service.py) for details.'
        refs = extract_code_refs(text, 'docs/guide.md')
        assert any(r['ref'] == 'src/auth/service.py' and r['type'] == 'md_link' for r in refs)

    def test_markdown_link_with_line_number(self):
        text = 'See [`Gene`](../../../include/genetics/Gene.hpp:107) class.'
        refs = extract_code_refs(text, 'docs/technical/design/resource.md')
        assert any(r['ref'] == '../../../include/genetics/Gene.hpp' for r in refs)

    def test_markdown_link_skips_urls(self):
        text = 'See [docs](https://example.com/file.py) for details.'
        refs = extract_code_refs(text, 'docs/guide.md')
        assert len(refs) == 0

    def test_markdown_link_skips_md_files(self):
        text = 'See [guide](getting-started.md) for details.'
        refs = extract_code_refs(text, 'docs/guide.md')
        assert len(refs) == 0

    def test_backtick_path_with_slash(self):
        text = 'Edit `src/auth/service.py` to add the handler.'
        refs = extract_code_refs(text, 'docs/guide.md')
        assert any(r['ref'] == 'src/auth/service.py' and r['type'] == 'backtick' for r in refs)

    def test_backtick_bare_filename(self):
        text = 'The `service.py` module handles requests.'
        refs = extract_code_refs(text, 'docs/guide.md')
        assert any(r['ref'] == 'service.py' and r['type'] == 'backtick' for r in refs)

    def test_backtick_skips_md_files(self):
        text = 'See `README.md` for details.'
        refs = extract_code_refs(text, 'docs/guide.md')
        assert not any(r['ref'] == 'README.md' for r in refs)

    def test_see_ref(self):
        text = '/** @see docs/design/auth-flow.py for specification */'
        refs = extract_code_refs(text, 'docs/guide.md')
        assert any(r['ref'] == 'docs/design/auth-flow.py' and r['type'] == 'see_ref' for r in refs)

    def test_see_ref_skips_md(self):
        text = '/** @see docs/design/auth.md for specification */'
        refs = extract_code_refs(text, 'docs/guide.md')
        assert len(refs) == 0

    def test_bare_path(self):
        text = 'The implementation lives in src/auth/handler.py and works well.'
        refs = extract_code_refs(text, 'docs/guide.md')
        assert any(r['ref'] == 'src/auth/handler.py' and r['type'] == 'bare_path' for r in refs)

    def test_bare_path_requires_slash(self):
        text = 'The handler.py file does stuff.'
        refs = extract_code_refs(text, 'docs/guide.md')
        # No bare_path match — needs a slash. May match as backtick if backticked.
        assert not any(r['type'] == 'bare_path' for r in refs)

    def test_deduplication(self):
        text = '''
See [`Gene`](include/Gene.hpp) for the class.
Also see `include/Gene.hpp` for implementation.
'''
        refs = extract_code_refs(text, 'docs/guide.md')
        paths = [r['ref'] for r in refs]
        assert paths.count('include/Gene.hpp') == 1

    def test_multiple_ref_types(self):
        text = '''
The [`AuthService`](src/auth.py) handles login.
Check `src/middleware/jwt.py` for token validation.
Related: src/models/user.py has the schema.
'''
        refs = extract_code_refs(text, 'docs/guide.md')
        assert len(refs) == 3
        types = {r['type'] for r in refs}
        assert 'md_link' in types
        assert 'backtick' in types
        assert 'bare_path' in types

    def test_file_table(self):
        text = '''
| File | Purpose |
|------|---------|
| [`ScentLayer.hpp`](include/world/ScentLayer.hpp) | Header |
| [`ScentLayer.cpp`](src/world/ScentLayer.cpp) | Implementation |
'''
        refs = extract_code_refs(text, 'docs/guide.md')
        paths = {r['ref'] for r in refs}
        assert 'include/world/ScentLayer.hpp' in paths
        assert 'src/world/ScentLayer.cpp' in paths

    def test_frontmatter_stripped(self):
        text = '''---
title: Guide
scope: [all]
---

See [`handler`](src/handler.py) for details.
'''
        refs = extract_code_refs(text, 'docs/guide.md')
        assert any(r['ref'] == 'src/handler.py' for r in refs)


# ── Unit: resolve_ref ────────────────────────────────────────────────────

class TestResolveRef:
    by_path = {
        'src/auth/service.py': True,
        'src/auth/handler.py': True,
        'src/models/user.py': True,
        'include/genetics/Gene.hpp': True,
        'lib/utils.py': True,
    }

    by_name = {
        'service.py': ['src/auth/service.py'],
        'handler.py': ['src/auth/handler.py'],
        'user.py': ['src/models/user.py'],
        'Gene.hpp': ['include/genetics/Gene.hpp'],
        'utils.py': ['lib/utils.py'],
    }

    def test_exact_match(self):
        path, match = resolve_ref('src/auth/service.py', 'docs/guide.md',
                                  self.by_path, self.by_name)
        assert path == 'src/auth/service.py'
        assert match == 'exact'

    def test_relative_resolution(self):
        path, match = resolve_ref(
            '../../../include/genetics/Gene.hpp',
            'docs/technical/design/resource.md',
            self.by_path, self.by_name
        )
        assert path == 'include/genetics/Gene.hpp'
        assert match == 'relative'

    def test_bare_filename_unambiguous(self):
        path, match = resolve_ref('Gene.hpp', 'docs/guide.md',
                                  self.by_path, self.by_name)
        assert path == 'include/genetics/Gene.hpp'
        assert match == 'filename'

    def test_bare_filename_ambiguous(self):
        by_name = {**self.by_name, 'utils.py': ['lib/utils.py', 'src/utils.py']}
        path, match = resolve_ref('utils.py', 'docs/guide.md',
                                  self.by_path, by_name)
        assert path is None
        assert match == 'unresolved'

    def test_nonexistent_file(self):
        path, match = resolve_ref('src/nonexistent.py', 'docs/guide.md',
                                  self.by_path, self.by_name)
        assert path is None
        assert match == 'unresolved'

    def test_with_line_number(self):
        path, match = resolve_ref('src/auth/service.py:42', 'docs/guide.md',
                                  self.by_path, self.by_name)
        assert path == 'src/auth/service.py'
        assert match == 'exact'


# ── Unit: collect_project_files ──────────────────────────────────────────

class TestCollectProjectFiles:
    def test_finds_code_files(self, tmp_path):
        _make_project(tmp_path, {
            'src/main.py': '',
            'src/utils.py': '',
            'docs/guide.md': '# Guide',
            'README.md': '# Readme',
        })
        by_path, by_name = collect_project_files(tmp_path, ['.git/'])
        assert 'src/main.py' in by_path
        assert 'src/utils.py' in by_path
        # .md files excluded by IGNORE_EXTENSIONS
        assert 'docs/guide.md' not in by_path
        assert 'README.md' not in by_path

    def test_respects_excludes(self, tmp_path):
        _make_project(tmp_path, {
            'src/main.py': '',
            'node_modules/dep/index.js': '',
            '.venv/lib/site.py': '',
        })
        by_path, by_name = collect_project_files(
            tmp_path, ['node_modules/', '.venv/']
        )
        assert 'src/main.py' in by_path
        assert 'node_modules/dep/index.js' not in by_path
        assert '.venv/lib/site.py' not in by_path

    def test_by_name_index(self, tmp_path):
        _make_project(tmp_path, {
            'src/auth/handler.py': '',
            'src/api/handler.py': '',
            'lib/utils.py': '',
        })
        by_path, by_name = collect_project_files(tmp_path, [])
        assert len(by_name['handler.py']) == 2
        assert len(by_name['utils.py']) == 1


# ── Integration: build_code_map ──────────────────────────────────────────

class TestBuildCodeMap:
    def test_basic_mapping(self, tmp_path):
        _make_project(tmp_path, {
            'src/auth.py': 'class AuthService: pass',
            'src/handler.py': 'def handle(): pass',
            'docs/architecture.md': '''---
title: Architecture
scope: [all]
---

# Auth System

The auth service is in [`AuthService`](../src/auth.py).
The handler is at `src/handler.py`.
''',
        })

        docs = [{
            'path': 'docs/architecture.md',
            'title': 'Architecture',
            'description': 'Auth system docs',
            'scope': ['all'],
            'status': None,
            'tags': None,
            'updated': None,
        }]

        config = {'exclude': ['.git/']}
        code_map = build_code_map(docs, tmp_path, config)

        assert 'src/auth.py' in code_map
        assert code_map['src/auth.py'][0]['doc'] == 'docs/architecture.md'
        assert 'src/handler.py' in code_map

    def test_multiple_docs_same_file(self, tmp_path):
        _make_project(tmp_path, {
            'src/auth.py': '',
            'docs/design.md': '''---
title: Design
---

See [`auth`](../src/auth.py) for implementation.
''',
            'docs/guide.md': '''---
title: Guide
---

Edit `src/auth.py` to configure authentication.
''',
        })

        docs = [
            {'path': 'docs/design.md', 'title': 'Design', 'description': None,
             'scope': None, 'status': None, 'tags': None, 'updated': None},
            {'path': 'docs/guide.md', 'title': 'Guide', 'description': None,
             'scope': None, 'status': None, 'tags': None, 'updated': None},
        ]

        config = {'exclude': ['.git/']}
        code_map = build_code_map(docs, tmp_path, config)

        assert 'src/auth.py' in code_map
        assert len(code_map['src/auth.py']) == 2
        doc_paths = {e['doc'] for e in code_map['src/auth.py']}
        assert doc_paths == {'docs/design.md', 'docs/guide.md'}

    def test_relative_path_resolution(self, tmp_path):
        _make_project(tmp_path, {
            'include/genetics/Gene.hpp': '',
            'docs/technical/design/resource.md': '''---
title: Resource Allocation
---

Extend [`GeneDefinition`](../../../include/genetics/Gene.hpp:107) to include costs.
''',
        })

        docs = [{'path': 'docs/technical/design/resource.md', 'title': 'Resource',
                 'description': None, 'scope': None, 'status': None,
                 'tags': None, 'updated': None}]

        config = {'exclude': ['.git/']}
        code_map = build_code_map(docs, tmp_path, config)

        assert 'include/genetics/Gene.hpp' in code_map

    def test_no_false_positives_for_missing_files(self, tmp_path):
        _make_project(tmp_path, {
            'src/real.py': '',
            'docs/guide.md': '''---
title: Guide
---

See `src/real.py` and `src/nonexistent.py` for details.
''',
        })

        docs = [{'path': 'docs/guide.md', 'title': 'Guide', 'description': None,
                 'scope': None, 'status': None, 'tags': None, 'updated': None}]

        config = {'exclude': ['.git/']}
        code_map = build_code_map(docs, tmp_path, config)

        assert 'src/real.py' in code_map
        assert 'src/nonexistent.py' not in code_map

    def test_empty_docs(self, tmp_path):
        _make_project(tmp_path, {
            'src/main.py': '',
            'docs/empty.md': '---\ntitle: Empty\n---\n\nNo code refs here.',
        })

        docs = [{'path': 'docs/empty.md', 'title': 'Empty', 'description': None,
                 'scope': None, 'status': None, 'tags': None, 'updated': None}]

        config = {'exclude': ['.git/']}
        code_map = build_code_map(docs, tmp_path, config)

        assert len(code_map) == 0

    def test_scores_ranked(self, tmp_path):
        _make_project(tmp_path, {
            'src/auth.py': '',
            'docs/high.md': '''---
title: High
---

See [`auth`](src/auth.py) — a markdown link (high confidence).
''',
            'docs/low.md': '''---
title: Low
---

The implementation lives in src/auth.py somewhere.
''',
        })

        docs = [
            {'path': 'docs/high.md', 'title': 'High', 'description': None,
             'scope': None, 'status': None, 'tags': None, 'updated': None},
            {'path': 'docs/low.md', 'title': 'Low', 'description': None,
             'scope': None, 'status': None, 'tags': None, 'updated': None},
        ]

        config = {'exclude': ['.git/']}
        code_map = build_code_map(docs, tmp_path, config)

        entries = code_map['src/auth.py']
        # md_link should score higher than bare_path
        assert entries[0]['doc'] == 'docs/high.md'
        assert entries[0]['score'] > entries[1]['score']


# ── Integration: context_search ──────────────────────────────────────────

class TestContextSearch:
    def test_exact_lookup(self):
        code_map = {
            'src/auth.py': [
                {'doc': 'docs/design.md', 'score': 1.0},
                {'doc': 'docs/guide.md', 'score': 0.7},
            ],
        }
        docs_by_path = {
            'docs/design.md': {'path': 'docs/design.md', 'title': 'Design'},
            'docs/guide.md': {'path': 'docs/guide.md', 'title': 'Guide'},
        }

        results = context_search('src/auth.py', code_map, docs_by_path)
        assert len(results) == 2
        assert results[0]['title'] == 'Design'
        assert results[0]['_score'] == 1.0

    def test_partial_match(self):
        code_map = {
            'src/auth/service.py': [
                {'doc': 'docs/auth.md', 'score': 1.0},
            ],
        }
        docs_by_path = {
            'docs/auth.md': {'path': 'docs/auth.md', 'title': 'Auth'},
        }

        results = context_search('service.py', code_map, docs_by_path)
        assert len(results) == 1
        assert results[0]['title'] == 'Auth'

    def test_no_match(self):
        code_map = {
            'src/auth.py': [{'doc': 'docs/auth.md', 'score': 1.0}],
        }
        docs_by_path = {
            'docs/auth.md': {'path': 'docs/auth.md', 'title': 'Auth'},
        }

        results = context_search('src/other.py', code_map, docs_by_path)
        assert len(results) == 0

    def test_top_limit(self):
        code_map = {
            'src/big.py': [
                {'doc': f'docs/doc{i}.md', 'score': 1.0 - i * 0.1}
                for i in range(20)
            ],
        }
        docs_by_path = {
            f'docs/doc{i}.md': {'path': f'docs/doc{i}.md', 'title': f'Doc {i}'}
            for i in range(20)
        }

        results = context_search('src/big.py', code_map, docs_by_path, top=5)
        assert len(results) == 5
