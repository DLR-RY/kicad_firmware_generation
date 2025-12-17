import argparse
import csv
from pathlib import Path
import sys
from typing import Tuple
import re

from common_types.parse_xml import parse_many_to_many_group_map
from common_types.group_types import stringify_group_id

# TODO: set this properly
TOOL_NAME = "group_many_to_many_map_to_csv v0.1.0"

sort_key_pattern = re.compile(r"(\d+)")


def _get_sort_key(name: str) -> Tuple[int, str]:
    matches = re.findall(sort_key_pattern, name)
    num = 0 if len(matches) == 0 else int(matches[-1])
    return num, name


def main() -> None:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Convert a many-to-many group map to a csv. "
        "The output is printed to stdout, errors and warnings to stderr.",
    )
    parser.add_argument(
        "group_many_to_many_map", help="The path to the group_many_to_many_map."
    )
    args = parser.parse_args()

    group_many_to_many_map = Path(args.group_many_to_many_map)
    map = parse_many_to_many_group_map(group_many_to_many_map)

    csv_writer = csv.DictWriter(
        sys.stdout,
        delimiter=",",
        quotechar='"',
        fieldnames=["schematic", "group_path", "group_type", "pin_name", "other_pins"],
        quoting=csv.QUOTE_MINIMAL,
    )
    csv_writer.writeheader()
    groups = list(map.groups)
    groups.sort(key=lambda s: stringify_group_id(s.get_id()))
    for group in groups:
        pins = list(group.pins.items())
        pins.sort(key=lambda p: _get_sort_key(p[0]))
        for pin_name, other_pins in pins:
            # This should be Set[GlobalGroupPinIdentifier] but that isn't known at runtime.
            assert type(other_pins) is set
            other_pins_list = list(other_pins)
            other_pins_list.sort()
            other_pins_str = "|".join([
                stringify_group_id(other_group_id) + "/" + other_pin
                for other_group_id, other_pin in other_pins_list
            ])
            csv_writer.writerow({
                "schematic": group.schematic,
                "group_path": group.path,
                "group_type": group.type_name,
                "pin_name": pin_name,
                "other_pins": other_pins_str,
            })


if __name__ == "__main__":
    main()
