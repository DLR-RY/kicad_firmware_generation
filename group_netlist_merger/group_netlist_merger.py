import argparse
import sys
from pathlib import Path
from typing import FrozenSet, Set
from enum import Enum

from common_types.group_types import (
    GroupGlob,
    GroupIdentifier,
    GroupNet,
    GroupNetlist,
    GroupPinName,
    compile_group_glob,
    does_match_pattern,
    stringify_group_id,
)
from common_types.parse_xml import parse_group_netlist
from common_types.stringify_xml import stringify_group_netlist

TOOL_NAME = "group_netlist_merger v0.1.0"
TOOL_NAME_WITH_VERSION = f"{TOOL_NAME} v0.1.0"


class PinMapper(Enum):
    equal = "equal"
    even_odd = "even_odd"

    def __str__(self) -> str:
        return self.value


def _merge_group_netlists(netlists: Set[GroupNetlist]) -> GroupNetlist:
    netlists_list = list(netlists)
    assert len(netlists_list) > 0
    netlist = netlists_list[0]
    for new_netlist in netlists_list[1:]:
        for source in netlist.sources:
            assert source not in new_netlist.sources
        netlist.sources |= new_netlist.sources
        for group_id in netlist.groups.keys():
            assert group_id not in new_netlist.groups
        netlist.groups |= new_netlist.groups
        assert len(netlist.nets & new_netlist.nets) == 0
        netlist.nets |= new_netlist.nets
    return netlist


def _connect_netlist(
    netlist: GroupNetlist, connect_group_globs: Set[GroupGlob], pin_mapper: PinMapper
) -> GroupNetlist:
    # For each group glob figure out what groups it matches.
    to_connect_group_sets: Set[FrozenSet[GroupIdentifier]] = set()
    for connect_group_glob in connect_group_globs:
        to_connect_group_set: Set[GroupIdentifier] = set()
        for group_id in netlist.groups:
            if not does_match_pattern(connect_group_glob, group_id):
                continue
            # Ensure we only connect groups that can be connected.
            if len(to_connect_group_set) != 0:
                group = netlist.groups[group_id]
                other_group = netlist.groups[list(to_connect_group_set)[0]]
                if set(other_group.pins) != set(group.pins):
                    print(
                        f"Error: The connect group glob pattern {connect_group_glob} matches both {stringify_group_id(group.get_id())} and {stringify_group_id(other_group.get_id())} but they don't have the same pins.",
                        file=sys.stderr,
                    )
                    sys.exit(1)
            to_connect_group_set.add(group_id)

        print(f"Merging groups: {to_connect_group_set}", file=sys.stderr)
        if len(to_connect_group_set) < 2:
            print(
                f"Warning: The connect group glob pattern {connect_group_glob} matches fewer than two groups: {to_connect_group_set}.",
                file=sys.stderr,
            )
        to_connect_group_sets.add(frozenset(to_connect_group_set))

    def should_pins_connect(pin_a: GroupPinName, pin_b: GroupPinName) -> bool:
        match pin_mapper:
            case PinMapper.equal:
                return pin_a == pin_b

            case PinMapper.even_odd:
                # 1 <-> 2
                # 2 <-> 1
                # 3 <-> 4
                # 4 <-> 3
                # ...
                try:
                    num_a = int(pin_a)
                    num_b = int(pin_b)
                except ValueError:
                    print(
                        f"Error: The pin_mapper {PinMapper.even_odd} needs numerical pins but {pin_a} and/or {pin_b} are not numerical.",
                        file=sys.stderr,
                    )
                    sys.exit(1)

                if num_a % 2 == 1:
                    return num_a + 1 == num_b
                if num_b % 2 == 1:
                    return num_b + 1 == num_a
                return False

    # This relation should be transitive but isn't.
    # We implement the transitive nature further down.
    # This could be implemented a lot faster but this is a lot simpler and easier to manually verify.
    def should_nets_be_merged(net_a: GroupNet, net_b: GroupNet) -> bool:
        if net_a == net_b:
            return True
        # We need a group_set that connects the two nets.
        # Loop through all to find one.
        for group_set in to_connect_group_sets:
            # We need a node in the net_a that should be connected to a node in net_b.
            for node_a in net_a:
                if node_a.group_id not in group_set:
                    # The node is not of a group that should be connected.
                    continue
                for node_b in net_b:
                    if node_b.group_id not in group_set:
                        # The node is not of a group that should be connected.
                        continue
                    if node_a.group_id == node_b.group_id:
                        # Do not connect a group to itself.
                        # This would be a problem with even_odd pin mapping.
                        continue
                    if not should_pins_connect(node_b.pin, node_a.pin):
                        # The pins of node_a and node_b aren't the same -> don't connect.
                        continue
                    return True
        return False

    out_nets: Set[GroupNet] = set()
    # We go through all nets and check if any other nets should be merged with it.
    # This works great with the non-transitive predicate from above.
    # An alternative would be a breadth-first search but that is more complicated.
    for net in netlist.nets:
        unioned = False
        # Should this net be unioned instead of appended?
        for out_net in out_nets:
            assert should_nets_be_merged(net, out_net) == should_nets_be_merged(
                out_net, net
            )
            if should_nets_be_merged(net, out_net):
                # Update the old net with the new nodes.
                out_nets.remove(out_net)
                out_nets.add(GroupNet(out_net | net))
                unioned = True
                break
        if not unioned:
            out_nets.add(net)

    netlist.nets = out_nets
    return netlist


