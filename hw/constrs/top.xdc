create_clock -name sys_clk -period 2.0 [get_ports clk] ; # 500 MHz -> will fail
set_input_delay  -clock [get_clocks sys_clk] 0.2 [get_ports {a b c d e}]
set_output_delay -clock [get_clocks sys_clk] 0.2 [get_ports {y}]
