create_clock -name sys_clk -period 10.0 [get_ports clk] ; # 100 MHz 
set_input_delay  -clock [get_clocks sys_clk] 1.0 [get_ports {a[*] b[*]}]
set_output_delay -clock [get_clocks sys_clk] 1.0 [get_ports {y[*]}]

set_false_path -from [get_ports rst_n]

