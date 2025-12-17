import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Set

from common_types.parse_xml import parse_group_netlist
from common_types.group_types import (
    GlobalGroupPinIdentifier,
    OtherGroupPinType,
    GroupIdentifier,
    GroupMap,
    GroupNetlist,
    GroupPath,
    GroupPinName,
    GroupType,
    GroupGlob,
    Schematic,
    does_match_pattern,
    compile_group_glob,
)
from common_types.stringify_xml import stringify_group_map

# TODO: set this properly
TOOL_NAME = "group_many_to_many_mapper v0.1.0"


def _gen_many_to_many_group_map(
    netlist: GroupNetlist,
    root_group_pattern: GroupGlob | None,
    simplify_pins: Set[GroupPinName],
) -> GroupMap:
    # general metadata
    group_map = GroupMap()
    group_map.map_type = OtherGroupPinType.MANY_TO_MANY
    group_map.sources = netlist.sources
    group_map.date = datetime.now()
    group_map.tool = TOOL_NAME
    group_map.root_group = None

    # Figure out what groups are connected how.
    for net in netlist.nets:
        for group_identifier, group_pin_name in net:
            # No one has touched this before so it must have remained None.
            assert netlist.groups[group_identifier].pins[group_pin_name] is None
            netlist.groups[group_identifier].pins[group_pin_name] = {
                other_pin
                for other_pin in net
                # Skip the own pin.
                if other_pin
                != GlobalGroupPinIdentifier((group_identifier, group_pin_name))
                # Skip other
                and not does_match_pattern(root_group_pattern, other_pin[0], False)
            }

    # Simplify some nets.
    for group in netlist.groups.values():
        for pin in group.pins.values():
            # Check if this net can be simplified.

            # Should be Set[GlobalGroupPinIdentifier] but that isn't konwn at runtime.
            assert type(pin) is set
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
                    GlobalGroupPinIdentifier((
                        GroupIdentifier((
                            # TODO: do this better
                            Schematic("This_was"),
                            GroupPath("/Simplified/"),
                            GroupType("Away"),
                        )),
                        found_simplify_pin,
                    ))
                )

    group_map.groups = {
        group
        for group in netlist.groups.values()
        if does_match_pattern(root_group_pattern, group.get_id(), True)
    }
    return group_map


def main() -> None:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Generate an overview over every group consisting of what all the group's pins are connected to.",
    )
    parser.add_argument("group_netlist_input", help="The path to the group_netlist.")
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

    group_netlist_path = Path(args.group_netlist_input)
    root_group_glob = (
        None
        if args.root_group_glob is None
        else compile_group_glob(args.root_group_glob)
    )
    simplify_pins: Set[GroupPinName] = {
        GroupPinName(pin)
        for pin in ([] if args.simplify_pins is None else args.simplify_pins.split(","))
    }

    group_netlist = parse_group_netlist(group_netlist_path)
    group_map = _gen_many_to_many_group_map(
        group_netlist, root_group_glob, simplify_pins
    )
    sys.stdout.buffer.write(stringify_group_map(group_map))


if __name__ == "__main__":
    main()
