"""
app/services/diff_service.py

Thin wrapper around Python's stdlib `difflib`.
Produces a unified diff string between two prompt texts.
"""

import difflib


def compute_diff(text_a: str, text_b: str, label_a: str = "a", label_b: str = "b") -> str:
    """
    Returns a unified diff between text_a and text_b.

    splitlines(keepends=True) — splits on newlines while preserving the \\n
    characters, which difflib requires to produce correct output.

    unified_diff produces the familiar +/- format used by `git diff`.
    lineterm="" suppresses the extra newline difflib appends to each line.
    """
    lines_a = text_a.splitlines(keepends=True)
    lines_b = text_b.splitlines(keepends=True)

    diff = difflib.unified_diff(
        lines_a,
        lines_b,
        fromfile=label_a,
        tofile=label_b,
        lineterm="",
    )

    return "".join(diff)
