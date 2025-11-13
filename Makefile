all: board.h

ICA_EPS_Distribution_netlist.xml: /home/chris/pluto_eps_distribution/ICA_EPS_Distribution.kicad_sch
	kicad-cli sch export netlist --format kicadxml --output ICA_EPS_Distribution_netlist.xml ~/pluto_eps_distribution/ICA_EPS_Distribution.kicad_sch

ICA_EPS_Distribution_snippet_netlist.xml: ICA_EPS_Distribution_netlist.xml
	python3 -m kicad_snippet_netlister.kicad_snippet_netlister ICA_EPS_Distribution_netlist.xml > ICA_EPS_Distribution_snippet_netlist.xml

ICA_EPS_Distribution_snippet_map.xml: ICA_EPS_Distribution_snippet_netlist.xml
	python3 -m snippet_mapper.snippet_mapper ICA_EPS_Distribution_snippet_netlist.xml '/Controller/Controller' > ICA_EPS_Distribution_snippet_map.xml

board.h: ICA_EPS_Distribution_snippet_map.xml
	python3 -m code_gen.code_gen ICA_EPS_Distribution_snippet_map.xml pluto_eps_templates/board.h.tmpl > board.h

clean:
	rm -vf ICA_EPS_Distribution_netlist.xml ICA_EPS_Distribution_snippet_netlist.xml ICA_EPS_Distribution_snippet_map.xml board.h
