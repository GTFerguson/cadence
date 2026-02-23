"""Configuration loader for .doc-index.yaml — line-based, no YAML dependency."""

from pathlib import Path

DEFAULT_CONFIG = {
    'scan': ['docs/', 'lib/docs/'],
    'exclude': ['node_modules/', '.git/'],
    'output': '.doc-index.json',
    'tfidf_output': '.doc-index-tfidf.json',
}


def load_config(project_root: Path) -> dict:
    """Load .doc-index.yaml config using line-based parsing."""
    config_path = project_root / '.doc-index.yaml'
    if not config_path.exists():
        return dict(DEFAULT_CONFIG)

    config = {}
    current_key = None
    current_list = None

    with open(config_path) as f:
        for line in f:
            line = line.rstrip('\n')

            if not line.strip() or line.strip().startswith('#'):
                if current_key and current_list is not None:
                    config[current_key] = current_list
                    current_key = None
                    current_list = None
                continue

            if line.startswith('  - ') and current_key:
                current_list.append(line.strip()[2:].strip())
                continue

            if ':' in line and not line.startswith(' '):
                if current_key and current_list is not None:
                    config[current_key] = current_list

                key, _, value = line.partition(':')
                key = key.strip()
                value = value.strip()

                if value:
                    config[key] = value
                    current_key = None
                    current_list = None
                else:
                    current_key = key
                    current_list = []

    if current_key and current_list is not None:
        config[current_key] = current_list

    for k, v in DEFAULT_CONFIG.items():
        if k not in config:
            config[k] = v

    return config
