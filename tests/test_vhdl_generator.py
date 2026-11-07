"""Tests for VHDL direct entity port-map generator."""

from ila_manager.generators.vhdl import generate_vhdl
from ila_manager.models import (
    Ila,
    Probe,
    ProbeMapping,
    RangeStep,
    Signal,
    TypeNode,
)


def test_vhdl_generator_direct_entity_and_1bit_syntax():
    signals = [
        Signal(name="rx_valid", kind="signal", type=TypeNode(kind="bit", base="std_logic"), line=1),
        Signal(
            name="rx_data",
            kind="signal",
            type=TypeNode(kind="vector", left=15, right=0, base="std_logic_vector"),
            line=2,
        ),
        Signal(
            name="pkt_cnt",
            kind="signal",
            type=TypeNode(kind="vector", left=7, right=0, base="unsigned"),
            line=3,
        ),
        Signal(
            name="int_cnt",
            kind="signal",
            type=TypeNode(kind="integer", left=0, right=255, base="integer"),
            line=4,
        ),
    ]

    ila = Ila(
        name="ila_0",
        clock="clk_100mhz",
        probes=[
            # Probe 0: 1-bit signal -> MUST generate probe0(0) => rx_valid
            Probe(index=0, mapping=ProbeMapping(signal="rx_valid"), width=1),
            # Probe 1: 8-bit slice of 16-bit vector -> probe1 => rx_data(15 downto 8)
            Probe(
                index=1,
                mapping=ProbeMapping(
                    signal="rx_data",
                    path=[RangeStep(left=15, right=8, ascending=False)],
                ),
                width=8,
            ),
            # Probe 2: unsigned vector -> probe2 => std_logic_vector(pkt_cnt)
            Probe(index=2, mapping=ProbeMapping(signal="pkt_cnt"), width=8),
            # Probe 3: integer -> uses intermediate signal
            Probe(index=3, mapping=ProbeMapping(signal="int_cnt"), width=8),
            # Probe 4: unmapped
            Probe(index=4, mapping=None, width=1),
        ],
    )

    vhdl = generate_vhdl(ila, signals=signals)

    # 1. Direct entity instantiation (no component declaration)
    assert "u_ila_0 : entity work.ila_0" in vhdl
    assert "port map (" in vhdl
    assert "clk" in vhdl and "clk_100mhz" in vhdl

    # 2. Strict 1-bit vector mapping syntax: probe0(0) => rx_valid
    assert "probe0(0)" in vhdl
    assert "rx_valid" in vhdl

    # 3. Vector slice: probe1 => rx_data(15 downto 8)
    assert "probe1" in vhdl
    assert "rx_data(15 downto 8)" in vhdl

    # 4. Unsigned conversion
    assert "std_logic_vector(pkt_cnt)" in vhdl

    # 5. Intermediate signal for integer
    assert "signal ila_ila_0_p3 : std_logic_vector(7 downto 0);" in vhdl
    assert "ila_ila_0_p3 <= std_logic_vector(to_unsigned(int_cnt, 8));" in vhdl
    assert "probe3" in vhdl and "ila_ila_0_p3" in vhdl

    # 6. Unmapped probe commented
    assert "-- probe4" in vhdl and "<unmapped>" in vhdl
