# KiCad Code Generation

Parse KiCad [intermediate XML netlist format](https://docs.kicad.org/9.0/en/eeschema/eeschema.html#generator-command-line-format).

Create the netlist, group_map and code like this:
```bash
kicad-cli sch export netlist --format kicadxml --output ICA_EPS_Distribution_netlist.xml ~/pluto_eps_distribution/ICA_EPS_Distribution.kicad_sch
python3 -m kicad_group_mapper.kicad_group_mapper ICA_EPS_Distribution_netlist.xml '/Controller/Controller' > ICA_EPS_Distribution_group_map.xml
python3 -m code_gen.code_gen ICA_EPS_Distribution_group_map.xml pluto_eps_templates/board.h.tmpl > board.h
```

## Steps
- understand what type of use (mix is possible)
    1. snippets (reused components that one can annotate once and use multiple times)
    2. no snippets, annotate the actual use directly (more time-consuming)
