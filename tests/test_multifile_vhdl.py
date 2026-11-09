"""Tests for Multi-File VHDL Package & Cross-File Custom Type Resolution."""

from pathlib import Path

from ila_manager.parser.vhdl import parse_vhdl_multi


def test_multifile_forward_order(multi_file_vhdl_project_dict):
    """Verify package types resolve when package is parsed before entity."""
    files = [
        ("pkg_types.vhd", multi_file_vhdl_project_dict["pkg_types.vhd"]),
        ("top_dsp_core.vhd", multi_file_vhdl_project_dict["top_dsp_core.vhd"]),
    ]
    units = parse_vhdl_multi(files)
    assert "top_dsp_core.rtl" in units
    sig_map = {s.name: s for s in units["top_dsp_core.rtl"]}

    # Verify array width: 4 channels * 32 bits = 128 bits
    assert sig_map["ch_buffer"].type.kind == "array"
    assert sig_map["ch_buffer"].type.computed_width() == 128

    # Verify record width: 32 (tdata) + 4 (tstrb) + 1 (tvalid) + 1 (tlast) + 4 (tid) = 42 bits
    assert sig_map["tx_stream"].type.kind == "record"
    assert sig_map["tx_stream"].type.computed_width() == 42

    # Verify enum width: 5 states -> ceil(log2(5)) = 3 bits
    assert sig_map["curr_state"].type.kind == "enum"
    assert sig_map["curr_state"].type.computed_width() == 3

    # Verify 2D array width: 2 * 4 * 8 = 64 bits
    assert sig_map["mem_matrix"].type.kind == "array"
    assert sig_map["mem_matrix"].type.computed_width() == 64

    # Verify nested type: stream_bundle_t is array (0 to 1) of axis_stream_t = 2 * 42 = 84 bits
    assert sig_map["bundle"].type.kind == "array"
    assert sig_map["bundle"].type.computed_width() == 84

    # Verify package constant evaluation in vector width: C_DATA_W = 32
    assert sig_map["raw_word"].type.computed_width() == 32

    # Verify unknown signal is flagged
    assert sig_map["unknown_sig"].is_unknown is True
    assert sig_map["unknown_sig"].type.computed_width() is None


def test_multifile_reverse_order(multi_file_vhdl_project_dict):
    """Verify 2-pass parser resolves types regardless of file order (entity before package)."""
    files = [
        ("top_dsp_core.vhd", multi_file_vhdl_project_dict["top_dsp_core.vhd"]),
        ("pkg_types.vhd", multi_file_vhdl_project_dict["pkg_types.vhd"]),
    ]
    units = parse_vhdl_multi(files)
    assert "top_dsp_core.rtl" in units
    sig_map = {s.name: s for s in units["top_dsp_core.rtl"]}

    assert sig_map["ch_buffer"].type.computed_width() == 128
    assert sig_map["tx_stream"].type.computed_width() == 42
    assert sig_map["curr_state"].type.computed_width() == 3
    assert sig_map["mem_matrix"].type.computed_width() == 64
    assert sig_map["bundle"].type.computed_width() == 84
    assert sig_map["raw_word"].type.computed_width() == 32
    assert sig_map["unknown_sig"].is_unknown is True


def test_multifile_from_disk_paths(multi_file_vhdl_disk_dir: Path):
    """Verify parsing via disk file paths."""
    paths = [
        str(multi_file_vhdl_disk_dir / "top_dsp_core.vhd"),
        str(multi_file_vhdl_disk_dir / "pkg_types.vhd"),
    ]
    file_tuples = [(p, Path(p).read_text(encoding="utf-8")) for p in paths]
    units, packages = parse_vhdl_multi(file_tuples)
    assert "top_dsp_core.rtl" in units
    assert "pkg_types" in packages
    sig_map = {s.name: s for s in units["top_dsp_core.rtl"]}
    assert sig_map["ch_buffer"].type.computed_width() == 128


def test_cross_package_dependency_fixpoint():
    """Verify fixpoint iteration resolves cross-package dependencies in reverse order."""
    pkg_b = """
    library ieee;
    use ieee.std_logic_1164.all;
    use work.pkg_a.all;

    package pkg_b is
        constant C_TOTAL_W : integer := C_BASE_W * 2;
        type bundle_b_t is array (0 to 1) of header_a_t;
    end package pkg_b;
    """

    pkg_a = """
    library ieee;
    use ieee.std_logic_1164.all;

    package pkg_a is
        constant C_BASE_W : integer := 16;
        type header_a_t is record
            magic : std_logic_vector(7 downto 0);
            flags : std_logic_vector(3 downto 0);
        end record;
    end package pkg_a;
    """

    top_vhd = """
    library ieee;
    use ieee.std_logic_1164.all;
    use work.pkg_b.all;

    entity test_top is
        port (
            wide_bus : out std_logic_vector(C_TOTAL_W-1 downto 0);
            b_data   : out bundle_b_t
        );
    end entity test_top;
    """

    # Pass files with pkg_b before pkg_a
    files = [
        ("top.vhd", top_vhd),
        ("pkg_b.vhd", pkg_b),
        ("pkg_a.vhd", pkg_a),
    ]
    units = parse_vhdl_multi(files)
    assert "test_top" in units
    sig_map = {s.name: s for s in units["test_top"]}

    # C_TOTAL_W = 16 * 2 = 32
    assert sig_map["wide_bus"].type.computed_width() == 32
    # header_a_t = 8 + 4 = 12 bits; bundle_b_t = 2 * 12 = 24 bits
    assert sig_map["b_data"].type.computed_width() == 24


def test_package_subtypes():
    """Verify subtype definitions in packages resolve to correct widths."""
    pkg_vhd = """
    library ieee;
    use ieee.std_logic_1164.all;

    package subtype_pkg is
        subtype byte_t is std_logic_vector(7 downto 0);
        subtype nibble_int_t is integer range 0 to 15;
    end package subtype_pkg;
    """

    top_vhd = """
    library ieee;
    use ieee.std_logic_1164.all;
    use work.subtype_pkg.all;

    entity top_sub is
        port (
            b_sig : in byte_t;
            n_sig : in nibble_int_t
        );
    end entity top_sub;
    """

    files = [("pkg.vhd", pkg_vhd), ("top.vhd", top_vhd)]
    units = parse_vhdl_multi(files)
    sig_map = {s.name: s for s in units["top_sub"]}

    assert sig_map["b_sig"].type.computed_width() == 8
    assert sig_map["n_sig"].type.computed_width() == 4


def test_package_qualified_identifiers():
    """Verify package-qualified identifiers like work.pkg_name.type_name."""
    pkg_vhd = """
    library ieee;
    use ieee.std_logic_1164.all;

    package my_lib_pkg is
        type bus_t is array (0 to 3) of std_logic_vector(15 downto 0);
    end package my_lib_pkg;
    """

    top_vhd = """
    library ieee;
    use ieee.std_logic_1164.all;

    entity top_qual is
        port (
            q_bus : in work.my_lib_pkg.bus_t
        );
    end entity top_qual;
    """

    files = [("top.vhd", top_vhd), ("pkg.vhd", pkg_vhd)]
    units = parse_vhdl_multi(files)
    sig_map = {s.name: s for s in units["top_qual"]}

    assert sig_map["q_bus"].type.computed_width() == 64
