"""Adversarial stress-test suite for Two-Pass Multi-File VHDL Parser and Type Registry.

Probing:
1. Multi-package dependencies: Package C uses Package B which uses Package A, passed in reverse order [pkg_c, pkg_a, pkg_b].
2. Complex 2D arrays with expressions in ranges (array (C_ROWS-1 downto 0, 0 to C_COLS-1) of std_logic_vector(C_WIDTH-1 downto 0)).
3. Records containing arrays of custom records (in package vs in architecture).
4. Unconstrained array instantiation in signals (signal mem : word_arr_t(0 to 15);), ports, and slicing.
5. Scoped use work.<pkg>.all; vs conflicting type names in multiple packages (separate files vs same file vs unimported).
6. Empty VHDL files, comments only, malformed packages.
"""

from ila_manager.models import (
    FieldStep,
    IndexStep,
    ProbeMapping,
    RangeStep,
)
from ila_manager.parser.vhdl import parse_vhdl, parse_vhdl_multi
from ila_manager.selection import resolve_selection


# ==============================================================================
# 1. Multi-package dependencies in reverse order: C -> B -> A
# ==============================================================================
def test_adversarial_3tier_package_reverse_order():
    """Package C uses Package B which uses Package A, passed in reverse order [C, A, B]."""
    pkg_c = """
    library ieee;
    use ieee.std_logic_1164.all;
    use work.pkg_b.all;

    package pkg_c is
        constant C_C_BLOCKS : integer := 2;
        type block_t is array (0 to C_C_BLOCKS - 1) of word_t;
        type packet_t is record
            header  : b_meta_t;
            payload : block_t;
        end record;
    end package pkg_c;
    """

    pkg_b = """
    library ieee;
    use ieee.std_logic_1164.all;
    use work.pkg_a.all;

    package pkg_b is
        constant C_B_COUNT : integer := 4;
        type word_t is array (0 to C_B_COUNT - 1) of byte_t;
        type b_meta_t is record
            tag   : byte_t;
            valid : std_logic;
        end record;
    end package pkg_b;
    """

    pkg_a = """
    library ieee;
    use ieee.std_logic_1164.all;

    package pkg_a is
        constant C_A_WIDTH : integer := 8;
        subtype byte_t is std_logic_vector(C_A_WIDTH - 1 downto 0);
    end package pkg_a;
    """

    top_vhd = """
    library ieee;
    use ieee.std_logic_1164.all;
    use work.pkg_c.all;

    entity top_network is
        port (
            clk : in std_logic
        );
    end entity top_network;

    architecture rtl of top_network is
        signal sig_block  : block_t;
        signal sig_packet : packet_t;
    begin
    end architecture rtl;
    """

    # Passed in reverse/shuffled order: pkg_c, top, pkg_a, pkg_b
    sources = [
        ("pkg_c.vhd", pkg_c),
        ("top_network.vhd", top_vhd),
        ("pkg_a.vhd", pkg_a),
        ("pkg_b.vhd", pkg_b),
    ]

    units, pkg_names = parse_vhdl_multi(sources)

    assert "pkg_a" in pkg_names
    assert "pkg_b" in pkg_names
    assert "pkg_c" in pkg_names
    assert "top_network.rtl" in units

    signals = {s.name: s for s in units["top_network.rtl"]}
    assert "sig_block" in signals
    assert "sig_packet" in signals

    # byte_t = 8 bits
    # word_t = 4 * 8 = 32 bits
    # block_t = 2 * 32 = 64 bits
    assert signals["sig_block"].is_unknown is False
    assert signals["sig_block"].type.computed_width() == 64

    # b_meta_t = 8 (tag) + 1 (valid) = 9 bits
    # packet_t = 9 + 64 = 73 bits
    assert signals["sig_packet"].is_unknown is False
    assert signals["sig_packet"].type.computed_width() == 73


