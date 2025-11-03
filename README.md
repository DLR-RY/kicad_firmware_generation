# KiCad Code Generation

Parse KiCad [intermediate XML netlist format](https://docs.kicad.org/9.0/en/eeschema/eeschema.html#generator-command-line-format).

Create the netlist like this:
```bash
kicad-cli sch export netlist --format kicadxml ICA_EPS_Distribution.kicad_sch
```
