create_clock -name sys_clk -period 4.0 [get_ports clk] ; # 1000 MHz -> will fail
set_input_delay  -clock [get_clocks sys_clk] 0.5 [get_ports [get_ports {a[*] b[*] c[*] d[*] e[*]}]]
set_output_delay -clock [get_clocks sys_clk] 0.5 [get_ports [get_ports {y[*]}]]

set_false_path -from [get_ports rst_n]

