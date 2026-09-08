module pipe_stage #(parameter W = 8) (
    input logic clk, rst_n,
    input logic [W-1:0] din,
    output logic [W-1:0] dout
);
    always_ff @(posedge clk or negedge rst_n)
        if (!rst_n) dout <= '0;
        else dout <= din;
endmodule

module pipeline #(parameter W = 8, parameter PIPELINED = 1) (
    input logic clk, rst_n,
    input logic [W-1:0] din,
    output wire [W-1:0] dout
);
    generate
        if (PIPELINED) begin: registered_path
            wire [W-1:0] mid;
            pipe_stage #(.W(W)) first (.clk(clk), .rst_n(rst_n), .din(din), .dout(mid));
            pipe_stage #(.W(W)) second (.clk(clk), .rst_n(rst_n), .din(mid), .dout(dout));
        end else begin: bypass_path
            assign dout = din;
        end
    endgenerate
endmodule
