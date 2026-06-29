"""Module that passes scan but has runtime issues."""

import os
import sys

def compute(value: int) -> int:
    """Compute something."""
    return value ** 2

def main():
    result = compute(42)
    print(f"Result: {result}")
