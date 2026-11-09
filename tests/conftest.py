"""Shared pytest fixtures for ILA Manager tests."""

from pathlib import Path
from typing import Dict

import pytest


@pytest.fixture
def vhdl_pkg_types_content() -> str:
    """Standalone VHDL package declaring constants, arrays, records, and enums."""
    return """
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

package pkg_types is
    constant C_DATA_W     : integer := 32;
    constant C_ADDR_W     : integer := 10;
    constant C_CHANNELS   : integer := 4;
    constant C_TOTAL_BITS : integer := C_DATA_W * C_CHANNELS;

    -- 1D custom array of vectors
    type channel_data_t is array (0 to C_CHANNELS-1) of std_logic_vector(C_DATA_W-1 downto 0);

    -- 2D custom array
    type matrix_2d_t is array (0 to 1, 0 to 3) of std_logic_vector(7 downto 0);

    -- Custom record
    type axis_stream_t is record
        tdata  : std_logic_vector(C_DATA_W-1 downto 0);
        tstrb  : std_logic_vector((C_DATA_W/8)-1 downto 0);
        tvalid : std_logic;
        tlast  : std_logic;
        tid    : unsigned(3 downto 0);
    end record;

    -- Custom enum
    type fsm_state_t is (ST_IDLE, ST_HEADER, ST_PAYLOAD, ST_CRC, ST_RESP);

    -- Array of records (nested custom types)
    type stream_bundle_t is array (0 to 1) of axis_stream_t;
end package pkg_types;
"""


@pytest.fixture
def vhdl_top_entity_content() -> str:
    """Top-level entity importing pkg_types and declaring signals of custom types."""
    return """
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.pkg_types.all;

entity top_dsp_core is
    generic (
        G_ENABLE_ILA : boolean := true
    );
    port (
        clk        : in  std_logic;
        rst_n      : in  std_logic;
        axis_rx    : in  axis_stream_t;
        chan_out   : out channel_data_t
    );
end entity top_dsp_core;

architecture rtl of top_dsp_core is
    signal ch_buffer   : channel_data_t;
    signal tx_stream   : axis_stream_t;
    signal curr_state  : fsm_state_t := ST_IDLE;
    signal mem_matrix  : matrix_2d_t;
    signal bundle      : stream_bundle_t;
    signal raw_word    : std_logic_vector(C_DATA_W-1 downto 0);
    signal unknown_sig : mystery_protocol_bus_t;  -- Deliberately unknown type
begin
    -- architecture statements
end architecture rtl;
"""


@pytest.fixture
def multi_file_vhdl_project_dict(
    vhdl_pkg_types_content: str, vhdl_top_entity_content: str
) -> Dict[str, str]:
    """Dictionary mapping filenames to content."""
    return {
        "pkg_types.vhd": vhdl_pkg_types_content,
        "top_dsp_core.vhd": vhdl_top_entity_content,
    }


@pytest.fixture
def multi_file_vhdl_disk_dir(
    tmp_path: Path, multi_file_vhdl_project_dict: Dict[str, str]
) -> Path:
    """Physical directory containing multi-file VHDL project on disk."""
    for filename, content in multi_file_vhdl_project_dict.items():
        (tmp_path / filename).write_text(content, encoding="utf-8")
    return tmp_path
