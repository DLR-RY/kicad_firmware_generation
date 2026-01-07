import argparse
import csv
from pathlib import Path
import sys
from typing import Set, Tuple
import re

from common_types.group_types import (
    GlobalGroupPinIdentifier,
    GroupGlob,
    GroupIdentifier,
    GroupNetlistWithConnections,
    GroupPinName,
    GroupWithConnection,
    assert_is_group_path,
    assert_is_group_type,
    assert_is_pin_name,
    assert_is_schematic,
    compile_group_glob,
    connect_netlist,
    does_match_pattern,
    stringify_group_id,
)
from common_types.parse_xml import parse_group_netlist

# TODO: set this properly
TOOL_NAME = "group_many_to_many_map_to_csv v0.1.0"

sort_key_pattern = re.compile(r"(\d+)")


def _get_sort_key(name: str) -> Tuple[int, str]:
    matches = re.findall(sort_key_pattern, name)
    num = 0 if len(matches) == 0 else int(matches[-1])
    return num, name


def _simplify_nets(
    netlist: GroupNetlistWithConnections,
    simplify_pins: Set[GroupPinName],
) -> GroupNetlistWithConnections:
    # Simplify some nets.
    for group in netlist.groups.values():
        for pin in group.pins.values():
            # Check if this net can be simplified.

            # Not None iff we found a simplification.
            found_simplify_pin: GroupPinName | None = None
            for _, other_pin in pin:
                for simplify_pin in simplify_pins:
                    if simplify_pin in other_pin:
                        found_simplify_pin = simplify_pin
                        print(
                            f"Warning: Simplifying {other_pin} to {found_simplify_pin}",
                            file=sys.stderr,
                        )
                        break
                if found_simplify_pin is not None:
                    break
            if found_simplify_pin is not None:
                pin.clear()
                pin.add(
                    GlobalGroupPinIdentifier(
                        GroupIdentifier(
                            # TODO: do this better
                            assert_is_schematic("This_was"),
                            assert_is_group_path("/Simplified/"),
                            assert_is_group_type("Away"),
                        ),
                        found_simplify_pin,
                    )
                )

    return netlist


# This is for example used for connectors.
# There we only care about connectors and don't care about connections between connectors,
# only from connector to other groups (i.e., non-root groups).
def _focus_on_root(
    netlist: GroupNetlistWithConnections,
    root_group_glob: GroupGlob | None,
) -> GroupNetlistWithConnections:
    # Remove all root pins from the other pins.
    def remove_root_pins(group: GroupWithConnection) -> GroupWithConnection:
        group.pins = {
            pin: {
                other_pin
                for other_pin in other_pins
                if not does_match_pattern(root_group_glob, other_pin.group_id)
            }
            for (pin, other_pins) in group.pins.items()
        }
        return group

    # Remove all other groups.
    netlist.groups = {
        group_id: remove_root_pins(group)
        for (group_id, group) in netlist.groups.items()
        if does_match_pattern(root_group_glob, group_id)
    }
    return netlist


def main() -> None:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Convert a group netlist to a csv. "
        "The output is printed to stdout, errors and warnings to stderr.",
    )
    parser.add_argument("group_netlist_path", help="The path to the group netlist.")
    parser.add_argument(
        "--root-group-glob",
        help="From what groups' perspective should the output be? "
        "This field is a glob. Use ** to match multiple path nodes. "
        "If this field is provided, only groups that don't match are considered as other groups. "
        "I.e., connections from matched groups to other matched groups are ignored. "
        "If this isn't provided, all groups will be included.",
    )
    parser.add_argument(
        "--simplify-pins",
        help="If a group connects to a pin that has this field as a substring, reduce all pins that belong to this net to a single pin with the provided name. "
        "Separate multiple values with a comma (,). "
        "When more than on simplification matches, an arbitraty one will be chosen."
        "This is, for example, useful to replace all GND connections with a single GND pin.",
    )
    args = parser.parse_args()

    group_netlist_path = Path(args.group_netlist_path)

    simplify_pins: Set[GroupPinName] = {
        assert_is_pin_name(pin)
        for pin in ([] if args.simplify_pins is None else args.simplify_pins.split(","))
    }

    root_group_glob = (
        None
        if args.root_group_glob is None
        else compile_group_glob(args.root_group_glob)
    )

    netlist = connect_netlist(parse_group_netlist(group_netlist_path))
    simple_netlist = _simplify_nets(netlist, simplify_pins)
    simple_root_focus_netlist = _focus_on_root(simple_netlist, root_group_glob)

    csv_writer = csv.DictWriter(
        sys.stdout,
        delimiter=",",
        quotechar='"',
        fieldnames=["schematic", "group_path", "group_type", "pin_name", "other_pins"],
        quoting=csv.QUOTE_MINIMAL,
    )
    csv_writer.writeheader()
    group_ids = list(simple_root_focus_netlist.groups.keys())
    group_ids.sort()
    for group_id in group_ids:
        group = simple_root_focus_netlist.groups[group_id]
        pins = list(group.pins.items())
        pins.sort(key=lambda p: _get_sort_key(p[0]))
        for pin_name, other_pins in pins:
            other_pins_list = list(other_pins)
            other_pins_list.sort()
            other_pins_str = "|".join([
                stringify_group_id(other_group_id) + "/" + other_pin
                for other_group_id, other_pin in other_pins_list
            ])
            csv_writer.writerow({
                "schematic": group.schematic,
                "group_path": group.path,
                "group_type": group.group_type,
                "pin_name": pin_name,
                "other_pins": other_pins_str,
            })


if __name__ == "__main__":
    main()
