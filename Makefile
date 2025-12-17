all: ICA_EPS_Distribution_netlist.xml ICA_EPS_Distribution_group_netlist.xml ICA_EPS_SOLBAT_netlist.xml ICA_EPS_SOLBAT_group_netlist.xml combined_group_netlist.xml combined_group_many_to_many_map.xml combined_group_many_to_many_map_connectors.xml board.h connectors.csv

ICA_EPS_Distribution_netlist.xml: /home/chris/pluto_eps_distribution/ICA_EPS_Distribution.kicad_sch
	kicad-cli sch export netlist --format kicadxml --output ICA_EPS_Distribution_netlist.xml ~/pluto_eps_distribution/ICA_EPS_Distribution.kicad_sch

ICA_EPS_SOLBAT_netlist.xml: /home/chris/pluto_eps_solbat/ICA_EPS_SOLBAT.kicad_sch
	kicad-cli sch export netlist --format kicadxml --output ICA_EPS_SOLBAT_netlist.xml ~/pluto_eps_solbat/ICA_EPS_SOLBAT.kicad_sch

ICA_EPS_Distribution_group_netlist.xml: ICA_EPS_Distribution_netlist.xml
	python3 -m kicad_group_netlister.kicad_group_netlister ICA_EPS_Distribution_netlist.xml > ICA_EPS_Distribution_group_netlist.xml

ICA_EPS_SOLBAT_group_netlist.xml: ICA_EPS_SOLBAT_netlist.xml
	python3 -m kicad_group_netlister.kicad_group_netlister ICA_EPS_SOLBAT_netlist.xml > ICA_EPS_SOLBAT_group_netlist.xml

combined_group_netlist.xml: ICA_EPS_Distribution_group_netlist.xml ICA_EPS_SOLBAT_group_netlist.xml
	# TODO: add merger
	python3 -m group_netlist_merger.group_netlist_merger ICA_EPS_Distribution_group_netlist.xml ICA_EPS_SOLBAT_group_netlist.xml > combined_group_netlist.xml

combined_group_many_to_many_map.xml: combined_group_netlist.xml
	python3 -m group_many_to_many_mapper.group_many_to_many_mapper combined_group_netlist.xml > combined_group_many_to_many_map.xml

combined_group_many_to_many_map_connectors.xml: combined_group_netlist.xml
	python3 -m group_many_to_many_mapper.group_many_to_many_mapper --root-group-glob '*/**/Connector*' --simplify-pins 'GND' combined_group_netlist.xml > combined_group_many_to_many_map_connectors.xml

board.h: combined_group_many_to_many_map.xml
	python3 -m code_gen.code_gen combined_group_many_to_many_map.xml pluto_eps_templates/board.h.tmpl > board.h

connectors.csv: combined_group_many_to_many_map_connectors.xml
	python3 -m map_to_csv.map_to_csv combined_group_many_to_many_map_connectors.xml > connectors.csv

clean:
	rm -vf ICA_EPS_Distribution_netlist.xml ICA_EPS_Distribution_group_netlist.xml ICA_EPS_SOLBAT_netlist.xml ICA_EPS_SOLBAT_group_netlist.xml combined_group_netlist.xml combined_group_many_to_many_map.xml combined_group_many_to_many_map_connectors.xml board.h connectors.csv
