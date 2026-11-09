"""Adversarial challenge tests for Unknown Type UX, Fallback, Slicing, and Web API (Challenger 6)."""

import re
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from ila_manager.generators.tcl import generate_tcl
from ila_manager.generators.vhdl import generate_vhdl
from ila_manager.models import (
    BitStep,
    FieldStep,
    Ila,
    IndexStep,
    Probe,
    ProbeMapping,
    RangeStep,
    Signal,
    TypeNode,
)
from ila_manager.selection import resolve_selection
from ila_manager.server import app

client = TestClient(app)


# ==============================================================================
# 1. FastAPI /api/hdl/parse Edge Cases
# ==============================================================================

def test_api_parse_multifile_forward_and_reverse_order():
    """Verify /api/hdl/parse resolves custom types regardless of file order."""
    pkg_vhd = """
    library ieee;
    use ieee.std_logic_1164.all;

    package sensor_pkg is
        constant SENSOR_W : integer := 20;
        type sensor_sample_t is array (0 to 3) of std_logic_vector(SENSOR_W - 1 downto 0);
    end package sensor_pkg;
    """

    top_vhd = """
    library ieee;
    use ieee.std_logic_1164.all;
    use work.sensor_pkg.all;

    entity sensor_top is
        port (
            clk     : in  std_logic;
            samples : in  sensor_sample_t;
            unk_bus : in  unknown_device_t
        );
    end entity sensor_top;
    """

    # Reverse order payload (top before package)
    res_rev = client.post(
        "/api/hdl/parse",
        json={
            "files": [
                {"filename": "sensor_top.vhd", "content": top_vhd},
                {"filename": "sensor_pkg.vhd", "content": pkg_vhd},
            ]
        },
    )
    assert res_rev.status_code == 200
    data_rev = res_rev.json()
    assert "sensor_pkg" in data_rev["packages"]
    assert "sensor_top" in data_rev["units"]
    sigs_rev = {s["name"]: s for s in data_rev["units"]["sensor_top"]}

    # sensor_sample_t = 4 * 20 = 80 bits
    assert sigs_rev["samples"]["type"]["kind"] == "array"
    assert sigs_rev["samples"]["width"] == 80
    assert sigs_rev["samples"]["is_unknown"] is False

    # unknown type check
    assert sigs_rev["unk_bus"]["is_unknown"] is True
    assert sigs_rev["unk_bus"]["width"] is None
    assert sigs_rev["unk_bus"]["type"]["kind"] == "unknown"


