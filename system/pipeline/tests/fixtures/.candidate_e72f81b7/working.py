"""Working module."""

def process(data: list) -> list:
    """Process data."""
    return [x.strip() for x in data if x]
