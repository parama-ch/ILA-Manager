"""Tests for diff and discrepancy detector."""

from ila_manager.diff import compute_diff
from ila_manager.models import (
    Ila,
    Probe,
    ProbeMapping,
    RangeStep,
    Signal,
    TypeNode,
)


def test_diff_width_changed():
    ila = Ila(
        name="ila_0",
        probes=[
            # Probe 0 was saved with width = 8
            Probe(index=0, mapping=ProbeMapping(signal="data_bus"), width=8),
        ],
    )

    # Current HDL now declares data_bus as 16 bits
    current_signals = [
        Signal(
            name="data_bus",
            kind="signal",
            type=TypeNode(kind="vector", left=15, right=0, base="std_logic_vector"),
            line=10,
        ),
    ]

    diffs = compute_diff(ila, current_signals)
    assert len(diffs) == 1
    d = diffs[0]
    assert d.kind == "width_changed"
    assert d.old_width == 8
    assert d.new_width == 16
    assert "follow_new_width" in d.allowed_actions


def test_diff_signal_missing_with_rename_suggestion():
    ila = Ila(
        name="ila_0",
        probes=[
            # Probe mapped to 'rx_byte_data' (width 8)
            Probe(index=0, mapping=ProbeMapping(signal="rx_byte_data"), width=8),
        ],
    )

    # In new HDL, signal was renamed to 'rx_byte_val' (width 8)
    current_signals = [
        Signal(
            name="rx_byte_val",
            kind="signal",
            type=TypeNode(kind="vector", left=7, right=0, base="std_logic_vector"),
            line=5,
        ),
    ]

    diffs = compute_diff(ila, current_signals)
    assert len(diffs) == 1
    d = diffs[0]
    assert d.kind == "signal_missing"
    assert d.suggested_signal == "rx_byte_val"
    assert "remap" in d.allowed_actions


def test_diff_slice_out_of_range():
    ila = Ila(
        name="ila_0",
        probes=[
            # Sliced [15:8]
            Probe(
                index=0,
                mapping=ProbeMapping(
                    signal="bus_val",
                    path=[RangeStep(left=15, right=8, ascending=False)],
                ),
                width=8,
            ),
        ],
    )

    # Signal shrank to 8 bits [7:0]
    current_signals = [
        Signal(
            name="bus_val",
            kind="signal",
            type=TypeNode(kind="vector", left=7, right=0, base="wire"),
            line=20,
        ),
    ]

    diffs = compute_diff(ila, current_signals)
    assert len(diffs) == 1
    assert diffs[0].kind == "slice_out_of_range"
