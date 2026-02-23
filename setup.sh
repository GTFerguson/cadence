#!/usr/bin/env bash
set -euo pipefail

# ── Cadence Setup ───────────────────────────────────────────────────────
# Scaffolds a project with Cadence conventions: docs structure,
# CLAUDE.md template, rules symlinks, doc-index tool, and config.
#
# Modes:
#   Submodule: detected when this script is inside a nested git repo
#   Standalone: pass --project-dir or run from a project root
#
# All operations are idempotent — safe to re-run.
# ───────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="1.0.0"

# Defaults
PROJECT_DIR=""
PROJECT_NAME=""
YES=false
FORCE=false
NO_RULES=false
DRY_RUN=false

# ── Helpers ────────────────────────────────────────────────────────────────

usage() {
    cat <<EOF
Cadence Setup v${VERSION}

Usage: $(basename "$0") [OPTIONS]

Options:
  --project-dir PATH   Project root directory (auto-detected if omitted)
  --project-name NAME  Project name for CLAUDE.md (defaults to directory name)
  --yes                Accept defaults without prompting
  --force              Overwrite existing CLAUDE.md
  --no-rules           Skip symlinking rules to ~/.claude/rules/
  --dry-run            Show what would be done without making changes
  -h, --help           Show this help

Examples:
  # New project setup
  ./setup.sh

  # Submodule mode (from project root)
  ./cadence/setup.sh

  # Non-interactive with explicit paths
  ./setup.sh --project-dir /path/to/project --project-name my-app --yes

  # Existing project (rules already installed)
  ./setup.sh --yes --no-rules
EOF
    exit 0
}

log() { echo "  $1"; }
log_ok() { echo "  ✓ $1"; }
log_skip() { echo "  · $1 (skipped)"; }
log_warn() { echo "  ! $1"; }
log_dry() { echo "  [dry-run] $1"; }

do_mkdir() {
    local dir="$1"
    if [[ "$DRY_RUN" == true ]]; then
        [[ -d "$dir" ]] || log_dry "mkdir -p $dir"
        return
    fi
    if [[ ! -d "$dir" ]]; then
        mkdir -p "$dir"
        log_ok "Created $dir"
    fi
}

# ── Parse arguments ───────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --project-dir)  PROJECT_DIR="$2"; shift 2 ;;
        --project-name) PROJECT_NAME="$2"; shift 2 ;;
        --yes)          YES=true; shift ;;
        --force)        FORCE=true; shift ;;
        --no-rules)     NO_RULES=true; shift ;;
        --dry-run)      DRY_RUN=true; shift ;;
        -h|--help)      usage ;;
        *)              echo "Unknown option: $1"; usage ;;
    esac
done

# ── Detect mode and resolve paths ─────────────────────────────────────────

ADK_ROOT="$SCRIPT_DIR"

if [[ -n "$PROJECT_DIR" ]]; then
    PROJECT_ROOT="$(cd "$PROJECT_DIR" && pwd)"
elif [[ -d "$SCRIPT_DIR/../.git" && -d "$SCRIPT_DIR/.git" ]]; then
    # Submodule: script is in a git repo that's inside another git repo
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
elif [[ -d "$SCRIPT_DIR/.git" ]]; then
    # We're at the cadence root itself — look for parent project
    parent="$(cd "$SCRIPT_DIR/.." && pwd)"
    if [[ -d "$parent/.git" ]]; then
        PROJECT_ROOT="$parent"
    else
        PROJECT_ROOT="$SCRIPT_DIR"
    fi
else
    # Walk up to find git root
    PROJECT_ROOT="$(cd "$SCRIPT_DIR" && git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi

# Don't scaffold inside cadence itself unless explicitly asked
if [[ "$PROJECT_ROOT" == "$ADK_ROOT" && -z "$PROJECT_DIR" ]]; then
    echo "Error: Cannot scaffold inside cadence itself."
    echo "Use --project-dir to specify a target project."
    exit 1
fi

# ── Resolve project name ──────────────────────────────────────────────────

if [[ -z "$PROJECT_NAME" ]]; then
    default_name="$(basename "$PROJECT_ROOT")"
    if [[ "$YES" == true ]]; then
        PROJECT_NAME="$default_name"
    else
        read -rp "  Project name [$default_name]: " input_name
        PROJECT_NAME="${input_name:-$default_name}"
    fi
fi

echo ""
echo "Cadence Setup v${VERSION}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Project:  $PROJECT_NAME"
echo "  Root:     $PROJECT_ROOT"
echo "  Brain:    $ADK_ROOT"
echo ""

# ── Step 1: Create docs structure ─────────────────────────────────────────

echo "1. Documentation structure"
for dir in docs/architecture docs/reference docs/guides docs/guides/tools docs/plans; do
    do_mkdir "$PROJECT_ROOT/$dir"
done
echo ""

# ── Step 2: Generate CLAUDE.md from template ──────────────────────────────

echo "2. CLAUDE.md"
claude_md="$PROJECT_ROOT/CLAUDE.md"
template="$ADK_ROOT/templates/CLAUDE.md.tmpl"

if [[ -f "$claude_md" && "$FORCE" != true ]]; then
    log_skip "CLAUDE.md already exists (use --force to overwrite)"
