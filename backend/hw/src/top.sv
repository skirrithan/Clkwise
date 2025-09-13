module top(
  input  logic         clk,
  input  logic         rst_n,
  input  logic [31:0]  a, b, c, d, e,
  output logic [63:0]  y
);

  // Use ALL inputs so nothing gets optimized away
  // This should easily meet 4ns timing
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) 
      y <= '0;
    else        
      y <= a + b + c + d + e;  // Simple addition using all inputs
  end

endmodule