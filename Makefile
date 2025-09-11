VIVADO = /mnt/c/Windows/System32/cmd.exe /C "C:\\Xilinx\\Vivado\\2024.2\\bin\\vivado.bat"

clean: 
	rm -rf vivado*
	rm -rf ./data/
	rm -rf ./hw/.Xil
	rm -rf ./hw/vivado*
	rm ./hw/*.txt

vivado: clean
	mkdir ./data
	cd hw/ && $(VIVADO) -mode batch -source run_vivado.tcl