else
    if [[ "$DRY_RUN" == true ]]; then
        log_dry "Generate CLAUDE.md from template"
    else
        sed "s/\${PROJECT_NAME}/$PROJECT_NAME/g" "$template" > "$claude_md"
        log_ok "Generated CLAUDE.md"
    fi
fi
echo ""

# ── Step 3: Symlink rules ────────────────────────────────────────────────

echo "3. Claude Code rules"
if [[ "$NO_RULES" == true ]]; then
    log_skip "Rules installation disabled (--no-rules)"
else
    rules_dir="$HOME/.claude/rules"
    if [[ "$DRY_RUN" == true ]]; then
        [[ -d "$rules_dir" ]] || log_dry "mkdir -p $rules_dir"
        for rule in "$ADK_ROOT"/rules/*.md; do
            rule_name="$(basename "$rule")"
            log_dry "symlink $rules_dir/$rule_name → $rule"
        done
    else
        mkdir -p "$rules_dir"
        for rule in "$ADK_ROOT"/rules/*.md; do
            rule_name="$(basename "$rule")"
            target="$rules_dir/$rule_name"

            if [[ -L "$target" ]]; then
                existing="$(readlink "$target")"
                if [[ "$existing" == "$rule" ]]; then
                    log_skip "$rule_name (symlink already correct)"
                else
                    log_warn "$rule_name exists → $existing (different source, skipping)"
                fi
            elif [[ -f "$target" ]]; then
                log_warn "$rule_name exists as regular file (skipping — remove manually to use symlink)"
            else
                ln -s "$rule" "$target"
                log_ok "Linked $rule_name"
            fi
        done
    fi
fi
echo ""

# ── Step 4: Install doc-index tool ───────────────────────────────────────

echo "4. Doc-index tool"
tools_dir="$PROJECT_ROOT/tools"

# Symlink the package directory and wrapper script
doc_index_pkg_src="$ADK_ROOT/tools/doc_index"
doc_index_pkg_dst="$tools_dir/doc_index"
doc_index_bin_src="$ADK_ROOT/tools/doc-index"
doc_index_bin_dst="$tools_dir/doc-index"

symlink_item() {
    local src="$1" dst="$2" label="$3"
    if [[ -L "$dst" ]]; then
        existing="$(readlink "$dst")"
        if [[ "$existing" == "$src" ]]; then
            log_skip "$label (symlink already correct)"
        else
            log_warn "$label exists → $existing (different source, skipping)"
        fi
    elif [[ -e "$dst" ]]; then
        log_skip "$label already exists (not a symlink, skipping)"
    else
        ln -s "$src" "$dst"
        log_ok "Linked $label"
    fi
}

if [[ "$DRY_RUN" == true ]]; then
    [[ -d "$tools_dir" ]] || log_dry "mkdir -p $tools_dir"
    log_dry "symlink $doc_index_pkg_dst → $doc_index_pkg_src"
    log_dry "symlink $doc_index_bin_dst → $doc_index_bin_src"
else
    mkdir -p "$tools_dir"
    symlink_item "$doc_index_pkg_src" "$doc_index_pkg_dst" "doc_index/ package"
    symlink_item "$doc_index_bin_src" "$doc_index_bin_dst" "doc-index wrapper"
fi
echo ""

# ── Step 5: Create .doc-index.yaml config ────────────────────────────────

echo "5. Doc-index config"
config_file="$PROJECT_ROOT/.doc-index.yaml"

if [[ -f "$config_file" ]]; then
    log_skip ".doc-index.yaml already exists"
else
    if [[ "$DRY_RUN" == true ]]; then
        log_dry "Create .doc-index.yaml"
    else
        cat > "$config_file" <<'YAML'
# Cadence doc-index configuration
# Directories to scan for markdown frontmatter
scan:
  - docs/
  - lib/docs/

# Directories to exclude from scanning
exclude:
  - node_modules/
  - .git/

# Output paths (stored in .cade/ to keep project root clean)
output: .cade/doc-index.json
YAML
        log_ok "Created .doc-index.yaml"
    fi
fi
echo ""

# ── Step 6: Update .gitignore ────────────────────────────────────────────

echo "6. Gitignore"
gitignore="$PROJECT_ROOT/.gitignore"

add_to_gitignore() {
    local pattern="$1"
    if [[ -f "$gitignore" ]] && grep -qF "$pattern" "$gitignore"; then
        log_skip "$pattern already in .gitignore"
    else
        if [[ "$DRY_RUN" == true ]]; then
            log_dry "Add $pattern to .gitignore"
        else
            echo "$pattern" >> "$gitignore"
            log_ok "Added $pattern to .gitignore"
        fi
    fi
}

add_to_gitignore ".cade/"
echo ""

# ── Summary ──────────────────────────────────────────────────────────────

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [[ "$DRY_RUN" == true ]]; then
    echo "  Dry run complete — no changes made."
else
    echo "  Setup complete!"
    echo ""
    echo "  Next steps:"
    echo "    1. Customize CLAUDE.md with your project structure"
    echo "    2. Add frontmatter to your docs (title, scope, tags)"
    echo "    3. Build the doc index: tools/doc-index --build"
fi
echo ""
