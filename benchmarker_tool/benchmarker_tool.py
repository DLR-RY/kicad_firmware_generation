from pathlib import Path
import tempfile
import timeit
import subprocess
from typing import Any, Dict, List
import skip
import os
import random

from kicad_group_netlister.kicad_group_netlister import create_group_netlist_from_kicad
from code_gen.code_gen import generate_code
from netlist_to_csv.netlist_to_csv import create_csv_from_netlist
from common_types.parse_xml import parse_group_netlist

from skip.eeschema.schematic.symbol import SymbolPin

TOOL_NAME = "benchmarker_tool v0.1.0"

SYMBOL_ANNOTATION_RATIO = 0.4
GROUP_TYPES = [
    "GroupTypeAlpha",
    "GroupTypeBravo",
    "GroupTypeCharlie",
    "GroupTypeDelta",
    "GroupTypeEcho",
    "GroupTypeFoxtrot",
    "GroupTypeGolf",
    "GroupTypeHotel",
]
REPETITIONS = 2


def main() -> None:
    schematic_files = []
    for root, dirs, files in os.walk("."):
        for name in files:
            if name.endswith(".sch") or name.endswith(".kicad_sch"):
                schematic_files.append(os.path.join(root, name))

    pinname_counter = 0
    statistics: Dict[str, Dict[str, Any]] = dict()
    for file in schematic_files:
        print(f"Creating benchmark for: {file}")
        schem = skip.Schematic(file)
        for symbol in random.sample(
            sorted(schem.symbol), int(SYMBOL_ANNOTATION_RATIO * len(schem.symbol))
        ):
            # Group Type
            group_type_field = symbol.property.Reference.clone()
            group_type_field.name = "GroupType"
            group_type_field.value = random.choice(GROUP_TYPES)

            # Group Pins
            if symbol.pin is None:
                continue
            for pin in symbol.pin:
                if type(pin) is not SymbolPin:
                    continue
                group_pin_field = symbol.property.Reference.clone()
                group_pin_field.name = f"GroupPin{pin.number}"
                group_pin_field.value = f"GroupPin{pinname_counter}"
                pinname_counter += 1
        statistics[file] = {"sym_count": len(schem.symbol)}

        schem.write(file)

    for file, statistic in statistics.items():
        print(f"Creating KiCad Netlist for: {file}")
        kicad_netlist_file = f"{file}_kicad_netlist.xml"
        statistic["kicad_netlist_file"] = kicad_netlist_file

        def run_kicad_cli():
            run = subprocess.run(
                f"kicad-cli sch export netlist --format kicadxml --output {kicad_netlist_file} {file}",
                stderr=subprocess.PIPE,
                shell=True,
            )
            if run.returncode != 0:
                raise ValueError(run.stderr)

        statistic["kicad-cli"] = timeit.timeit(
            run_kicad_cli,
            number=REPETITIONS,
        )
        print(f"{statistic['kicad-cli']}s")

    for file, statistic in statistics.items():
        print(f"Creating Group Netlist for: {file}")
        group_netlist_file = f"{file}_group_netlist.xml"
        statistic["group_netlist_file"] = group_netlist_file

        statistic["kicad_group_netlister"] = timeit.timeit(
            lambda: create_group_netlist_from_kicad(
                Path(statistic["kicad_netlist_file"]),
                True,
                Path(group_netlist_file),
            ),
            number=REPETITIONS,
        )
        group_netlist = parse_group_netlist(Path(group_netlist_file))
        statistic["groups"] = len(group_netlist.groups)
        statistic["average_pins_per_group"] = sum([
            len(group.pins) for group in group_netlist.groups.values()
        ]) / len(group_netlist.groups)
        statistic["nets"] = len(group_netlist.nets)
        statistic["nets_with_multiple_nodes"] = len([
            net for net in group_netlist.nets if len(net) >= 2
        ])
        print(
            f"{statistic['kicad_group_netlister']}s; groups: {statistic['groups']}; average_pins_per_group: {statistic['average_pins_per_group']}; nets: {statistic['nets']}; nets_with_multiple_nodes: {statistic['nets_with_multiple_nodes']}"
        )

    template_str = """
#pragma once

// Assume we've included some library with types like GND, PD2, VCC, PD5.
{# ** is a Group Glob matching all Groups. #}
{% for group in glob_groups("**") %}
{% for periphery_pin in group.pins %}
    {# /Controller is a Group Glob matching only the controller's group. #}
    {% set controller_pin = group.get_single_pin_to_glob(periphery_pin, "*/GroupTypeAlpha") %}
    {% if controller_pin is not none %}
#define {{ pascal_case(group.path) }}{{ group.group_type }}_{{ periphery_pin }} {{ controller_pin.pin }}
    {% else %}
#define {{ pascal_case(group.path) }}{{ group.group_type }}_{{ periphery_pin }} void
    {% endif %}
{% endfor %}
{% endfor %}
    """

    with tempfile.NamedTemporaryFile(mode="w") as template_file:
        template_file.write(template_str)
        template_file.flush()

        for file, statistic in statistics.items():
            print(f"Creating Code for: {file}")
            code_file = f"{file}_code.h"
            statistic["code_file"] = code_file

            statistic["code_gen"] = timeit.timeit(
                lambda: generate_code(
                    Path(statistic["group_netlist_file"]),
                    Path(template_file.name),
                    None,
                    Path(code_file),
                ),
                number=REPETITIONS,
            )
            print(f"{statistic['code_gen']}s")

        print(statistics)


if __name__ == "__main__":
    main()