def test_api_parse_mixed_vhdl_verilog_payloads():
    """Verify /api/hdl/parse correctly handles combined VHDL and Verilog files."""
    vhdl_code = """
    library ieee;
    use ieee.std_logic_1164.all;

    entity vhdl_filter is
        port (
            clk   : in  std_logic;
            coeff : in  std_logic_vector(11 downto 0);
            y_out : out std_logic_vector(15 downto 0)
        );
    end entity vhdl_filter;
    """

    verilog_code = """
    module verilog_top (
        input  wire        sys_clk,
        input  wire [23:0] audio_in,
        output reg  [23:0] audio_out
    );
        reg [7:0] gain_ctrl;
    endmodule
    """

    res = client.post(
        "/api/hdl/parse",
        json={
            "files": [
                {"filename": "filter.vhd", "content": vhdl_code},
                {"filename": "top.v", "content": verilog_code},
            ]
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert "filter.vhd" in data["files"]
    assert "top.v" in data["files"]
    assert "vhdl_filter" in data["units"]
    assert "verilog_top" in data["units"]

    vhd_sigs = {s["name"]: s for s in data["units"]["vhdl_filter"]}
    assert vhd_sigs["coeff"]["width"] == 12

    vlg_sigs = {s["name"]: s for s in data["units"]["verilog_top"]}
    assert vlg_sigs["audio_in"]["width"] == 24
    assert vlg_sigs["gain_ctrl"]["width"] == 8


def test_api_parse_edge_cases_and_contract_resilience():
    """Verify robust handling of empty requests, missing disk paths, and malformed files."""
    # 1. Empty payload
    r_empty = client.post("/api/hdl/parse", json={})
    assert r_empty.status_code == 200
    assert r_empty.json() == {"units": {}, "files": [], "packages": []}

    # 2. Non-existent disk paths
    r_bad_path = client.post(
        "/api/hdl/parse",
        json={"paths": ["/tmp/does_not_exist_xyz.vhd", "/tmp/does_not_exist_abc.v"]},
    )
    assert r_bad_path.status_code == 200
    assert r_bad_path.json() == {"units": {}, "files": [], "packages": []}

    # 3. Corrupt syntax does not crash server
    r_corrupt = client.post(
        "/api/hdl/parse",
        json={"files": [{"filename": "bad.vhd", "content": "NOT VALID VHDL CODE AT ALL @@@@"}]},
    )
    assert r_corrupt.status_code == 200
    assert r_corrupt.json()["files"] == ["bad.vhd"]
    assert r_corrupt.json()["units"] == {}

    # 4. Mixed on-disk and uploaded files
    with tempfile.TemporaryDirectory() as tmpdir:
        p_vhd = Path(tmpdir) / "disk_unit.vhd"
        p_vhd.write_text(
            """
            library ieee;
            use ieee.std_logic_1164.all;
            entity disk_unit is
                port ( disk_pin : in std_logic );
            end entity disk_unit;
            """,
            encoding="utf-8",
        )
        r_mixed = client.post(
            "/api/hdl/parse",
            json={
                "paths": [str(p_vhd)],
                "files": [
                    {
                        "filename": "mem.v",
                        "content": "module mem (input wire [7:0] addr); endmodule",
                    }
                ],
            },
        )
        assert r_mixed.status_code == 200
        d_mixed = r_mixed.json()
        assert str(p_vhd) in d_mixed["files"]
        assert "mem.v" in d_mixed["files"]
        assert "disk_unit" in d_mixed["units"]
        assert "mem" in d_mixed["units"]


# ==============================================================================
# 2. resolve_selection and Complex Slicing Chains
# ==============================================================================

def test_resolve_selection_complex_array_and_record_chains():
    """Verify complex indexing chains: arr(2)(15 downto 8) and rec.field(0)."""
    # Chain 1: arr_sig(2)(15 downto 8)
    elem_vec = TypeNode(kind="vector", left=31, right=0, base="std_logic_vector")
    arr_type = TypeNode(kind="array", left=0, right=3, element=elem_vec, base="arr_type_t")
    sig_arr = Signal(name="arr_sig", kind="signal", type=arr_type, line=10)

    mapping_1 = ProbeMapping(
        signal="arr_sig",
        path=[IndexStep(index=2), RangeStep(left=15, right=8, ascending=False)],
    )
    res_1 = resolve_selection(mapping_1, sig_arr)
    assert res_1.vhdl_expr == "arr_sig(2)(15 downto 8)"
    assert res_1.verilog_expr == "arr_sig[2][15:8]"
    assert res_1.width == 8
    assert res_1.is_single_bit is False

    # Chain 2: rec_sig.field(0)
    rec_type = TypeNode(
        kind="record",
        fields={
            "flags": TypeNode(kind="vector", left=3, right=0, base="std_logic_vector"),
            "field": TypeNode(kind="vector", left=7, right=0, base="std_logic_vector"),
        },
        base="msg_packet_t",
    )
    sig_rec = Signal(name="rec_sig", kind="signal", type=rec_type, line=20)

    mapping_2 = ProbeMapping(
        signal="rec_sig",
        path=[FieldStep(field="field"), BitStep(bit=0)],
    )
    res_2 = resolve_selection(mapping_2, sig_rec)
    assert res_2.vhdl_expr == "rec_sig.field(0)"
    assert res_2.verilog_expr == "rec_sig.field[0]"
    assert res_2.width == 1
    assert res_2.is_single_bit is True

    # Chain 3: Nested array of records: arr_rec(1).field(7 downto 0)
    arr_rec_type = TypeNode(kind="array", left=0, right=1, element=rec_type, base="bundle_t")
    sig_arr_rec = Signal(name="arr_rec", kind="signal", type=arr_rec_type, line=30)
    mapping_3 = ProbeMapping(
        signal="arr_rec",
        path=[IndexStep(index=1), FieldStep(field="field"), RangeStep(left=7, right=0, ascending=False)],
    )
    res_3 = resolve_selection(mapping_3, sig_arr_rec)
    assert res_3.vhdl_expr == "arr_rec(1).field(7 downto 0)"
    assert res_3.verilog_expr == "arr_rec[1].field[7:0]"
    assert res_3.width == 8
    assert res_3.is_single_bit is False


def test_resolve_selection_unknown_type_slicing_and_fallback():
    """Verify unknown type fallback width=1 and custom slicing on unknown type."""
    sig_unk = Signal(
        name="opaque_sig",
        kind="signal",
        type=TypeNode(kind="unknown", base="vendor_opaque_t"),
        line=42,
    )

    # Full unknown signal mapping defaults to width 1 and is_single_bit True
    map_full = ProbeMapping(signal="opaque_sig", path=[])
    res_full = resolve_selection(map_full, sig_unk)
    assert res_full.width == 1
    assert res_full.is_single_bit is True
    assert res_full.vhdl_expr == "opaque_sig"

    # Unknown signal sliced with RangeStep(63 downto 32)
    map_slice = ProbeMapping(
        signal="opaque_sig",
        path=[RangeStep(left=63, right=32, ascending=False)],
    )
    res_slice = resolve_selection(map_slice, sig_unk)
    assert res_slice.vhdl_expr == "opaque_sig(63 downto 32)"
    assert res_slice.verilog_expr == "opaque_sig[63:32]"
    assert res_slice.width == 32
    assert res_slice.is_single_bit is False


# ==============================================================================
# 3. Manual Width Overrides and Code Generators (VHDL and Vivado TCL)
# ==============================================================================

def test_code_generators_single_vs_multibit_probe_syntax():
    """Verify single-bit probeN(0) => sig vs multi-bit probeN => sig in VHDL and TCL."""
    sig_unk = Signal(name="unk_bus", kind="signal", type=TypeNode(kind="unknown", base="unk_t"), line=1)
    sig_bit = Signal(name="ready", kind="signal", type=TypeNode(kind="bit", base="std_logic"), line=2)
    sig_vec = Signal(name="data", kind="signal", type=TypeNode(kind="vector", left=15, right=0, base="std_logic_vector"), line=3)

    # 1. Default unknown width (1-bit): probe0(0) => unk_bus
    ila_def = Ila(
        name="ila_0",
        probes=[
            Probe(index=0, mapping=ProbeMapping(signal="unk_bus"), width=1),
            Probe(index=1, mapping=ProbeMapping(signal="ready"), width=1),
            Probe(index=2, mapping=ProbeMapping(signal="data"), width=16),
        ],
    )
    vhdl_def = generate_vhdl(ila_def, [sig_unk, sig_bit, sig_vec])
    tcl_def = generate_tcl(ila_def, [sig_unk, sig_bit, sig_vec])

    assert "probe0(0)" in vhdl_def
    assert "probe1(0)" in vhdl_def
    assert "probe2(0)" not in vhdl_def
    assert "probe2 " in vhdl_def or "probe2\t" in vhdl_def or "probe2 =>" in vhdl_def
    assert "CONFIG.C_PROBE0_WIDTH {1}" in tcl_def
    assert "CONFIG.C_PROBE1_WIDTH {1}" in tcl_def
    assert "CONFIG.C_PROBE2_WIDTH {16}" in tcl_def

    # Warnings emitted in both VHDL and TCL
    assert "WARNING" in vhdl_def
    assert "unresolved type; defaulted to 1 bit(s)" in vhdl_def
    assert "WARNING" in tcl_def
    assert "defaulted to 1 bit(s)" in tcl_def

    # 2. Manual width override to 48 bits on unknown type
    ila_ovr = Ila(
        name="ila_0",
        probes=[
            Probe(index=0, mapping=ProbeMapping(signal="unk_bus"), width=48),
        ],
    )
    vhdl_ovr = generate_vhdl(ila_ovr, [sig_unk])
    tcl_ovr = generate_tcl(ila_ovr, [sig_unk])

    # probe0 must NOT have (0) index because width is 48
    assert "probe0(0)" not in vhdl_ovr
    assert "probe0 " in vhdl_ovr or "probe0\t" in vhdl_ovr or "probe0 =>" in vhdl_ovr
    assert "CONFIG.C_PROBE0_WIDTH {48}" in tcl_ovr
    assert "defaulted to 48 bit(s)" in vhdl_ovr
    assert "defaulted to 48 bit(s)" in tcl_ovr

    # 3. Clean ILA with only known resolved types -> NO warnings emitted
    ila_clean = Ila(
        name="ila_clean",
        probes=[Probe(index=0, mapping=ProbeMapping(signal="data"), width=16)],
    )
    vhdl_clean = generate_vhdl(ila_clean, [sig_vec])
    tcl_clean = generate_tcl(ila_clean, [sig_vec])
    assert "WARNING" not in vhdl_clean
    assert "WARNING" not in tcl_clean


# ==============================================================================
# 4. Frontend Regex Parsing with Diverse Whitespace and Formatting
# ==============================================================================

def test_frontend_regex_parsing_diverse_formatting():
    """Simulate frontend regex logic across diverse whitespace, cases, and brackets."""
    def parse_range(raw_input: str):
        raw = raw_input.strip()
        path = []
        computed_w = None

        m_downto = re.search(r"(\d+)\s+downto\s+(\d+)", raw, re.IGNORECASE)
        m_to = re.search(r"(\d+)\s+to\s+(\d+)", raw, re.IGNORECASE)
        m_colon = re.search(r"\[?\s*(\d+)\s*:\s*(\d+)\s*\]?", raw)

        if m_downto:
            left_idx = int(m_downto.group(1))
            right_idx = int(m_downto.group(2))
            path.append({"step": "range", "left": left_idx, "right": right_idx, "ascending": False})
            computed_w = abs(left_idx - right_idx) + 1
        elif m_to:
            left_idx = int(m_to.group(1))
            right_idx = int(m_to.group(2))
            path.append({"step": "range", "left": left_idx, "right": right_idx, "ascending": True})
            computed_w = abs(left_idx - right_idx) + 1
        elif m_colon:
            left_idx = int(m_colon.group(1))
            right_idx = int(m_colon.group(2))
            path.append({"step": "range", "left": left_idx, "right": right_idx, "ascending": left_idx < right_idx})
            computed_w = abs(left_idx - right_idx) + 1
        elif re.match(r"^\d+$", raw):
            bit_val = int(raw)
            path.append({"step": "bit", "bit": bit_val})
            computed_w = 1

        return path, computed_w

    # Diverse test inputs
    cases = [
        ("15   downto    0", "range", 15, 0, False, 16),
        ("  15  downto  0  ", "range", 15, 0, False, 16),
        ("15\tdownto\t0", "range", 15, 0, False, 16),
        ("31 DOWNTO 16", "range", 31, 16, False, 16),
        ("7 DownTo 0", "range", 7, 0, False, 8),
        ("0  TO  7", "range", 0, 7, True, 8),
        ("0 to 7", "range", 0, 7, True, 8),
        ("  0   To   31  ", "range", 0, 31, True, 32),
        ("[15:0]", "range", 15, 0, False, 16),
        ("[ 15 : 0 ]", "range", 15, 0, False, 16),
        ("15:0", "range", 15, 0, False, 16),
        ("  15  :  0  ", "range", 15, 0, False, 16),
        ("[0:7]", "range", 0, 7, True, 8),
        ("3", "bit", None, None, None, 1),
        ("  3  ", "bit", None, None, None, 1),
        ("0", "bit", None, None, None, 1),
        ("127", "bit", None, None, None, 1),
        ("(15 downto 0)", "range", 15, 0, False, 16),
        ("(0 to 7)", "range", 0, 7, True, 8),
    ]

    for raw, expected_step, exp_l, exp_r, exp_asc, exp_w in cases:
        p, w = parse_range(raw)
        assert len(p) == 1, f"Failed to parse: {raw}"
        assert p[0]["step"] == expected_step
        assert w == exp_w
        if expected_step == "range":
            assert p[0]["left"] == exp_l
            assert p[0]["right"] == exp_r
            assert p[0]["ascending"] == exp_asc
