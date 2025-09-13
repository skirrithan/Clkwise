set_part xc7k160tfbg484-3       ;# your known device
read_verilog ./src/top.sv
read_xdc     ./constrs/top.xdc
synth_design -top top -flatten_hierarchy rebuilt -retiming -fsm_extraction one_hot -resource_sharing off -shreg_min_size 5 -keep_equivalent_registers
opt_design
place_design
route_design

# Produce reports your parser will ingest
report_timing_summary -delay_type max -max_paths 20 -warn_on_violation -file ../data/timing_summary.rpt
report_timing -max_paths 10 -path_type full_clock -file ../data/top10_paths.rpt
report_utilization -file ../data/util.rpt
report_design_analysis -timing -of_timing_paths [get_timing_paths -max_paths 10] -file ../data/analysis.rpt

set worst_path   [lindex [get_timing_paths -max_paths 1 -nworst 1] 0]
set worst_slack  [get_property SLACK $worst_path]
puts "WORST_SLACK = $worst_slack ns"
if {$worst_slack < 0.0} {
  puts "ERROR: Timing not met; skipping bitstream."
  exit 2
}

# Generate bitstream (will run if routed and no fatal errors)
puts "no fatal errors"
write_bitstream -force ../data/top.bit

exit