# ==============================================================================
# 2. Complex 2D arrays with expressions in ranges
# ==============================================================================
def test_adversarial_complex_2d_arrays_with_expressions():
    """Verify 2D arrays with constant arithmetic expressions in bounds and slicing."""
    pkg_vhd = """
    library ieee;
    use ieee.std_logic_1164.all;

    package matrix_pkg is
        constant C_ROWS  : integer := 3;
        constant C_COLS  : integer := 5;
        constant C_WIDTH : integer := 12;

        -- 2D array of vectors: 3 * 5 * 12 = 180 bits
        type matrix_2d_t is array (C_ROWS - 1 downto 0, 0 to C_COLS - 1)
            of std_logic_vector(C_WIDTH - 1 downto 0);

        -- 2D array of std_logic bits: (3*2) * (5+1) = 6 * 6 * 1 = 36 bits
        type bit_grid_t is array ((C_ROWS * 2) - 1 downto 0, 0 to C_COLS)
            of std_logic;

        -- 2D array with parentheses in range expressions: 3 * 5 * 6 = 90 bits
        type paren_grid_t is array ((C_ROWS - 1) downto 0, 0 to (C_COLS - 1))
            of std_logic_vector((C_WIDTH / 2) - 1 downto 0);
    end package matrix_pkg;
    """

    top_vhd = """
    library ieee;
    use ieee.std_logic_1164.all;
    use work.matrix_pkg.all;

    entity top_matrix is
        port (clk : in std_logic);
    end entity top_matrix;

    architecture rtl of top_matrix is
        signal mat        : matrix_2d_t;
        signal grid       : bit_grid_t;
        signal paren_mat  : paren_grid_t;
    begin
    end architecture rtl;
    """

    units, _ = parse_vhdl_multi([("top.vhd", top_vhd), ("matrix_pkg.vhd", pkg_vhd)])
    assert "top_matrix.rtl" in units
    sig_map = {s.name: s for s in units["top_matrix.rtl"]}

    # mat: 3 rows * 5 cols * 12 bits = 180 bits
    assert sig_map["mat"].is_unknown is False
    assert sig_map["mat"].type.kind == "array"
    assert sig_map["mat"].type.computed_width() == 180

    # grid: 6 rows * 6 cols * 1 bit = 36 bits
    assert sig_map["grid"].is_unknown is False
    assert sig_map["grid"].type.kind == "array"
    assert sig_map["grid"].type.computed_width() == 36

    # paren_mat: 3 rows * 5 cols * 6 bits = 90 bits
    assert sig_map["paren_mat"].is_unknown is False
    assert sig_map["paren_mat"].type.kind == "array"
    assert sig_map["paren_mat"].type.computed_width() == 90

    # ProbeMapping and Selection slicing on 2D array:
    # 1. Slice row: mat(2) -> 5 cols * 12 bits = 60 bits
    m_row = ProbeMapping(signal="mat", path=[IndexStep(index=2)])
    r_row = resolve_selection(m_row, sig_map["mat"])
    assert r_row.vhdl_expr == "mat(2)"
    assert r_row.width == 60

    # 2. Slice element: mat(2)(3) -> 12 bits
    m_elem = ProbeMapping(signal="mat", path=[IndexStep(index=2), IndexStep(index=3)])
    r_elem = resolve_selection(m_elem, sig_map["mat"])
    assert r_elem.vhdl_expr == "mat(2)(3)"
    assert r_elem.width == 12

    # 3. Slice bit range: mat(2)(3)(7 downto 0) -> 8 bits
    m_bits = ProbeMapping(
        signal="mat",
        path=[IndexStep(index=2), IndexStep(index=3), RangeStep(left=7, right=0, ascending=False)],
    )
    r_bits = resolve_selection(m_bits, sig_map["mat"])
    assert r_bits.vhdl_expr == "mat(2)(3)(7 downto 0)"
    assert r_bits.width == 8


