"""Tests for Verilog / SystemVerilog parser."""

from ila_manager.parser.verilog import parse_verilog

VERILOG_SAMPLE = """
module fifo_ctrl #(
    parameter DATA_WIDTH = 32,
    parameter DEPTH = 16
) (
    input clk,
    input rst_n,
    input wr_en,
    input [DATA_WIDTH-1:0] wr_data,
    output reg full,
    output reg [3:0] count
);

    localparam ADDR_BITS = 4;

    reg [DATA_WIDTH-1:0] mem [0:DEPTH-1];
    wire [ADDR_BITS-1:0] wr_ptr;
    reg [ADDR_BITS-1:0] rd_ptr;
    logic status_flag;
    logic [7:0] debug_bus;

    // module logic
endmodule
"""


def test_parse_verilog():
    modules = parse_verilog(VERILOG_SAMPLE, filename="fifo_ctrl.v")
    assert "fifo_ctrl" in modules
    signals = modules["fifo_ctrl"]
    sig_map = {s.name: s for s in signals}

    # Ports
    assert "clk" in sig_map
    assert sig_map["clk"].kind == "port_input"
    assert sig_map["clk"].type.computed_width() == 1

    assert "wr_data" in sig_map
    assert sig_map["wr_data"].type.kind == "vector"
    assert sig_map["wr_data"].type.left == 31
    assert sig_map["wr_data"].type.right == 0
    assert sig_map["wr_data"].type.computed_width() == 32

    assert "count" in sig_map
    assert sig_map["count"].kind == "port_output"
    assert sig_map["count"].type.computed_width() == 4

    # Internal nets
    assert "wr_ptr" in sig_map
    assert sig_map["wr_ptr"].type.computed_width() == 4

    assert "status_flag" in sig_map
    assert sig_map["status_flag"].type.computed_width() == 1

    assert "debug_bus" in sig_map
    assert sig_map["debug_bus"].type.computed_width() == 8

    # Unpacked memory array
    assert "mem" in sig_map
    assert sig_map["mem"].type.kind == "array"
    assert sig_map["mem"].type.left == 0
    assert sig_map["mem"].type.right == 15
    assert sig_map["mem"].type.element.computed_width() == 32
    assert sig_map["mem"].type.computed_width() == 16 * 32
