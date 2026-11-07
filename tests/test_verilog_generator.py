"""Tests for Verilog named port-map generator."""

from ila_manager.generators.verilog import generate_verilog
from ila_manager.models import (
    Ila,
    Probe,
    ProbeMapping,
    RangeStep,
    Signal,
    TypeNode,
)


def test_verilog_generator():
    signals = [
        Signal(name="rx_valid", kind="signal", type=TypeNode(kind="bit", base="wire"), line=1),
        Signal(
            name="rx_data",
            kind="signal",
            type=TypeNode(kind="vector", left=31, right=0, base="wire"),
            line=2,
        ),
    ]

    ila = Ila(
        name="ila_0",
        clock="sys_clk",
        probes=[
            Probe(index=0, mapping=ProbeMapping(signal="rx_valid"), width=1),
            Probe(
                index=1,
                mapping=ProbeMapping(
                    signal="rx_data",
                    path=[RangeStep(left=15, right=8, ascending=False)],
                ),
                width=8,
            ),
        ],
    )

    code = generate_verilog(ila, signals=signals)
    assert "ila_0 u_ila_0 (" in code
    assert ".clk" in code and "(sys_clk)" in code
    assert ".probe0" in code and "(rx_valid)" in code
    assert ".probe1" in code and "(rx_data[15:8])" in code