# ==============================================================================
# 3. Records containing arrays of custom records
# ==============================================================================
def test_adversarial_records_containing_arrays_in_package():
    """Verify deep recursive type resolution and selection path traversal when defined in package."""
    pkg_vhd = """
    library ieee;
    use ieee.std_logic_1164.all;

    package tree_pkg is
        type leaf_record_t is record
            id    : std_logic_vector(3 downto 0);  -- 4 bits
            valid : std_logic;                     -- 1 bit
        end record;                                -- 5 bits total

        type leaf_array_t is array (0 to 3) of leaf_record_t;  -- 4 * 5 = 20 bits

        type mid_record_t is record
            leaves : leaf_array_t;                 -- 20 bits
            seq    : std_logic_vector(7 downto 0); -- 8 bits
        end record;                                -- 28 bits total

        type mid_array_t is array (1 downto 0) of mid_record_t; -- 2 * 28 = 56 bits

        type root_record_t is record
            branch : mid_array_t;                   -- 56 bits
            crc    : std_logic_vector(15 downto 0); -- 16 bits
        end record;                                 -- 72 bits total
    end package tree_pkg;
    """

    top_vhd = """
    library ieee;
    use ieee.std_logic_1164.all;
    use work.tree_pkg.all;

    entity top_tree is
        port (clk : in std_logic);
    end entity top_tree;

    architecture rtl of top_tree is
        signal tree_sig : root_record_t;
    begin
    end architecture rtl;
    """

    units, _ = parse_vhdl_multi([("tree_pkg.vhd", pkg_vhd), ("top.vhd", top_vhd)])
    sig = {s.name: s for s in units["top_tree.rtl"]}["tree_sig"]

    assert sig.is_unknown is False
    assert sig.type.kind == "record"
    assert sig.type.computed_width() == 72

    # Verify drill-down selection path: tree_sig.branch(0).leaves(2).id
    mapping = ProbeMapping(
        signal="tree_sig",
        path=[
            FieldStep(field="branch"),
            IndexStep(index=0),
            FieldStep(field="leaves"),
            IndexStep(index=2),
            FieldStep(field="id"),
        ],
    )
    resolved = resolve_selection(mapping, sig)
    assert resolved.vhdl_expr == "tree_sig.branch(0).leaves(2).id"
    assert resolved.width == 4
    assert resolved.is_single_bit is False

    # Verify drill-down single bit leaf: tree_sig.branch(1).leaves(0).valid
    mapping_bit = ProbeMapping(
        signal="tree_sig",
        path=[
            FieldStep(field="branch"),
            IndexStep(index=1),
            FieldStep(field="leaves"),
            IndexStep(index=0),
            FieldStep(field="valid"),
        ],
    )
    resolved_bit = resolve_selection(mapping_bit, sig)
    assert resolved_bit.vhdl_expr == "tree_sig.branch(1).leaves(0).valid"
    assert resolved_bit.width == 1
    assert resolved_bit.is_single_bit is True


def test_adversarial_records_containing_arrays_in_architecture():
    """Verify records using custom arrays defined in the same architecture declarative region resolve correctly."""
    code = """
    library ieee;
    use ieee.std_logic_1164.all;

    entity top_local is
        port (clk : in std_logic);
    end entity top_local;

    architecture rtl of top_local is
        type leaf_t is record
            val : std_logic_vector(7 downto 0);
        end record;

        type leaf_arr_t is array (0 to 3) of leaf_t;

        type root_rec_t is record
            items : leaf_arr_t;
        end record;

        signal root_sig : root_rec_t;
    begin
    end architecture rtl;
    """
    units = parse_vhdl(code)
    sig = {s.name: s for s in units["top_local.rtl"]}["root_sig"]

    # Expected standard VHDL behavior: root_sig should be resolved to 32 bits (4 items * 8 bits)
    # Actual defective behavior: root_sig.is_unknown is True and items is unknown
    assert sig.is_unknown is False
    assert sig.type.computed_width() == 32


# ==============================================================================
# 4. Unconstrained array instantiation in signals and ports
# ==============================================================================
def test_adversarial_unconstrained_array_instantiation():
    """Verify signal instantiation of unconstrained array types: word_arr_t(0 to 15)."""
    pkg_vhd = """
    library ieee;
    use ieee.std_logic_1164.all;

    package unconstrained_pkg is
        constant C_BUF_DEPTH : integer := 4;
        type word_arr_t is array (natural range <>) of std_logic_vector(31 downto 0);
        type byte_arr_t is array (integer range <>) of std_logic_vector(7 downto 0);
    end package unconstrained_pkg;
    """

    top_vhd = """
    library ieee;
    use ieee.std_logic_1164.all;
    use work.unconstrained_pkg.all;

    entity top_unconstrained is
        port (
            clk  : in std_logic;
            port_mem : in word_arr_t(0 to 3)
        );
    end entity top_unconstrained;

    architecture rtl of top_unconstrained is
        signal mem        : word_arr_t(0 to 15);
        signal mem_down   : word_arr_t(7 downto 0);
        signal byte_buf   : byte_arr_t(0 to C_BUF_DEPTH - 1);
        signal unconst    : word_arr_t;
    begin
    end architecture rtl;
    """

    units, _ = parse_vhdl_multi([("pkg.vhd", pkg_vhd), ("top.vhd", top_vhd)])
    sig_map = {s.name: s for s in units["top_unconstrained.rtl"]}

    # port_mem: 4 words of 32 bits = 128 bits
    assert sig_map["port_mem"].is_unknown is False
    assert sig_map["port_mem"].type.computed_width() == 128

    # mem: 16 words of 32 bits = 512 bits
    assert sig_map["mem"].is_unknown is False
    assert sig_map["mem"].type.kind == "array"
    assert sig_map["mem"].type.is_unconstrained is False
    assert sig_map["mem"].type.left == 0
    assert sig_map["mem"].type.right == 15
    assert sig_map["mem"].type.ascending is True
    assert sig_map["mem"].type.computed_width() == 512

    # mem_down: 8 words of 32 bits = 256 bits
    assert sig_map["mem_down"].is_unknown is False
    assert sig_map["mem_down"].type.kind == "array"
    assert sig_map["mem_down"].type.is_unconstrained is False
    assert sig_map["mem_down"].type.left == 7
    assert sig_map["mem_down"].type.right == 0
    assert sig_map["mem_down"].type.ascending is False
    assert sig_map["mem_down"].type.computed_width() == 256

    # byte_buf with evaluated constant: 4 bytes of 8 bits = 32 bits
    assert sig_map["byte_buf"].is_unknown is False
    assert sig_map["byte_buf"].type.computed_width() == 32

    # unconst: uninstantiated unconstrained array
    assert sig_map["unconst"].type.is_unconstrained is True
    assert sig_map["unconst"].type.computed_width() is None
    assert sig_map["unconst"].is_unknown is False  # valid unconstrained declaration

    # Slicing instantiated unconstrained array
    m_slice = ProbeMapping(signal="mem", path=[IndexStep(index=2), RangeStep(left=15, right=0, ascending=False)])
    r_slice = resolve_selection(m_slice, sig_map["mem"])
    assert r_slice.vhdl_expr == "mem(2)(15 downto 0)"
    assert r_slice.width == 16


