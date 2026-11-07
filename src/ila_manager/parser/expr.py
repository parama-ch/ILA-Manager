"""Safe integer expression evaluator for HDL constants, generics, and parameters."""

from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Tuple

# Token types
TOKEN_NUM = "NUM"
TOKEN_IDENT = "IDENT"
TOKEN_OP = "OP"
TOKEN_LPAREN = "LPAREN"
TOKEN_RPAREN = "RPAREN"
TOKEN_COMMA = "COMMA"


def tokenize(expr: str) -> List[Tuple[str, str]]:
    """Tokenize an HDL arithmetic expression."""
    tokens = []
    i = 0
    n = len(expr)

    while i < n:
        c = expr[i]

        if c.isspace():
            i += 1
            continue

        if c == "(":
            tokens.append((TOKEN_LPAREN, "("))
            i += 1
            continue

        if c == ")":
            tokens.append((TOKEN_RPAREN, ")"))
            i += 1
            continue

        if c == ",":
            tokens.append((TOKEN_COMMA, ","))
            i += 1
            continue

        # Two-character operators
        if i + 1 < n and expr[i : i + 2] in ("**", "//", "<=", ">="):
            tokens.append((TOKEN_OP, expr[i : i + 2]))
            i += 2
            continue

        if c in "+-*/%":
            tokens.append((TOKEN_OP, c))
            i += 1
            continue

        # Hex or binary literals in Verilog: 8'hFF, 16'd100, 4'b1010
        m_verilog_lit = re.match(r"\d+'[bBoOdDhH][0-9a-fA-F_]+", expr[i:])
        if m_verilog_lit:
            val_str = m_verilog_lit.group(0)
            tokens.append((TOKEN_NUM, val_str))
            i += len(val_str)
            continue

        # Hex or binary in VHDL: 16#FF#, 2#1010#
        m_vhdl_based = re.match(r"(\d+)#([0-9a-fA-F_]+)#", expr[i:])
        if m_vhdl_based:
            val_str = m_vhdl_based.group(0)
            tokens.append((TOKEN_NUM, val_str))
            i += len(val_str)
            continue

        # Hex standard: 0x123
        m_hex = re.match(r"0[xX][0-9a-fA-F_]+", expr[i:])
        if m_hex:
            val_str = m_hex.group(0)
            tokens.append((TOKEN_NUM, val_str))
            i += len(val_str)
            continue

        # Decimal integer
        m_dec = re.match(r"\d+", expr[i:])
        if m_dec:
            tokens.append((TOKEN_NUM, m_dec.group(0)))
            i += len(m_dec.group(0))
            continue

        # Identifier or keyword ($clog2, mod, etc.)
        m_ident = re.match(r"(\$?[a-zA-Z_][a-zA-Z0-9_]*)", expr[i:])
        if m_ident:
            ident_str = m_ident.group(0)
            if ident_str.lower() == "mod":
                tokens.append((TOKEN_OP, "%"))
            else:
                tokens.append((TOKEN_IDENT, ident_str))
            i += len(ident_str)
            continue

        # Unknown character - skip
        i += 1

    return tokens


def parse_literal(val_str: str) -> Optional[int]:
    """Parse numeric literal from Verilog, VHDL, or decimal formats."""
    # Verilog: 8'hFF, 16'd20, 4'b1011
    m_v = re.match(r"\d+'([bBoOdDhH])([0-9a-fA-F_]+)", val_str)
    if m_v:
        base_char = m_v.group(1).lower()
        digits = m_v.group(2).replace("_", "")
        if base_char == "h":
            return int(digits, 16)
        if base_char == "d":
            return int(digits, 10)
        if base_char == "b":
            return int(digits, 2)
        if base_char == "o":
            return int(digits, 8)

    # VHDL based: 16#FF#, 2#1010#
    m_vh = re.match(r"(\d+)#([0-9a-fA-F_]+)#", val_str)
    if m_vh:
        base = int(m_vh.group(1))
        digits = m_vh.group(2).replace("_", "")
        return int(digits, base)

    # Python/C hex
    if val_str.lower().startswith("0x"):
        return int(val_str, 16)

    # Decimal
    digits = val_str.replace("_", "")
    if digits.isdigit():
        return int(digits, 10)

    return None


