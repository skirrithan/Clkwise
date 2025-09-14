// Top-level module with added pipeline registers to meet timing
module top(
  input  logic         clk,
  input  logic         rst_n,
  input  logic [31:0]  a, b, c, d, e, // 32‑bit operands
  output logic [63:0]  y               // 64‑bit result
);

  // -------------------------------------------------------------------
  // Stage 1: first‑level multiplications (combinational)
  // -------------------------------------------------------------------
  logic [63:0] mul1_comb, mul2_comb;
  assign mul1_comb = a * b; // 32‑bit x 32‑bit
  assign mul2_comb = c * d; // 32‑bit x 32‑bit

  // Pipeline registers after mul1 and mul2
  logic [63:0] mul1_reg, mul2_reg;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      mul1_reg <= '0;
      mul2_reg <= '0;
    end else begin
      mul1_reg <= mul1_comb;
      mul2_reg <= mul2_comb;
    end
  end

  // -------------------------------------------------------------------
  // Stage 2: second multiplication using registered mul1
  // -------------------------------------------------------------------
  logic [63:0] mul3_comb;
  assign mul3_comb = mul1_reg[31:0] * e; // 32‑bit x 32‑bit

  // Register mul3 result
  logic [63:0] mul3_reg;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) mul3_reg <= '0;
    else        mul3_reg <= mul3_comb;
  end

  // -------------------------------------------------------------------
  // Stage 3: first addition (sum1)
  // -------------------------------------------------------------------
  logic [63:0] sum1_comb;
  assign sum1_comb = mul1_reg + mul2_reg;

  // Register sum1 result
  logic [63:0] sum1_reg;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) sum1_reg <= '0;
    else        sum1_reg <= sum1_comb;
  end

  // -------------------------------------------------------------------
  // Stage 4: second addition (sum2)
  // -------------------------------------------------------------------
  logic [63:0] sum2_comb;
  assign sum2_comb = sum1_reg + mul3_reg;

  // Register sum2 result
  logic [63:0] sum2_reg;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) sum2_reg <= '0;
    else        sum2_reg <= sum2_comb;
  end

  // -------------------------------------------------------------------
  // Stage 5: final conditional computation
  // -------------------------------------------------------------------
  logic [63:0] final_comb;
  always_comb begin
    if (|a) // if any bit of a is high
      final_comb = sum2_reg + sum1_reg;
    else
      final_comb = sum2_reg - mul2_reg;
  end

  // Register final result
  logic [63:0] final_reg;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) final_reg <= '0;
    else        final_reg <= final_comb;
  end

  // -------------------------------------------------------------------
  // Output register placed in IOB for best timing
  // -------------------------------------------------------------------
  (* IOB = "TRUE" *) logic [63:0] y_reg;
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) y_reg <= '0;
    else        y_reg <= final_reg;
  end

  assign y = y_reg;

endmodule