# ==============================================================================
# 5. Scoped use work.<pkg>.all; vs conflicting type names in multiple packages
# ==============================================================================
def test_adversarial_scoped_use_separate_files():
    """Verify package scoping isolates conflicting type names when units are in separate files."""
    pkg_net = """
    package pkg_net is
        type header_t is record
            ip_addr : std_logic_vector(31 downto 0);
        end record;
    end package pkg_net;
    """

    pkg_audio = """
    package pkg_audio is
        type header_t is record
            sample_rate : std_logic_vector(15 downto 0);
            channels    : std_logic_vector(3 downto 0);
        end record;
    end package pkg_audio;
    """

    top_net = """
    library ieee;
    use ieee.std_logic_1164.all;
    use work.pkg_net.all;

    entity net_node is port (clk : in std_logic); end entity net_node;
    architecture rtl of net_node is
        signal hdr : header_t;
    begin
    end architecture rtl;
    """

    top_audio = """
    library ieee;
    use ieee.std_logic_1164.all;
    use work.pkg_audio.all;

    entity audio_node is port (clk : in std_logic); end entity audio_node;
    architecture rtl of audio_node is
        signal hdr : header_t;
    begin
    end architecture rtl;
    """

    top_dual = """
    library ieee;
    use ieee.std_logic_1164.all;

    entity dual_node is port (clk : in std_logic); end entity dual_node;
    architecture rtl of dual_node is
        signal net_hdr   : work.pkg_net.header_t;
        signal audio_hdr : work.pkg_audio.header_t;
    begin
    end architecture rtl;
    """

    sources = [
        ("pkg_net.vhd", pkg_net),
        ("pkg_audio.vhd", pkg_audio),
        ("top_net.vhd", top_net),
        ("top_audio.vhd", top_audio),
        ("top_dual.vhd", top_dual),
    ]

    units, _ = parse_vhdl_multi(sources)

    # Scoped imports in separate files resolve correctly
    net_hdr = {s.name: s for s in units["net_node.rtl"]}["hdr"]
    assert net_hdr.type.package == "pkg_net"
    assert net_hdr.type.computed_width() == 32

    audio_hdr = {s.name: s for s in units["audio_node.rtl"]}["hdr"]
    assert audio_hdr.type.package == "pkg_audio"
    assert audio_hdr.type.computed_width() == 20

    # Package-qualified references resolve correctly
    dual_sigs = {s.name: s for s in units["dual_node.rtl"]}
    assert dual_sigs["net_hdr"].type.computed_width() == 32
    assert dual_sigs["audio_hdr"].type.computed_width() == 20


