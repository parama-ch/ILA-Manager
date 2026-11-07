"""Tests for VHDL parser."""

from ila_manager.parser.vhdl import parse_vhdl

VHDL_SAMPLE = """
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

package test_pkg is
    constant C_DATA_W : integer := 16;
    type bus_array_t is array (0 to 3) of std_logic_vector(7 downto 0);
    type header_rec_t is record
        src_id  : std_logic_vector(3 downto 0);
        valid   : std_logic;
        payload : std_logic_vector(15 downto 0);
    end record;
    type fsm_state_t is (IDLE, READ, WRITE, DONE);
end package test_pkg;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.test_pkg.all;

entity my_core is
    generic (
        G_ADDR_W : integer := 8;
        G_PIPE   : integer := 2
    );
    port (
        clk        : in  std_logic;
        rst_n      : in  std_logic;
        data_in    : in  std_logic_vector(C_DATA_W-1 downto 0);
        addr_in    : in  unsigned(G_ADDR_W-1 downto 0);
        data_out   : out std_logic_vector(15 downto 0);
        ready      : out std_logic
    );
end entity my_core;

architecture rtl of my_core is
    constant C_MAX_COUNT : integer := 255;
    signal count_reg     : unsigned(7 downto 0) := (others => '0');
    signal buffers       : bus_array_t;
    signal header        : header_rec_t;
    signal state         : fsm_state_t := IDLE;
    signal int_val       : integer range 0 to 100;
    signal flag_a, flag_b: std_logic;
begin
    -- architecture statements
end architecture rtl;
"""


def test_parse_vhdl_ports_and_signals():
    units = parse_vhdl(VHDL_SAMPLE, filename="test.vhd")
    assert "my_core.rtl" in units
    signals = units["my_core.rtl"]
    sig_map = {s.name: s for s in signals}

    # Verify ports
    assert "clk" in sig_map
    assert sig_map["clk"].kind == "port_in"
    assert sig_map["clk"].type.kind == "bit"
    assert sig_map["clk"].type.computed_width() == 1

    assert "data_in" in sig_map
    assert sig_map["data_in"].type.kind == "vector"
    assert sig_map["data_in"].type.left == 15
    assert sig_map["data_in"].type.right == 0
    assert sig_map["data_in"].type.computed_width() == 16

    assert "addr_in" in sig_map
    assert sig_map["addr_in"].type.kind == "vector"
    assert sig_map["addr_in"].type.left == 7
    assert sig_map["addr_in"].type.right == 0
    assert sig_map["addr_in"].type.computed_width() == 8

    # Verify architecture signals
    assert "count_reg" in sig_map
    assert sig_map["count_reg"].type.computed_width() == 8

    # Verify array type
    assert "buffers" in sig_map
    assert sig_map["buffers"].type.kind == "array"
    assert sig_map["buffers"].type.left == 0
    assert sig_map["buffers"].type.right == 3
    assert sig_map["buffers"].type.element is not None
    assert sig_map["buffers"].type.element.computed_width() == 8
    assert sig_map["buffers"].type.computed_width() == 32  # 4 * 8

    # Verify record type
    assert "header" in sig_map
    assert sig_map["header"].type.kind == "record"
    assert "src_id" in sig_map["header"].type.fields
    assert "valid" in sig_map["header"].type.fields
    assert "payload" in sig_map["header"].type.fields
    assert sig_map["header"].type.fields["src_id"].computed_width() == 4
    assert sig_map["header"].type.fields["valid"].computed_width() == 1
    assert sig_map["header"].type.fields["payload"].computed_width() == 16
    assert sig_map["header"].type.computed_width() == 21  # 4 + 1 + 16

    # Verify enum type
    assert "state" in sig_map
    assert sig_map["state"].type.kind == "enum"
    assert sig_map["state"].type.computed_width() == 2  # ceil(log2(4)) = 2

    # Verify integer range
    assert "int_val" in sig_map
    assert sig_map["int_val"].type.kind == "integer"
    assert sig_map["int_val"].type.computed_width() == 7  # 100 fits in 7 bits (up to 127)

    # Verify multi-name signals
    assert "flag_a" in sig_map
    assert "flag_b" in sig_map
    assert sig_map["flag_a"].type.computed_width() == 1
    assert sig_map["flag_b"].type.computed_width() == 1
