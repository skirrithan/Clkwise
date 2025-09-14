VIVADO = /mnt/c/Windows/System32/cmd.exe /C "C:\\Xilinx\\Vivado\\2024.2\\bin\\vivado.bat"

clean: 
	rm -rf vivado*
	rm -rf ./data/*.rpt
	rm -rf ./hw/.Xil
	rm -rf ./hw/vivado*
	rm -f ./hw/*.txt

vivado: clean
	cd hw/ && $(VIVADO) -mode batch -source run_vivado.tcl