def test_adversarial_scoped_use_same_file_pollution():
    """Verify sibling architectures in the same file do not pollute each other's use scopes."""
    pkg_net = """
    package pkg_net is
        type header_t is record
            ip_addr : std_logic_vector(31 downto 0);
        end record;
    end package pkg_net;
    """

    pkg_audio = """
    package pkg_audio is
        type header_t is record
            sample_rate : std_logic_vector(15 downto 0);
            channels    : std_logic_vector(3 downto 0);
        end record;
    end package pkg_audio;
    """

    # Both architectures in ONE file
    single_file = """
    entity net_node is port (clk : in std_logic); end entity net_node;
    architecture rtl of net_node is
        use work.pkg_net.all;
        signal hdr : header_t;
    begin
    end architecture rtl;

    entity audio_node is port (clk : in std_logic); end entity audio_node;
    architecture rtl of audio_node is
        use work.pkg_audio.all;
        signal hdr : header_t;
    begin
    end architecture rtl;
    """

    units, _ = parse_vhdl_multi([
        ("pkg_net.vhd", pkg_net),
        ("pkg_audio.vhd", pkg_audio),
        ("single_file.vhd", single_file),
    ])

    net_hdr = {s.name: s for s in units["net_node.rtl"]}["hdr"]
    # Standard VHDL behavior: net_node imports only pkg_net, so hdr must be 32 bits
    # Actual defective behavior: file_uses leaks pkg_audio into net_node, overwriting hdr to 20 bits
    assert net_hdr.type.package == "pkg_net"
    assert net_hdr.type.computed_width() == 32


def test_adversarial_unimported_conflicting_types_leakage():
    """Verify entity that does NOT import any package does not resolve ambiguous type names."""
    pkg_net = """
    package pkg_net is
        type header_t is record ip_addr : std_logic_vector(31 downto 0); end record;
    end package pkg_net;
    """

    pkg_audio = """
    package pkg_audio is
        type header_t is record sample_rate : std_logic_vector(15 downto 0); end record;
    end package pkg_audio;
    """

    unrelated_vhd = """
    entity unrelated_node is port (clk : in std_logic); end entity unrelated_node;
    architecture rtl of unrelated_node is
        signal hdr : header_t;
    begin
    end architecture rtl;
    """

    units, _ = parse_vhdl_multi([
        ("pkg_net.vhd", pkg_net),
        ("pkg_audio.vhd", pkg_audio),
        ("unrelated.vhd", unrelated_vhd),
    ])

    hdr = {s.name: s for s in units["unrelated_node.rtl"]}["hdr"]
    # Standard VHDL behavior: header_t was never imported, and multiple packages declare it.
    # It must be treated as unknown/unresolved so the UI can warn the user.
    # Actual defective behavior: silently resolves to pkg_audio (width 16).
    assert hdr.is_unknown is True


# ==============================================================================
# 6. Empty VHDL files, comments only, malformed packages
# ==============================================================================
def test_adversarial_empty_comments_and_malformed_vhdl():
    """Verify robustness against empty, comment-only, and malformed VHDL sources."""
    sources = [
        ("empty.vhd", ""),
        ("whitespace.vhd", "   \n\t   \n  \r\n"),
        ("comments_only.vhd", "-- This is a pure comment\n-- Line 2\n   -- Line 3\n"),
        ("malformed_pkg1.vhd", "package is end package;"),
        ("malformed_pkg2.vhd", "package truncated_pkg is constant C : integer := 42;"),  # unclosed
        ("malformed_pkg3.vhd", "package bad_syntax is type broken_t is array (0 to ) of ; end package;"),
        ("malformed_entity.vhd", "entity broken_ent is port (clk : in std_logic); architecture of broken is begin"),
    ]

    # Should not crash, raise unhandled exceptions, or loop infinitely
    units, pkgs = parse_vhdl_multi(sources)
    assert isinstance(units, dict)
    assert isinstance(pkgs, list)

    # Valid entity alongside malformed sources should still parse cleanly
    valid_source = """
    library ieee;
    use ieee.std_logic_1164.all;

    entity valid_top is
        port (
            data_in  : in  std_logic_vector(7 downto 0);
            data_out : out std_logic_vector(7 downto 0)
        );
    end entity valid_top;

    architecture rtl of valid_top is
        signal internal_reg : std_logic_vector(7 downto 0);
    begin
    end architecture rtl;
    """
    mixed_sources = sources + [("valid_top.vhd", valid_source)]
    units_mixed, _ = parse_vhdl_multi(mixed_sources)

    assert "valid_top.rtl" in units_mixed
    sig_map = {s.name: s for s in units_mixed["valid_top.rtl"]}
    assert "data_in" in sig_map
    assert "data_out" in sig_map
    assert "internal_reg" in sig_map
    assert sig_map["internal_reg"].type.computed_width() == 8
