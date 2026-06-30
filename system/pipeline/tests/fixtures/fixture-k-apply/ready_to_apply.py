"""Module ready for apply decision."""

import pathlib
import tempfile

def create_temp_config(name: str, values: dict) -> pathlib.Path:
    """Create a temporary config file."""
    path = pathlib.Path(tempfile.gettempdir()) / f"{name}.json"
    import json
    path.write_text(json.dumps(values, indent=2))
    return path

def validate_config(path: pathlib.Path) -> bool:
    """Validate config file exists and is valid JSON."""
    import json
    if not path.exists():
        return False
    try:
        json.loads(path.read_text())
        return True
    except json.JSONDecodeError:
        return False
