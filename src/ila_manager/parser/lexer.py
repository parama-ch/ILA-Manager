"""Lexical utilities for HDL parsing, comment stripping, and tokenization."""

from __future__ import annotations

from typing import List


def strip_comments_vhdl(text: str) -> str:
    """Strip VHDL comments (-- line comment, /* */ block comment) preserving newlines."""
    out = []
    i = 0
    n = len(text)
    in_string = False

    while i < n:
        if in_string:
            if text[i] == '"':
                if i + 1 < n and text[i + 1] == '"':
                    out.append('""')
                    i += 2
                    continue
                in_string = False
            out.append(text[i])
            i += 1
            continue

        if text[i] == '"':
            in_string = True
            out.append('"')
            i += 1
            continue

        # Single-line comment --
        if i + 1 < n and text[i : i + 2] == "--":
            # skip until newline
            j = i + 2
            while j < n and text[j] != "\n":
                j += 1
            out.append(" ")
            i = j
            continue

        # Block comment /* ... */ (VHDL-2008)
        if i + 1 < n and text[i : i + 2] == "/*":
            j = i + 2
            while j + 1 < n and text[j : j + 2] != "*/":
                if text[j] == "\n":
                    out.append("\n")
                j += 1
            i = j + 2
            out.append(" ")
            continue

        out.append(text[i])
        i += 1

    return "".join(out)


def strip_comments_verilog(text: str) -> str:
    """Strip Verilog comments (// line comment, /* */ block comment) preserving newlines."""
    out = []
    i = 0
    n = len(text)
    in_string = False

    while i < n:
        if in_string:
            if text[i] == "\\":
                out.append(text[i : i + 2])
                i += 2
                continue
            if text[i] == '"':
                in_string = False
            out.append(text[i])
            i += 1
            continue

        if text[i] == '"':
            in_string = True
            out.append('"')
            i += 1
            continue

        # Single-line comment //
        if i + 1 < n and text[i : i + 2] == "//":
            j = i + 2
            while j < n and text[j] != "\n":
                j += 1
            out.append(" ")
            i = j
            continue

        # Block comment /* ... */
        if i + 1 < n and text[i : i + 2] == "/*":
            j = i + 2
            while j + 1 < n and text[j : j + 2] != "*/":
                if text[j] == "\n":
                    out.append("\n")
                j += 1
            i = j + 2
            out.append(" ")
            continue

        out.append(text[i])
        i += 1

    return "".join(out)


def split_declarations(block: str) -> List[str]:
    """Split a semicolon-separated declaration block into individual statements."""
    statements: List[str] = []
    current: List[str] = []
    paren_depth = 0

    for char in block:
        if char in "([{":
            paren_depth += 1
        elif char in ")]}":
            paren_depth = max(0, paren_depth - 1)

        if char == ";" and paren_depth == 0:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(char)

    last = "".join(current).strip()
    if last:
        statements.append(last)

    return statements
