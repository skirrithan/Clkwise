#!/usr/bin/env python3
"""
code_comparison_demo.py
Demonstrates how the parser currently compares old vs new code
"""

import difflib
import json
import sys
from pathlib import Path

def show_current_comparison_method():
    """Show how the parser currently generates code diffs"""
    
    print("🔍 CURRENT CODE COMPARISON METHOD")
    print("=" * 60)
    
    # This is exactly how the parser currently works (from _extract_code_changes)
    
    # 1. HARDCODED ORIGINAL CODE
    print("\n1️⃣ ORIGINAL CODE (Hardcoded):")
    print("-" * 40)
    original_code = """module top(
  input  logic         clk,
  input  logic         rst_n,
  input  logic [31:0]  a, b, c, d, e, //32 bit
  output logic [63:0]  y //64 bit
);

  logic [63:0] mul1 = a * b; //32 bit x 32 bit
  logic [63:0] mul2 = c * d; //32 bit x 32 bit
  logic [63:0] sum  = mul1 + mul2 + e;  //64 bit + 64 bit + 32 bit

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) y <= '0;
    else        y <= sum;
  end
endmodule"""
    
    print(original_code)
    
    # 2. NEW CODE FROM ARTIFACTS
    print("\n2️⃣ NEW CODE (From Cerebras Artifacts):")
    print("-" * 40)
    
    # Load the actual new code from cerebras_out1.json
    cerebras_file = "/Users/raiya/Clkwise-2/cerebras_out1.json"
    with open(cerebras_file, 'r') as f:
        data = json.load(f)
    
    new_code = data.get("result", {}).get("artifacts", {}).get("top_sv", {}).get("content", "")
    print(new_code[:500] + "..." if len(new_code) > 500 else new_code)
    
    # 3. DIFF GENERATION PROCESS
    print("\n3️⃣ DIFF GENERATION PROCESS:")
    print("-" * 40)
    
    original_lines = original_code.splitlines(keepends=True)
    new_lines = new_code.splitlines(keepends=True)
    
    print(f"Original lines: {len(original_lines)}")
    print(f"New lines: {len(new_lines)}")
    print(f"Lines added: {len(new_lines) - len(original_lines)}")
    
    # 4. UNIFIED DIFF OUTPUT
    print("\n4️⃣ UNIFIED DIFF OUTPUT:")
    print("-" * 40)
    
    diff = difflib.unified_diff(
        original_lines, 
        new_lines,
        fromfile="a/top.sv",
        tofile="b/top.sv",
        lineterm=""
    )
    
    diff_text = ''.join(diff)
    print(diff_text[:800] + "..." if len(diff_text) > 800 else diff_text)
    
    # 5. LIMITATIONS
    print("\n❗ CURRENT LIMITATIONS:")
    print("-" * 40)
    print("• Hardcoded original code - only works for specific test case")
    print("• Cannot handle different input files or modules")
    print("• Original code is reconstructed, not from actual source")
    print("• No support for multiple files or dynamic module names")
    print("• Limited to 'top.sv' artifact only")
    
    # 6. IMPROVEMENT SUGGESTIONS
    print("\n💡 SUGGESTED IMPROVEMENTS:")
    print("-" * 40) 
    print("• Extract original code from input files or git history")
    print("• Support dynamic module names and file paths")
    print("• Handle multiple file changes")
    print("• Use more sophisticated diff algorithms")
    print("• Add side-by-side diff view option")
    print("• Include context lines for better readability")

if __name__ == "__main__":
    show_current_comparison_method()