def merge_group_netlists(
    pin_mapper: PinMapper,
    connect_group_globs: Set[GroupGlob],
    output_path: Path | None,
    netlist_paths: Set[Path],
) -> None:
    """
    This function does the same and has the same parameters as the group_netlist_merger CLI interface.
    """

    netlists: Set[GroupNetlist] = set()
    for netlist_path in netlist_paths:
        netlist = parse_group_netlist(netlist_path)
        for other_netlist in netlists:
            assert len(other_netlist.sources & netlist.sources) == 0
        netlists.add(netlist)

    merged_group_netlist = _merge_group_netlists(
        netlists,
    )
    connected_merged_group_netlist = _connect_netlist(
        merged_group_netlist,
        connect_group_globs,
        pin_mapper,
    )
    output = stringify_group_netlist(connected_merged_group_netlist)
    if output_path is not None:
        print(f"Printing output to: {output_path}")
        with open(output_path, "wb") as file:
            file.write(output)
    else:
        sys.stdout.buffer.write(output)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Merge multiple Group Netlists from different schematics into a single one. "
        "The output is printed to stdout, errors and warnings to stderr.",
    )
    parser.add_argument(
        "pin_mapper",
        help="When two groups should be connected, how should the pins be connected? "
        "When 'equal' every pin is connected with a pin of the same name. "
        "When 'even_odd' (this only works with numerical pin names) every odd pin number n is connected to pin n+1.",
        type=PinMapper,
        choices=list(PinMapper),
    )
    parser.add_argument(
        "--connect-group-glob",
        help="All groups that match this glob are merged into a single one. "
        "All groups that match must have exactly the same pins. "
        "All matching groups are connected together. "
        "This reflects the use of a physical connector, connecting multiple schematics together. "
        "You may provide multiple.",
        action="append",
    )
    parser.add_argument(
        "--output",
        help="The output path. Print to stdout if not provided.",
    )
    parser.add_argument(
        "group_netlist_file",
        help="The path to a Group Netlist files. You may provide multiple.",
        nargs="+",
    )
    args = parser.parse_args()

    merge_group_netlists(
        args.pin_mapper,
        set()
        if args.connect_group_glob is None
        else {compile_group_glob(group_glob) for group_glob in args.connect_group_glob},
        None if args.output is None else Path(args.output),
        {Path(path) for path in args.group_netlist_file},
    )


if __name__ == "__main__":
    main()
