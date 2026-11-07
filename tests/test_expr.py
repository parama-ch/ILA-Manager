"""Tests for the safe integer expression evaluator."""

from ila_manager.parser.expr import evaluate_expression


def test_basic_arithmetic():
    assert evaluate_expression("8") == 8
    assert evaluate_expression("8 - 1") == 7
    assert evaluate_expression("2 * 16") == 32
    assert evaluate_expression("16 / 4") == 4
    assert evaluate_expression("10 % 3") == 1
    assert evaluate_expression("10 mod 3") == 1
    assert evaluate_expression("2 ** 4") == 16


def test_parens_precedence():
    assert evaluate_expression("(8 - 1) * 2") == 14
    assert evaluate_expression("8 - 1 * 2") == 6
    assert evaluate_expression("((2 + 3) * 4) - 5") == 15


def test_literals():
    # Verilog literals
    assert evaluate_expression("8'hFF") == 255
    assert evaluate_expression("4'b1010") == 10
    assert evaluate_expression("16'd1000") == 1000

    # VHDL literals
    assert evaluate_expression("16#FF#") == 255
    assert evaluate_expression("2#1010#") == 10

    # Hex
    assert evaluate_expression("0xFF") == 255


def test_clog2():
    assert evaluate_expression("$clog2(16)") == 4
    assert evaluate_expression("$clog2(17)") == 5
    assert evaluate_expression("clog2(8)") == 3


def test_symbols():
    syms = {"DATA_WIDTH": 32, "ADDR_WIDTH": 10}
    assert evaluate_expression("DATA_WIDTH - 1", syms) == 31
    assert evaluate_expression("2 ** ADDR_WIDTH", syms) == 1024


def test_unresolved_returns_none():
    assert evaluate_expression("UNKNOWN_VAR - 1", {}) is None
    assert evaluate_expression("", {}) is None
    assert evaluate_expression("   ", {}) is None
