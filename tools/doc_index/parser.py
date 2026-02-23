"""Frontmatter parser — no PyYAML dependency.

Handles:
  - Bare values: status: in-progress
  - Bracket lists: scope: [perspective, shot-detection]
  - Quoted strings: title: "006: Goal Decomposition"
  - Missing frontmatter: returns None
"""

import re

FRONTMATTER_FENCE = re.compile(r'^---\s*$')
KV_PATTERN = re.compile(r'^(\w[\w-]*)\s*:\s*(.*)$')
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
    """Extract YAML frontmatter from markdown text."""
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


def strip_frontmatter(text: str) -> str:
    """Return markdown body with frontmatter removed."""
    lines = text.split('\n')
    if not lines or not FRONTMATTER_FENCE.match(lines[0]):
        return text

    for i, line in enumerate(lines[1:], start=1):
        if FRONTMATTER_FENCE.match(line):
            return '\n'.join(lines[i + 1:])

    return text