class ExprParser:
    """Recursive-descent parser for arithmetic expressions."""

    def __init__(self, tokens: List[Tuple[str, str]], symbols: Dict[str, int]):
        self.tokens = tokens
        self.symbols = {k.lower(): v for k, v in symbols.items()}
        self.pos = 0

    def peek(self) -> Optional[Tuple[str, str]]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self, expected_type: Optional[str] = None) -> Optional[Tuple[str, str]]:
        tok = self.peek()
        if tok is None:
            return None
        if expected_type and tok[0] != expected_type:
            return None
        self.pos += 1
        return tok

    def parse(self) -> Optional[int]:
        val = self.parse_expr()
        if self.pos != len(self.tokens):
            return None
        return val

    def parse_expr(self) -> Optional[int]:
        return self.parse_additive()

    def parse_additive(self) -> Optional[int]:
        left = self.parse_multiplicative()
        if left is None:
            return None

        while True:
            tok = self.peek()
            if tok and tok[0] == TOKEN_OP and tok[1] in ("+", "-"):
                self.consume()
                right = self.parse_multiplicative()
                if right is None:
                    return None
                if tok[1] == "+":
                    left = left + right
                else:
                    left = left - right
            else:
                break

        return left

    def parse_multiplicative(self) -> Optional[int]:
        left = self.parse_power()
        if left is None:
            return None

        while True:
            tok = self.peek()
            if tok and tok[0] == TOKEN_OP and tok[1] in ("*", "/", "//", "%"):
                self.consume()
                right = self.parse_power()
                if right is None:
                    return None
                if tok[1] == "*":
                    left = left * right
                elif tok[1] in ("/", "//"):
                    if right == 0:
                        return None
                    left = left // right
                elif tok[1] == "%":
                    if right == 0:
                        return None
                    left = left % right
            else:
                break

        return left

    def parse_power(self) -> Optional[int]:
        left = self.parse_unary()
        if left is None:
            return None

        tok = self.peek()
        if tok and tok[0] == TOKEN_OP and tok[1] == "**":
            self.consume()
            right = self.parse_power()
            if right is None:
                return None
            return left**right

        return left

    def parse_unary(self) -> Optional[int]:
        tok = self.peek()
        if tok and tok[0] == TOKEN_OP and tok[1] in ("+", "-"):
            self.consume()
            val = self.parse_unary()
            if val is None:
                return None
            return val if tok[1] == "+" else -val

        return self.parse_primary()

    def parse_primary(self) -> Optional[int]:
        tok = self.peek()
        if tok is None:
            return None

        if tok[0] == TOKEN_NUM:
            self.consume()
            return parse_literal(tok[1])

        if tok[0] == TOKEN_IDENT:
            name = tok[1]
            self.consume()

            # Function call e.g. $clog2(arg) or clog2(arg)
            if self.peek() and self.peek()[0] == TOKEN_LPAREN:
                self.consume(TOKEN_LPAREN)
                arg = self.parse_expr()
                if not self.consume(TOKEN_RPAREN):
                    return None
                if arg is None:
                    return None
                if name.lower() in ("$clog2", "clog2"):
                    if arg <= 1:
                        return 1
                    return math.ceil(math.log2(arg))
                return None

            # Variable / symbol lookup
            sym_key = name.lower()
            return self.symbols.get(sym_key)

        if tok[0] == TOKEN_LPAREN:
            self.consume(TOKEN_LPAREN)
            val = self.parse_expr()
            if not self.consume(TOKEN_RPAREN):
                return None
            return val

        return None


def evaluate_expression(expr: str, symbols: Optional[Dict[str, int]] = None) -> Optional[int]:
    """Safely evaluate an arithmetic expression using integer symbols.

    Returns:
        Evaluated integer or None if the expression cannot be resolved.
    """
    if not expr or not expr.strip():
        return None

    # Fast path for raw digits
    clean = expr.strip()
    if clean.isdigit():
        return int(clean)

    tokens = tokenize(clean)
    if not tokens:
        return None

    parser = ExprParser(tokens, symbols or {})
    try:
        return parser.parse()
    except Exception:
        return None
