# KiCad Code Generation

Parse KiCad [intermediate XML netlist format](https://docs.kicad.org/9.0/en/eeschema/eeschema.html#generator-command-line-format).

Create the netlist like this:
```bash
kicad-cli sch export netlist --format kicadxml --output ICA_EPS_Distribution.xml ~/pluto_eps_distribution/ICA_EPS_Distribution.kicad_sch
python3 main.py ICA_EPS_Distribution.xml /Controller/Controller
```
