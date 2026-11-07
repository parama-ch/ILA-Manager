module sample_fifo #(
    parameter DATA_WIDTH = 32,
    parameter DEPTH = 16
) (
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  wr_en,
    input  wire [DATA_WIDTH-1:0] wr_data,
    input  wire                  rd_en,
    output reg  [DATA_WIDTH-1:0] rd_data,
    output wire                  full,
    output wire                  empty,
    output reg  [4:0]            count
);

    reg [DATA_WIDTH-1:0] memory [0:DEPTH-1];
    reg [3:0] wr_ptr;
    reg [3:0] rd_ptr;
    wire [7:0] debug_status;

    assign full  = (count == DEPTH);
    assign empty = (count == 0);
    assign debug_status = {2'b00, full, empty, count[3:0]};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= 0;
            rd_ptr <= 0;
            count  <= 0;
            rd_data <= 0;
        end else begin
            if (wr_en && !full) begin
                memory[wr_ptr] <= wr_data;
                wr_ptr <= wr_ptr + 1;
            end
            if (rd_en && !empty) begin
                rd_data <= memory[rd_ptr];
                rd_ptr <= rd_ptr + 1;
            end
            case ({wr_en && !full, rd_en && !empty})
                2'b10: count <= count + 1;
                2'b01: count <= count - 1;
                default: count <= count;
            endcase
        end
    end

endmodule
