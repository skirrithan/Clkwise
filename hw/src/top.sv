module top(
  input  logic         clk,
  input  logic         rst_n,
  input  logic [31:0]  a, b, c, d, e,
  output logic [63:0]  y
);
  // Intentionally long combinational path: two multiplies + add chain
  logic [63:0] mul1 = a * b;
  logic [63:0] mul2 = c * d;
  logic [63:0] sum  = mul1 + mul2 + e;

  // Single-stage register => critical path is the whole chain
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) y <= '0;
    else        y <= sum;
  end
endmodule
