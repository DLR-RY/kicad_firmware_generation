from pathlib import Path
import tempfile
import csv
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
from common_types.group_types import compile_group_glob

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
CSV_OUTPUT_FILE = f"./statistics_rep_{REPETITIONS}_ratio_{SYMBOL_ANNOTATION_RATIO}.csv"


def main() -> None:
    schematic_files: List[str] = []
    for root, dirs, files in os.walk("."):
        for name in files:
            if name.endswith(".sch") or name.endswith(".kicad_sch"):
                schematic_files.append(os.path.join(root, name))

    pinname_counter = 0
    statistics: Dict[str, Dict[str, Any]] = dict()
    for file in schematic_files:
        print(f"Creating benchmark for: {file}")
        # TODO: remove
        statistics[file] = {"file": file, "sym_count": 0}
        continue
        try:
            schem = skip.Schematic(file)
        except:
            print("skip read error")
            continue
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

        try:
            schem.write(file)
        except:
            print("skip write error")
            continue
        statistics[file] = {"file": file, "sym_count": len(schem.symbol)}

    for file, statistic in statistics.items():
        print(f"Creating KiCad Netlist for: {file}")
        kicad_netlist_file = f"{file}_kicad_netlist.xml"
        statistic["kicad_netlist_file"] = kicad_netlist_file

        def run_kicad_cli():
            run = subprocess.run(
                [
                    "kicad-cli",
                    "sch",
                    "export",
                    "netlist",
                    "--format",
                    "kicadxml",
                    "--output",
                    kicad_netlist_file,
                    str(file),
                ],
                stderr=subprocess.PIPE,
            )
            if run.returncode != 0:
                raise ValueError(run.stderr)

        # TODO: uncomment
        # statistic["kicad-cli"] = timeit.timeit(
        #     run_kicad_cli,
        #     number=REPETITIONS,
        # )
        # print(f"{statistic['kicad-cli']}s")

    drop_files: List[str] = []
    for file, statistic in statistics.items():
        print(f"Creating Group Netlist for: {file}")
        group_netlist_file = f"{file}_group_netlist.xml"
        statistic["group_netlist_file"] = group_netlist_file

        try:
            statistic["kicad_group_netlister"] = timeit.timeit(
                lambda: create_group_netlist_from_kicad(
                    Path(statistic["kicad_netlist_file"]),
                    True,
                    Path(group_netlist_file),
                ),
                number=REPETITIONS,
            )
        except:
            print("Error in kicad_group_netlister")
            drop_files += [file]
            continue

        group_netlist = parse_group_netlist(Path(group_netlist_file))
        statistic["groups"] = len(group_netlist.groups)
        statistic["average_pins_per_group"] = (
            None
            if len(group_netlist.groups) == 0
            else sum([len(group.pins) for group in group_netlist.groups.values()])
            / len(group_netlist.groups)
        )
        statistic["nets"] = len(group_netlist.nets)
        statistic["nets_with_multiple_nodes"] = len([
            net for net in group_netlist.nets if len(net) >= 2
        ])
        print(
            f"{statistic['kicad_group_netlister']}s; groups: {statistic['groups']}; average_pins_per_group: {statistic['average_pins_per_group']}; nets: {statistic['nets']}; nets_with_multiple_nodes: {statistic['nets_with_multiple_nodes']}"
        )

    for file in drop_files:
        statistics.pop(file)

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

    for file, statistic in statistics.items():
        print(f"Creating CSV for: {file}")
        csv_file = f"{file}_spreadsheet.csv"
        statistic["csv_file"] = csv_file

        statistic["netlist_to_csv"] = timeit.timeit(
            lambda: create_csv_from_netlist(
                Path(statistic["group_netlist_file"]),
                compile_group_glob("**"),
                set(),
                Path(csv_file),
            ),
            number=REPETITIONS,
        )
        with open(csv_file) as file:
            statistic["csv_lines"] = len(file.readlines())
            print(
                f"{statistic['netlist_to_csv']}s; csv_lines: {statistic['csv_lines']}"
            )

    with open(CSV_OUTPUT_FILE, "w") as file:
        csv_writer = csv.DictWriter(
            file,
            delimiter=",",
            quotechar='"',
            fieldnames=list(statistics.values())[0].keys(),
            quoting=csv.QUOTE_MINIMAL,
        )
        csv_writer.writeheader()
        for statistic in statistics.values():
            csv_writer.writerow(statistic)


if __name__ == "__main__":
    main()
