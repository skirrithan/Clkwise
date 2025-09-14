//hello
module top(
  input  logic         clk,
  input  logic         rst_n,
  input  logic [31:0]  a, b, c, d, e, //32 bit
  output logic [63:0]  y //64 bit
);

// -----------------------------------------------------------------------------
// Pipeline registers to meet timing (added stages)
// -----------------------------------------------------------------------------
logic [63:0] mul1_reg, mul2_reg;   // stage 1
logic [63:0] mul3_reg;            // stage 2
logic [63:0] sum1_reg;            // stage 3
logic [63:0] sum2_reg;            // stage 4
logic [63:0] final_result_reg;   // stage 5

// Stage 1: first level multiplications
always_ff @(posedge clk or negedge rst_n) begin
  if (!rst_n) begin
    mul1_reg <= '0;
    mul2_reg <= '0;
  end else begin
    mul1_reg <= a * b;   // 32x32 multiplier
    mul2_reg <= c * d;   // 32x32 multiplier
  end
end

// Stage 2: second level multiplication (uses lower half of mul1)
always_ff @(posedge clk or negedge rst_n) begin
  if (!rst_n) begin
    mul3_reg <= '0;
  end else begin
    mul3_reg <= mul1_reg[31:0] * e; // 32x32 multiplier
  end
end

// Stage 3: first addition
always_ff @(posedge clk or negedge rst_n) begin
  if (!rst_n) begin
    sum1_reg <= '0;
  end else begin
    sum1_reg <= mul1_reg + mul2_reg;
  end
end

// Stage 4: second addition
always_ff @(posedge clk or negedge rst_n) begin
  if (!rst_n) begin
    sum2_reg <= '0;
  end else begin
    sum2_reg <= sum1_reg + mul3_reg;
  end
end

// Stage 5: conditional final computation
always_ff @(posedge clk or negedge rst_n) begin
  if (!rst_n) begin
    final_result_reg <= '0;
  end else begin
    if (|a) // if a != 0
      final_result_reg <= sum2_reg + sum1_reg;
    else
      final_result_reg <= sum2_reg - mul2_reg;
  end
end

// Output register (placed in IOB for timing)
(* IOB="TRUE" *)
always_ff @(posedge clk or negedge rst_n) begin
  if (!rst_n) begin
    y <= '0;
  end else begin
    y <= final_result_reg;
  end
end

endmodule