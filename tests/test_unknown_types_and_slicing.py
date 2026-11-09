"""Tests for Unknown Type Detection, Fallback Warnings, Manual Overrides, and Array Slicing."""

from ila_manager.generators.tcl import generate_tcl
from ila_manager.generators.vhdl import generate_vhdl
from ila_manager.models import (
    BitStep,
    Ila,
    IndexStep,
    PackageDefinition,
    PackageRegistry,
    Probe,
    ProbeMapping,
    Project,
    RangeStep,
    Signal,
    TypeNode,
)
from ila_manager.selection import resolve_selection


def test_unknown_type_detection():
    """Verify unknown type is marked kind='unknown' and computed_width() is None."""
    node = TypeNode(kind="unknown", base="mystery_protocol_bus_t")
    assert node.kind == "unknown"
    assert node.computed_width() is None
    assert node.summary() == "mystery_protocol_bus_t"

    sig = Signal(name="unknown_sig", kind="signal", type=node, line=10)
    assert sig.is_unknown is True
    assert sig.to_dict()["is_unknown"] is True


def test_unknown_type_fallback_resolution():
    """Verify unknown type defaults to width 1 in resolve_selection."""
    sig = Signal(
        name="unknown_sig",
        kind="signal",
        type=TypeNode(kind="unknown", base="foo_t"),
        line=10,
    )
    mapping = ProbeMapping(signal="unknown_sig", path=[])
    res = resolve_selection(mapping, sig)
    assert res.width == 1
    assert res.signal_name == "unknown_sig"
    assert res.is_single_bit is True
    assert res.vhdl_expr == "unknown_sig"


def test_unknown_type_vhdl_and_tcl_generation():
    """Verify code generators handle unknown type with warning comments."""
    sig = Signal(
        name="unknown_sig",
        kind="signal",
        type=TypeNode(kind="unknown", base="vendor_bus_t"),
        line=10,
    )
    ila = Ila(
        name="ila_0",
        probes=[Probe(index=0, mapping=ProbeMapping(signal="unknown_sig"), width=1)],
    )

    vhdl = generate_vhdl(ila, [sig])
    tcl = generate_tcl(ila, [sig])

    # Vivado TCL sets width 1 and warning comment
    assert "CONFIG.C_PROBE0_WIDTH {1}" in tcl
    assert "WARNING" in tcl

    # VHDL mapping generates single-bit probe connection probe0(0) and warning comment
    assert "probe0(0)" in vhdl
    assert "unknown_sig" in vhdl
    assert "WARNING" in vhdl


def test_manual_width_override_on_unknown_type():
    """Verify user manual override (e.g. width=48) generates correct multi-bit port map and TCL."""
    sig = Signal(
        name="unknown_sig",
        kind="signal",
        type=TypeNode(kind="unknown", base="vendor_bus_t"),
        line=10,
    )
    # User manually overrides probe width to 48
    ila = Ila(
        name="ila_0",
        probes=[Probe(index=0, mapping=ProbeMapping(signal="unknown_sig"), width=48)],
    )

    tcl = generate_tcl(ila, [sig])
    vhdl = generate_vhdl(ila, [sig])

    assert "CONFIG.C_PROBE0_WIDTH {48}" in tcl
    # Multi-bit probe MUST NOT have (0) index
    assert "probe0(0)" not in vhdl
    assert "probe0" in vhdl and "unknown_sig" in vhdl


def test_array_indexing_selection():
    """Verify selecting array index ch_data(2) extracts element vector and width."""
    elem_type = TypeNode(kind="vector", left=31, right=0, base="std_logic_vector")
    arr_type = TypeNode(kind="array", left=0, right=3, element=elem_type, base="channel_data_t")
    sig = Signal(name="ch_data", kind="signal", type=arr_type, line=5)

    mapping = ProbeMapping(signal="ch_data", path=[IndexStep(index=2)])
    res = resolve_selection(mapping, sig)
    assert res.vhdl_expr == "ch_data(2)"
    assert res.verilog_expr == "ch_data[2]"
    assert res.width == 32
    assert not res.is_single_bit


def test_array_indexing_and_bit_slice_chain():
    """Verify chaining IndexStep and RangeStep: ch_data(2)(15 downto 8)."""
    elem_type = TypeNode(kind="vector", left=31, right=0, base="std_logic_vector")
    arr_type = TypeNode(kind="array", left=0, right=3, element=elem_type, base="channel_data_t")
    sig = Signal(name="ch_data", kind="signal", type=arr_type, line=5)

    mapping = ProbeMapping(
        signal="ch_data",
        path=[IndexStep(index=2), RangeStep(left=15, right=8, ascending=False)],
    )
    res = resolve_selection(mapping, sig)
    assert res.vhdl_expr == "ch_data(2)(15 downto 8)"
    assert res.verilog_expr == "ch_data[2][15:8]"
    assert res.width == 8
    assert not res.is_single_bit


def test_array_indexing_single_bit_syntax():
    """Verify indexing single bit of array element generates probeN(0) => arr(1)(0)."""
    elem_type = TypeNode(kind="vector", left=7, right=0, base="std_logic_vector")
    arr_type = TypeNode(kind="array", left=0, right=3, element=elem_type, base="buf_t")
    sig = Signal(name="buf_sig", kind="signal", type=arr_type, line=12)

    mapping = ProbeMapping(signal="buf_sig", path=[IndexStep(index=1), BitStep(bit=0)])
    res = resolve_selection(mapping, sig)
    assert res.vhdl_expr == "buf_sig(1)(0)"
    assert res.width == 1
    assert res.is_single_bit

    ila = Ila(name="ila_0", probes=[Probe(index=0, mapping=mapping, width=1)])
    vhdl = generate_vhdl(ila, [sig])
    assert "probe0(0)" in vhdl
    assert "buf_sig(1)(0)" in vhdl


def test_unknown_type_slicing_with_range_step():
    """Verify slicing an unknown type with RangeStep computes range width and completes path."""
    sig = Signal(
        name="raw_bus",
        kind="signal",
        type=TypeNode(kind="unknown", base="opaque_bus_t"),
        line=20,
    )
    mapping = ProbeMapping(
        signal="raw_bus",
        path=[RangeStep(left=31, right=16, ascending=False)],
    )
    res = resolve_selection(mapping, sig)
    assert res.vhdl_expr == "raw_bus(31 downto 16)"
    assert res.verilog_expr == "raw_bus[31:16]"
    assert res.width == 16
    assert not res.is_single_bit


def test_package_registry_serialization():
    """Verify PackageDefinition, PackageRegistry, and Project serialization roundtrip."""
    pkg = PackageDefinition(
        name="test_pkg",
        file="pkg.vhd",
        line=1,
        constants={"WIDTH": 16},
        types={"word_t": TypeNode(kind="vector", left=15, right=0, base="std_logic_vector")},
        use_clauses=["work.base_pkg.all"],
    )
    reg = PackageRegistry()
    reg.add_package(pkg)

    proj = Project(source_files=["pkg.vhd", "top.vhd"], package_registry=reg)
    d = proj.to_dict()
    assert "package_registry" in d
    assert "test_pkg" in d["package_registry"]

    proj_restored = Project.from_dict(d)
    assert "test_pkg" in proj_restored.package_registry.packages
    restored_pkg = proj_restored.package_registry.packages["test_pkg"]
    assert restored_pkg.constants["WIDTH"] == 16
    assert restored_pkg.types["word_t"].computed_width() == 16
