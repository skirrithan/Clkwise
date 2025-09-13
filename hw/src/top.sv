module top(
  input  logic         clk,
  input  logic         rst_n,
  input  logic [31:0]  a, b, c, d, e, //32 bit
  output logic [63:0]  y //64 bit
);

  logic [63:0] mul1 = a * b; //32 bit x 32 bit
  logic [63:0] mul2 = c * d; //32 bit x 32 bit
  logic [63:0] sum  = mul1 + mul2 + e;  //64 bit + 64 bit + 32 bit

  // Single-stage register => critical path is the whole chain
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) y <= '0;
      else        y <= sum;
  end
endmodule
