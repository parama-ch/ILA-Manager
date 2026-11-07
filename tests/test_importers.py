"""Tests for HDL instance and TCL importers."""

from ila_manager.importers.hdl_instance import import_from_hdl
from ila_manager.importers.tcl import import_from_tcl


def test_import_from_vhdl_instance():
    vhdl_code = """
    u_ila_debug : entity work.ila_0
        port map (
            clk       => sys_clk,
            probe0(0) => rx_valid,
            probe1    => rx_data(15 downto 8),
            probe2    => std_logic_vector(counter)
        );
    """
    ilas = import_from_hdl(vhdl_code, is_vhdl=True)
    assert len(ilas) == 1
    ila = ilas[0]
    assert ila.name == "ila_0"
    assert ila.clock == "sys_clk"
    assert len(ila.probes) == 3

    assert ila.probes[0].mapping.signal == "rx_valid"
    assert ila.probes[1].mapping.signal == "rx_data"
    assert len(ila.probes[1].mapping.path) == 1
    assert ila.probes[1].mapping.path[0].left == 15
    assert ila.probes[1].mapping.path[0].right == 8

    assert ila.probes[2].mapping.signal == "counter"


def test_import_from_verilog_instance():
    v_code = """
    ila_0 u_ila_0 (
        .clk    (clk),
        .probe0 (valid),
        .probe1 (data[7:0])
    );
    """
    ilas = import_from_hdl(v_code, is_vhdl=False)
    assert len(ilas) == 1
    ila = ilas[0]
    assert ila.name == "ila_0"
    assert len(ila.probes) == 2
    assert ila.probes[0].mapping.signal == "valid"
    assert ila.probes[1].mapping.signal == "data"


def test_import_from_tcl():
    tcl_code = """
    create_ip -name ila -vendor xilinx.com -library ip -module_name ila_main
    set_property -dict [list \\
        CONFIG.C_NUM_OF_PROBES {3} \\
        CONFIG.C_INPUT_PIPE_STAGES {4} \\
        CONFIG.C_DATA_DEPTH {4096} \\
        CONFIG.ALL_PROBE_SAME_MU {true} \\
        CONFIG.ALL_PROBE_SAME_MU_CNT {2} \\
        CONFIG.C_PROBE0_WIDTH {1} CONFIG.C_PROBE0_TYPE {0} \\
        CONFIG.C_PROBE1_WIDTH {8} CONFIG.C_PROBE1_TYPE {1} \\
        CONFIG.C_PROBE2_WIDTH {32} CONFIG.C_PROBE2_TYPE {2} \\
    ] [get_ips ila_main]
    """
    ila = import_from_tcl(tcl_code)
    assert ila is not None
    assert ila.name == "ila_main"
    assert ila.pipe_stages == 4
    assert ila.data_depth == 4096
    assert len(ila.probes) == 3
    assert ila.probes[0].width == 1
    assert ila.probes[0].probe_type == "DATA_AND_TRIGGER"
    assert ila.probes[1].width == 8
    assert ila.probes[1].probe_type == "DATA"
    assert ila.probes[2].width == 32
    assert ila.probes[2].probe_type == "TRIGGER"
